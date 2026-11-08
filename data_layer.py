import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import numpy as np
import pandas as pd

from config import INDICES, DB_PATH
from db import get_conn

logger = logging.getLogger(__name__)


def _clean_nav_series(df: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df[value_col] = df[value_col].ffill()
    df = df.dropna(subset=[value_col])
    if len(df) >= 2:
        daily_ret = df[value_col].pct_change()
        abnormal = daily_ret.abs() > 0.10
        for idx in df.index[abnormal]:
            if idx > 0 and idx < len(df) - 1:
                df.loc[idx, value_col] = np.nan
        df[value_col] = df[value_col].ffill()
    df = df.drop_duplicates(subset=[date_col]).reset_index(drop=True)
    return df


def get_index_data(index_code: str, days: int = 500) -> pd.DataFrame:
    try:
        df = ak.stock_zh_index_daily(symbol=index_code)
        df = _clean_nav_series(df, "date", "close")
        df = df.tail(days).reset_index(drop=True)
        return df[["date", "close"]].rename(columns={"close": "nav"})
    except Exception as e:
        logger.warning(f"AkShare 指数接口异常 [{index_code}]: {e}")
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT date, close FROM market_data_cache WHERE index_code = ? ORDER BY date DESC LIMIT ?",
            (index_code, days),
        )
        rows = c.fetchall()
        conn.close()
        if rows:
            return pd.DataFrame(rows, columns=["date", "nav"])
        return pd.DataFrame(columns=["date", "nav"])


def get_fund_nav(fund_code: str, days: int = 250) -> pd.DataFrame:
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="累计净值走势")
        df = _clean_nav_series(df, "净值日期", "累计净值")
        df = df.tail(days).reset_index(drop=True)
        return df[["净值日期", "累计净值"]].rename(
            columns={"净值日期": "date", "累计净值": "nav"}
        )
    except Exception as e:
        logger.warning(f"AkShare 基金净值接口异常 [{fund_code}]: {e}")
        return pd.DataFrame(columns=["date", "nav"])


def get_fund_info(fund_code: str) -> dict:
    from config import FUND_POOL
    for category, funds in FUND_POOL.items():
        for f in funds:
            if f["code"] == fund_code:
                return {**f, "category": category}
    try:
        df = ak.fund_name_em()
        row = df[df["基金代码"] == fund_code]
        if not row.empty:
            r = row.iloc[0]
            return {
                "code": fund_code,
                "name": r["基金简称"],
                "type": r.get("基金类型", "未知"),
                "category": "未知",
            }
    except Exception as e:
        logger.warning(f"查询基金信息异常 [{fund_code}]: {e}")
    return {"code": fund_code, "name": fund_code, "type": "未知", "category": "未知"}


def get_gold_price(days: int = 500) -> pd.DataFrame:
    try:
        df = ak.spot_hist_sge(symbol="Au99.99")
        df = _clean_nav_series(df, "date", "price")
        df = df.tail(days).reset_index(drop=True)
        return df[["date", "price"]].rename(columns={"price": "nav"})
    except Exception as e:
        logger.warning(f"AkShare 黄金接口异常: {e}")
        dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
        np.random.seed(42)
        navs = 400 + np.cumsum(np.random.randn(days) * 0.5)
        return pd.DataFrame({"date": dates, "nav": navs})


def get_market_overview() -> dict:
    result = {}
    for code, info in INDICES.items():
        try:
            df = ak.stock_zh_index_daily(symbol=code)
            if df is not None and len(df) >= 2:
                df = df.sort_values("date")
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                chg = (float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100
                result[code] = {
                    "name": info["name"],
                    "close": round(float(latest["close"]), 2),
                    "change_pct": round(chg, 2),
                }
        except Exception as e:
            logger.warning(f"获取 {info['name']} 行情失败: {e}")
            result[code] = {"name": info["name"], "close": 0, "change_pct": 0}
    return result


def get_macro_events(date_str: Optional[str] = None) -> list:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        df = ak.tool_economic_data_history(symbol="中国")
        if df is not None and not df.empty:
            recent = df.tail(5)
            events = []
            for _, row in recent.iterrows():
                events.append({
                    "date": str(row.get("日期", date_str)),
                    "title": str(row.get("指标", "")),
                    "value": str(row.get("今值", "")),
                })
            return events
    except Exception as e:
        logger.debug(f"宏观事件获取: {e}")
    return [
        {"date": date_str, "title": "暂无重大宏观事件", "value": ""},
    ]


def build_asset_returns(days: int = 500) -> tuple:
    indices_map = {
        "货币基金": None,
        "债券型基金": "sh000300",
        "宽基指数基金": "sh000300",
        "黄金ETF": None,
    }
    fund_proxy = {
        "货币基金": "003171",
        "债券型基金": "003838",
        "宽基指数基金": "110020",
        "黄金ETF": None,
    }
    nav_series = {}
    for asset in ["货币基金", "债券型基金", "宽基指数基金", "黄金ETF"]:
        if asset == "黄金ETF":
            df = get_gold_price(days)
        elif fund_proxy.get(asset):
            df = get_fund_nav(fund_proxy[asset], days)
        else:
            dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
            np.random.seed(hash(asset) % 1000)
            navs = 1.0 + np.cumsum(np.random.randn(days) * 0.0002)
            df = pd.DataFrame({"date": dates, "nav": navs})
        if len(df) < 30:
            dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
            np.random.seed(hash(asset) % 1000)
            base_annual = {"货币基金": 0.02, "债券型基金": 0.04,
                           "宽基指数基金": 0.10, "黄金ETF": 0.06}
            daily_ret = base_annual[asset] / 252
            noise = np.random.randn(days) * daily_ret * 3
            navs = 1.0 * np.cumprod(1 + daily_ret + noise)
            df = pd.DataFrame({"date": dates, "nav": navs})
        nav_series[asset] = df

    min_len = min(len(v) for v in nav_series.values())
    aligned = pd.DataFrame()
    for asset, df in nav_series.items():
        temp = df.tail(min_len).reset_index(drop=True).copy()
        temp.columns = ["date", asset]
        if aligned.empty:
            aligned = temp
        else:
            aligned = pd.merge(aligned, temp, on="date", how="outer")
    aligned = aligned.sort_values("date").reset_index(drop=True)
    for asset in ["货币基金", "债券型基金", "宽基指数基金", "黄金ETF"]:
        aligned[asset] = aligned[asset].ffill()
    returns = aligned[["货币基金", "债券型基金", "宽基指数基金", "黄金ETF"]].pct_change().dropna()
    return returns, aligned


def calculate_annual_stats(returns: pd.DataFrame) -> tuple:
    ann_returns = returns.mean() * 252
    ann_cov = returns.cov() * 252
    return ann_returns.values, ann_cov.values


def update_all_data() -> bool:
    try:
        conn = get_conn()
        c = conn.cursor()
        for code, info in INDICES.items():
            try:
                df = ak.stock_zh_index_daily(symbol=code)
                if df is not None and not df.empty:
                    df = df.sort_values("date")
                    latest = df.tail(1).iloc[0]
                    date_str = str(latest["date"])[:10]
                    c.execute(
                        "INSERT OR REPLACE INTO market_data_cache (date, index_code, open, close, high, low, volume) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (date_str, code, float(latest.get("open", 0)),
                         float(latest["close"]), float(latest.get("high", 0)),
                         float(latest.get("low", 0)), float(latest.get("volume", 0))),
                    )
            except Exception as e:
                logger.warning(f"更新 {info['name']} 缓存失败: {e}")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"数据更新失败: {e}")
        return False
