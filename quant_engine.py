import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from config import (
    RISK_FREE_RATE, TRADING_DAYS, RISK_CONSTRAINTS, RISK_LEVEL_MAP,
    DIM_WEIGHTS, RISK_QUESTIONS, MARKET_EQUILIBRIUM_WEIGHTS,
    RISK_AVERSION, BL_TAU, FUND_POOL,
)
from data_layer import build_asset_returns, calculate_annual_stats, get_fund_nav

logger = logging.getLogger(__name__)

ASSET_NAMES = ["货币基金", "债券型基金", "宽基指数基金", "黄金ETF"]


def calculate_risk_score(answers: dict) -> tuple:
    dim_scores = {}
    dim_count = {}
    for q in RISK_QUESTIONS:
        qid = str(q["id"])
        if qid in answers:
            ans_val = answers[qid]
            for opt in q["options"]:
                if opt["score"] == int(ans_val) or opt["text"] == ans_val:
                    dim = q["dim"]
                    dim_scores[dim] = dim_scores.get(dim, 0) + opt["score"]
                    dim_count[dim] = dim_count.get(dim, 0) + 1
                    break

    weighted_total = 0.0
    total_weight = 0.0
    for dim, score in dim_scores.items():
        avg = score / dim_count[dim]
        weight = DIM_WEIGHTS.get(dim, 0)
        weighted_total += avg * weight
        total_weight += weight

    if total_weight == 0:
        return 0, 1, "保守型"

    raw_score = round(weighted_total * 10)

    for entry in RISK_LEVEL_MAP:
        if raw_score <= entry["max"]:
            return raw_score, entry["level"], entry["label"]
    return raw_score, 5, "进取型"


def _portfolio_variance(w, cov_matrix):
    return np.dot(w.T, np.dot(cov_matrix, w))


def _neg_sharpe(w, expected_returns, cov_matrix, rf=RISK_FREE_RATE):
    ret = np.dot(w, expected_returns)
    vol = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
    if vol < 1e-8:
        return 0
    return -(ret - rf) / vol


def _get_constraints(risk_level: int):
    rc = RISK_CONSTRAINTS.get(risk_level, RISK_CONSTRAINTS[3])
    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "ineq", "fun": lambda w: w[2] - 0.0},
        {"type": "ineq", "fun": lambda w: rc["equity_max"] - w[2]},
        {"type": "ineq", "fun": lambda w: w[3] - 0.0},
        {"type": "ineq", "fun": lambda w: rc["gold_max"] - w[3]},
        {"type": "ineq", "fun": lambda w: w[1] - rc["bond_min"]},
        {"type": "ineq", "fun": lambda w: w[0] - rc["cash_min"]},
    ]
    return constraints


def _black_litterman_returns(prior_returns, cov_matrix, P, Q, Omega=None):
    if P is None or Q is None:
        return prior_returns
    pi = RISK_AVERSION * cov_matrix @ np.array(MARKET_EQUILIBRIUM_WEIGHTS)
    if Omega is None:
        Omega = np.eye(len(Q)) * 0.3 * np.diag(P @ (BL_TAU * cov_matrix) @ P.T)
    tau_cov = BL_TAU * cov_matrix
    A = tau_cov @ P.T
    B = P @ A + Omega
    posterior = pi + A @ np.linalg.lstsq(B, Q - P @ pi, rcond=None)[0]
    return posterior


def optimize_portfolio(expected_returns, cov_matrix, risk_level: int):
    n = len(expected_returns)
    constraints = _get_constraints(risk_level)
    bounds = tuple((0, 1) for _ in range(n))
    x0 = np.ones(n) / n

    result = minimize(
        _neg_sharpe, x0, args=(expected_returns, cov_matrix),
        method="SLSQP", bounds=bounds, constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-8},
    )
    if not result.success:
        logger.warning(f"优化未收敛: {result.message}, 使用等权回退")
        w = np.ones(n) / n
        rc = RISK_CONSTRAINTS.get(risk_level, RISK_CONSTRAINTS[3])
        w[2] = min(w[2], rc["equity_max"])
        w[3] = min(w[3], rc["gold_max"])
        w[1] = max(w[1], rc["bond_min"])
        w[0] = max(w[0], rc["cash_min"])
        w = w / w.sum()
    else:
        w = result.x
    w = np.clip(w, 0, 1)
    w = w / w.sum()
    return w


def get_efficient_frontier(expected_returns, cov_matrix, n_points=50):
    min_ret = expected_returns.min()
    max_ret = expected_returns.max()
    target_returns = np.linspace(min_ret, max_ret * 0.8, n_points)
    frontier = []
    n = len(expected_returns)
    bounds = tuple((0, 1) for _ in range(n))
    x0 = np.ones(n) / n

    for tr in target_returns:
        cons = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w, tr=tr: np.dot(w, expected_returns) - tr},
        ]
        res = minimize(
            _portfolio_variance, x0, args=(cov_matrix,),
            method="SLSQP", bounds=bounds, constraints=cons,
            options={"maxiter": 300, "ftol": 1e-8},
        )
        if res.success:
            vol = np.sqrt(res.fun)
            frontier.append({"return": round(float(tr), 4), "volatility": round(float(vol), 4)})
    return frontier


def _pick_funds(weights):
    picks = []
    for i, asset in enumerate(ASSET_NAMES):
        if weights[i] < 0.001:
            continue
        pool = FUND_POOL.get(asset, [])
        if pool:
            fund = pool[0]
            picks.append({
                "category": asset,
                "code": fund["code"],
                "name": fund["name"],
                "type": fund["type"],
                "weight": round(float(weights[i]), 4),
            })
    return picks


def calculate_allocation(amount: float, period: int, risk_level: int) -> dict:
    returns_df, _ = build_asset_returns(days=500)
    if len(returns_df) < 30:
        logger.warning("历史数据不足，使用模拟数据")
        np.random.seed(42)
        base = {"货币基金": 0.02, "债券型基金": 0.04, "宽基指数基金": 0.10, "黄金ETF": 0.06}
        for asset in ASSET_NAMES:
            daily_r = base[asset] / 252
            noise = np.random.randn(250) * daily_r * 3
            returns_df[asset] = daily_r + noise

    expected_returns, cov_matrix = calculate_annual_stats(returns_df)

    P = np.array([[0, 0, 1, -1]])
    Q = np.array([0.02])
    Omega = np.array([[0.3]])
    bl_returns = _black_litterman_returns(expected_returns, cov_matrix, P, Q, Omega)

    optimal_weights = optimize_portfolio(bl_returns, cov_matrix, risk_level)

    port_return = float(np.dot(optimal_weights, bl_returns))
    port_vol = float(np.sqrt(np.dot(optimal_weights.T, np.dot(cov_matrix, optimal_weights))))
    sharpe = (port_return - RISK_FREE_RATE) / (port_vol + 1e-8)

    nav_series = np.cumprod(1 + returns_df.values @ optimal_weights / 252 + np.zeros(len(returns_df)))
    if len(nav_series) > 0:
        peak = np.maximum.accumulate(nav_series)
        drawdowns = (nav_series - peak) / peak
        max_drawdown = float(min(drawdowns.min(), 0))
    else:
        max_drawdown = -0.05

    frontier = get_efficient_frontier(bl_returns, cov_matrix, 30)

    fund_picks = _pick_funds(optimal_weights)

    weights_dict = {}
    for i, asset in enumerate(ASSET_NAMES):
        weights_dict[asset] = round(float(optimal_weights[i]), 4)
    weights_dict["现金留存"] = round(max(0, 1 - sum(optimal_weights)), 4)

    return {
        "weights": weights_dict,
        "expected_return": round(port_return, 4),
        "expected_return_amount": round(port_return * amount, 2),
        "max_drawdown": round(max_drawdown, 4),
        "max_loss_amount": round(max_drawdown * amount, 2),
        "volatility": round(port_vol, 4),
        "sharpe": round(sharpe, 4),
        "fund_picks": fund_picks,
        "efficient_frontier": frontier,
        "input": {"amount": amount, "period": period, "risk_level": risk_level},
    }


def _calc_max_drawdown(nav: np.ndarray) -> float:
    peak = np.maximum.accumulate(nav)
    drawdowns = (nav - peak) / peak
    return float(min(drawdowns.min(), 0)) if len(drawdowns) > 0 else 0


def calculate_risk_metrics(returns: pd.Series, rf: float = RISK_FREE_RATE) -> dict:
    if len(returns) < 2:
        return {"sharpe": 0, "sortino": 0, "volatility": 0, "max_drawdown": 0, "annual_return": 0}

    ann_return = float(returns.mean() * TRADING_DAYS)
    ann_vol = float(returns.std() * np.sqrt(TRADING_DAYS))
    sharpe = (ann_return - rf) / (ann_vol + 1e-8)

    downside = returns[returns < 0]
    if len(downside) > 0:
        downside_vol = float(downside.std() * np.sqrt(TRADING_DAYS))
        sortino = (ann_return - rf) / (downside_vol + 1e-8)
    else:
        sortino = sharpe

    nav = np.cumprod(1 + returns.values)
    mdd = _calc_max_drawdown(nav)

    return {
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "volatility": round(ann_vol, 4),
        "max_drawdown": round(mdd, 4),
        "annual_return": round(ann_return, 4),
    }


def diagnose_portfolio(holdings: list) -> dict:
    if not holdings:
        return {"error": "持仓为空，请先添加持仓"}

    nav_dfs = {}
    total_amount = sum(h["amount"] for h in holdings)

    for h in holdings:
        code = h["fund_code"]
        if code not in nav_dfs:
            df = get_fund_nav(code, days=250)
            if len(df) >= 30:
                df = df.set_index("date")
                nav_dfs[code] = df["nav"]
            else:
                dates = pd.date_range(end="2026-09-13", periods=250, freq="B")
                np.random.seed(hash(code) % 1000)
                navs = 1.0 + np.cumsum(np.random.randn(250) * 0.002)
                nav_dfs[code] = pd.Series(navs, index=dates)

    combined = pd.DataFrame(nav_dfs)
    combined = combined.ffill().dropna()
    if len(combined) < 30:
        return {"error": "有效净值数据不足，无法诊断"}

    # 按基金代码聚合权重（同一基金多次买入合并计算），并与 combined 列对齐
    weight_map = {}
    for h in holdings:
        code = h["fund_code"]
        if code in weight_map:
            weight_map[code] += h["amount"] / total_amount
        else:
            weight_map[code] = h["amount"] / total_amount
    # 构建与 combined 列顺序一致的权重 Series
    weights = pd.Series(
        [weight_map.get(col, 0.0) for col in combined.columns],
        index=combined.columns
    )
    port_returns = (combined.pct_change().fillna(0) * weights).sum(axis=1)

    metrics = calculate_risk_metrics(port_returns)
    sharpe = metrics["sharpe"]
    ret_risk_score = round(30 * min(1, max(0, sharpe) / 1.0))

    asset_categories = {"货币基金": 0, "债券型基金": 0, "宽基指数基金": 0, "黄金ETF": 0}
    for h in holdings:
        fund_type = h.get("fund_type", "")
        if "货币" in fund_type or "货" in fund_type:
            asset_categories["货币基金"] += h["amount"]
        elif "债" in fund_type:
            asset_categories["债券型基金"] += h["amount"]
        elif "指数" in fund_type or "股" in fund_type:
            asset_categories["宽基指数基金"] += h["amount"]
        elif "黄金" in fund_type or "gold" in fund_type.lower():
            asset_categories["黄金ETF"] += h["amount"]
        else:
            asset_categories["宽基指数基金"] += h["amount"]

    actual_w = np.array([v / total_amount for v in asset_categories.values()])
    target_w = np.array([0.15, 0.30, 0.40, 0.15])
    deviation = float(np.sum(np.abs(actual_w - target_w)) / 2)
    div_score = round(25 * max(0, 1 - deviation / 0.5))

    cr3 = float(sum(sorted(actual_w, reverse=True)[:3]))
    conc_score = round(25 * max(0, 1 - max(0, (cr3 - 0.4) / 0.6)))

    value_ratio = 0.5
    growth_ratio = 0.5
    for h in holdings:
        fund_type = h.get("fund_type", "")
        if "成长" in fund_type or "创业板" in fund_type:
            growth_ratio += h["amount"] / total_amount * 0.3
        if "价值" in fund_type or "沪深300" in fund_type:
            value_ratio += h["amount"] / total_amount * 0.2
    value_ratio = min(1.0, value_ratio)
    growth_ratio = min(1.0, growth_ratio)
    style_score = round(20 * max(0, 1 - abs(value_ratio - 0.5) - abs(growth_ratio - 0.5)))

    total_score = ret_risk_score + div_score + conc_score + style_score

    risk_points = []
    advice_actions = []

    if sharpe < 0.5:
        risk_points.append(f"夏普比率偏低（{sharpe:.2f}），承担的风险没有换来足够的收益")
        advice_actions.append({"type": "rebalance", "desc": "考虑调整持仓结构，提高收益风险比"})
    if deviation > 0.4:
        risk_points.append(f"资产分散度不足（偏离度{deviation*100:.0f}%），大类资产配置与推荐方案差距较大")
        advice_actions.append({"type": "add_asset", "desc": "建议补充缺失的资产类别，使配置更均衡"})
    if cr3 > 0.6:
        risk_points.append(f"行业集中度偏高（前三大占比{cr3*100:.0f}%），超过60%安全线")
        advice_actions.append({"type": "reduce", "target": "重仓行业", "amount_ratio": 0.15})
    if growth_ratio > 0.7:
        risk_points.append(f"风格偏成长（成长占比{growth_ratio*100:.0f}%），风格失衡")
        advice_actions.append({"type": "add_value", "desc": "建议增加价值风格标的，平衡风格暴露"})
    if value_ratio > 0.7:
        risk_points.append(f"风格偏价值（价值占比{value_ratio*100:.0f}%），风格失衡")
        advice_actions.append({"type": "add_growth", "desc": "建议增加成长风格标的，平衡风格暴露"})

    if total_score >= 85:
        rating = "优秀"
    elif total_score >= 70:
        rating = "中等健康"
    elif total_score >= 55:
        rating = "需关注"
    else:
        rating = "需调整"

    return {
        "total_score": total_score,
        "rating": rating,
        "total_amount": total_amount,
        "metrics": metrics,
        "dimensions": {
            "return_risk": {"score": ret_risk_score, "max": 30, "sharpe": sharpe, "sortino": metrics["sortino"]},
            "diversification": {"score": div_score, "max": 25, "deviation": round(deviation, 4)},
            "concentration": {"score": conc_score, "max": 25, "cr3": round(cr3, 4)},
            "style": {"score": style_score, "max": 20, "value_ratio": round(value_ratio, 4),
                      "growth_ratio": round(growth_ratio, 4)},
        },
        "risk_points": risk_points,
        "advice_actions": advice_actions,
    }
