import json
import logging
import os
from datetime import datetime

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Streamlit Community Cloud Secrets 注入：
# 将平台侧 st.secrets 中的配置写入 os.environ，使 config.py/ai_service.py
# 无需改动即可读取 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 等配置。
# 本地开发时由 .env 文件（python-dotenv）提供，二者互不冲突。
try:
    if st.secrets:
        for _k, _v in st.secrets.items():
            if isinstance(_v, str) and not os.environ.get(_k):
                os.environ[_k] = _v
except Exception:
    pass

from config import (
    RISK_QUESTIONS, RISK_LEVEL_MAP, FUND_POOL, DISCLAIMER,
    ASSET_CATEGORIES, INDICES, LLM_CONFIG,
)
from db import (
    init_db, get_or_create_user, get_user_info, save_risk_assessment,
    add_holding, delete_holding, get_holdings, save_allocation,
    save_chat, get_chat_history,
)
from data_layer import get_market_overview, get_macro_events
from quant_engine import calculate_risk_score, calculate_allocation, diagnose_portfolio
from ai_service import generate_interpretation, generate_market_summary, chat_answer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def st_metric(label, value, delta=None):
    parts = [f"<div style='text-align:center;padding:8px 4px'>",
             f"<div style='font-size:0.75rem;color:#6A737D;margin-bottom:4px'>{label}</div>",
             f"<div style='font-size:1.4rem;font-weight:bold;color:#0969DA'>{value}</div>"]
    if delta:
        parts.append(f"<div style='font-size:0.7rem;color:#6A737D;margin-top:2px'>{delta}</div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


st.set_page_config(
    page_title="阿尔法智投 - AI 智能投资顾问",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session():
    if "db_initialized" not in st.session_state:
        init_db()
        st.session_state["db_initialized"] = True
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = get_or_create_user()
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []


def render_sidebar():
    st.sidebar.markdown("## 阿尔法智投")
    st.sidebar.markdown("*AI 智能投资顾问系统*")
    st.sidebar.divider()

    user_id = st.session_state["user_id"]
    user_info = get_user_info(user_id)
    risk_level = user_info.get("risk_level")
    risk_score = user_info.get("risk_score")

    if risk_level:
        level_info = RISK_LEVEL_MAP[risk_level - 1]
        st.sidebar.markdown(f"**风险等级**")
        st.sidebar.markdown(f"<span style='font-size:1.5rem;font-weight:bold;color:#0969DA'>{level_info['label']}</span>",
                            unsafe_allow_html=True)
        st.sidebar.caption(f"测评得分：{risk_score} 分")
    else:
        st.sidebar.warning("尚未完成风险测评")

    st.sidebar.divider()
    page = st.sidebar.radio("功能导航", [
        "🏠 首页",
        "📋 风险测评",
        "💼 持仓管理",
        "📊 资产配置",
        "🔍 持仓诊断",
        "📰 市场解读",
        "💬 智能问答",
    ])

    st.sidebar.divider()
    st.sidebar.caption("投资有风险，入市需谨慎。")
    st.sidebar.caption("本系统不提供个股买卖建议，不承诺收益。")
    st.sidebar.caption(f"© 2026 阿尔法炼丹房 | AI+工程管理课程项目")
    return page


def render_home():
    st.markdown("# 阿尔法智投 AI 智能投资顾问系统")
    st.markdown("### 专业量化打底 · AI 通俗解读 · 普惠陪伴式投顾")
    st.divider()

    st.markdown("""
    阿尔法智投结合金融工程专业量化能力与 AI 大语言模型技术，
    打造一款「底层量化可验证、上层表达通俗化」的智能投顾工具。

    系统以 Markowitz 均值-方差模型 + Black-Litterman 模型为量化底座，
    通过 AI 大语言模型将专业量化结果转化为通俗易懂的投资建议。
    """)

    st.markdown("### 核心功能")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st_metric("资产配置", "Markowitz + BL", "个性化配置方案")
    with col2:
        st_metric("持仓诊断", "四维度评分", "识别风险点")
    with col3:
        st_metric("市场解读", "每日自动", "关联持仓影响")
    with col4:
        st_metric("智能问答", "合规校验", "通俗化解答")

    st.markdown("### 技术架构")
    st.markdown("""
    | 层 | 技术 | 职责 |
    |---|---|---|
    | 数据层 | AkShare + SQLite | 行情数据采集、清洗、存储 |
    | 量化引擎层 | SciPy + NumPy | 组合优化、风险计算、持仓评分 |
    | AI 服务层 | LangChain + LLM | 提示词工程、合规校验、内容生成 |
    | 应用展示层 | Streamlit | 交互界面、结果可视化 |
    """)

    user_id = st.session_state["user_id"]
    user_info = get_user_info(user_id)
    if not user_info.get("risk_level"):
        st.warning("请先完成风险测评，才能使用资产配置等功能。")
        if st.button("去完成风险测评", type="primary"):
            st.session_state["nav_page"] = "📋 风险测评"
            st.rerun()


def render_risk_assessment():
    st.markdown("# 风险测评")
    st.markdown("请如实回答以下问题，系统将根据您的回答评估风险承受能力。")
    st.progress(0)

    answers = {}
    for i, q in enumerate(RISK_QUESTIONS):
        st.markdown(f"**Q{i+1}. {q['text']}**")
        options = [opt["text"] for opt in q["options"]]
        choice = st.radio(
            f"question_{q['id']}",
            options,
            label_visibility="collapsed",
            key=f"q_{q['id']}",
        )
        selected_opt = next(opt for opt in q["options"] if opt["text"] == choice)
        answers[str(q["id"])] = selected_opt["score"]
        st.markdown("")

    if st.button("提交测评", type="primary"):
        score, level, label = calculate_risk_score(answers)
        user_id = st.session_state["user_id"]
        save_risk_assessment(user_id, answers, score, level)

        st.success("风险测评完成！")
        st.markdown(f"### 测评结果")
        col1, col2 = st.columns(2)
        with col1:
            st_metric("得分", f"{score} 分")
        with col2:
            st_metric("风险等级", label)

        level_info = RISK_LEVEL_MAP[level - 1]
        st.info(f"**配置建议**：{level_info['desc']}")
        st.caption(DISCLAIMER)

        if st.button("返回首页"):
            st.session_state["nav_page"] = "🏠 首页"
            st.rerun()


def render_portfolio_manager():
    st.markdown("# 持仓管理")
    st.markdown("记录和管理您的投资持仓。支持公募基金和宽基指数基金。")

    with st.expander("添加持仓", expanded=True):
        with st.form("add_holding_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                fund_code = st.text_input("基金代码", placeholder="6位基金代码，如 110020", max_chars=6)
            with col2:
                amount = st.number_input("持仓金额（元）", min_value=100, max_value=5000000, value=10000, step=1000)
            with col3:
                buy_date = st.date_input("买入日期", value=datetime.now())

            col_a, col_b = st.columns(2)
            with col_a:
                fund_name_input = st.text_input("基金名称（可选，留空自动查询）")
            with col_b:
                fund_type_input = st.selectbox("基金类型", ["", "货币型", "债券型", "指数型", "股票型", "混合型", "黄金型"])

            submitted = st.form_submit_button("添加", type="primary")
            if submitted:
                if not fund_code or len(fund_code) != 6 or not fund_code.isdigit():
                    st.error("请输入6位数字基金代码")
                else:
                    from data_layer import get_fund_info
                    fund_info = get_fund_info(fund_code)
                    fund_name = fund_name_input or fund_info.get("name", fund_code)
                    fund_type = fund_type_input or fund_info.get("type", "未知")

                    user_id = st.session_state["user_id"]
                    add_holding(
                        user_id, fund_code, fund_name, fund_type,
                        float(amount), buy_date.strftime("%Y-%m-%d"),
                    )
                    st.success(f"已添加：{fund_name}（{fund_code}）- {amount}元")
                    st.rerun()

    st.divider()
    st.markdown("### 当前持仓")

    user_id = st.session_state["user_id"]
    holdings = get_holdings(user_id)

    if not holdings:
        st.info("暂无持仓，请在上方添加。")
    else:
        total = sum(h["amount"] for h in holdings)
        df_data = []
        for h in holdings:
            df_data.append({
                "基金代码": h["fund_code"],
                "基金名称": h["fund_name"],
                "类型": h["fund_type"],
                "持仓金额": h["amount"],
                "占比": f"{h['amount']/total*100:.1f}%",
                "买入日期": h["buy_date"],
            })

        import pandas as pd
        df = pd.DataFrame(df_data)
        st.table(df)
        st_metric("持仓总额", f"{total:,.0f} 元")

        st.markdown("### 删除持仓")
        del_options = [f"{h['fund_name']}（{h['fund_code']}）- {h['amount']}元" for h in holdings]
        del_choice = st.selectbox("选择要删除的持仓", [""] + del_options)
        if del_choice and st.button("确认删除"):
            idx = del_options.index(del_choice)
            delete_holding(holdings[idx]["portfolio_id"])
            st.success("已删除")
            st.rerun()


def render_asset_allocation():
    st.markdown("# 个性化资产配置")
    st.markdown("输入投资参数，系统基于量化模型生成符合您风险等级的资产配置方案。")

    user_id = st.session_state["user_id"]
    user_info = get_user_info(user_id)
    risk_level = user_info.get("risk_level")

    if not risk_level:
        st.warning("请先完成风险测评。")
        if st.button("去测评", type="primary"):
            st.session_state["nav_page"] = "📋 风险测评"
            st.rerun()
        return

    level_info = RISK_LEVEL_MAP[risk_level - 1]
    st.info(f"当前风险等级：**{level_info['label']}**")

    col1, col2 = st.columns(2)
    with col1:
        amount = st.number_input("投资金额（元）", min_value=1000, max_value=1000000, value=100000, step=10000)
    with col2:
        period = st.select_slider("投资期限（月）", [3, 6, 12, 24, 36], 12)

    if st.button("生成配置方案", type="primary"):
        with st.spinner("正在计算最优配置方案..."):
            result = calculate_allocation(float(amount), int(period), int(risk_level))

        save_allocation(user_id, {"amount": float(amount), "period": int(period), "risk_level": int(risk_level)}, result)

        st.success("配置方案生成完成！")

        weights = result["weights"]
        labels = [k for k, v in weights.items() if v > 0]
        values = [v for k, v in weights.items() if v > 0]

        col_chart, col_detail = st.columns([1, 1])
        with col_chart:
            colors = ["#0969DA", "#8250DF", "#06B6D4", "#BF3989", "#D0D7DE"]
            fig = go.Figure(data=[go.Pie(
                labels=labels, values=values,
                hole=0.5, marker=dict(colors=colors[:len(labels)]),
                textinfo="label+percent",
            )])
            fig.update_layout(height=350, showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

        with col_detail:
            st.markdown("#### 配置明细")
            for label, val in zip(labels, values):
                st.markdown(f"- **{label}**：{val*100:.1f}%（{val*amount:,.0f} 元）")

        st.markdown("---")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st_metric("预期年化收益", f"{result['expected_return']*100:.1f}%")
        with col_m2:
            st_metric("预期收益金额", f"{result['expected_return_amount']:,.0f} 元")
        with col_m3:
            st_metric("最大回撤", f"{result['max_drawdown']*100:.1f}%")
        with col_m4:
            st_metric("夏普比率", f"{result['sharpe']:.2f}")

        st.markdown("#### 推荐标的")
        fund_data = []
        for pick in result.get("fund_picks", []):
            fund_data.append({
                "资产类别": pick["category"],
                "基金代码": pick["code"],
                "基金名称": pick["name"],
                "类型": pick["type"],
                "配置比例": f"{pick['weight']*100:.1f}%",
                "配置金额": f"{pick['weight']*amount:,.0f} 元",
            })
        if fund_data:
            import pandas as pd
            st.table(pd.DataFrame(fund_data))

        st.markdown("---")
        st.markdown("#### AI 方案解读")
        with st.spinner("AI 正在生成通俗化解读..."):
            interpretation = generate_interpretation(result, {"risk_level": risk_level, "amount": float(amount), "period": int(period)}, "allocation")
        st.info(interpretation)

        if result.get("efficient_frontier"):
            st.markdown("#### 有效前沿")
            frontier = result["efficient_frontier"]
            fig_ef = go.Figure()
            fig_ef.add_trace(go.Scatter(
                x=[p["volatility"] for p in frontier],
                y=[p["return"] for p in frontier],
                mode="lines+markers",
                name="有效前沿",
                line=dict(color="#0969DA", width=2),
            ))
            fig_ef.add_trace(go.Scatter(
                x=[result["volatility"]],
                y=[result["expected_return"]],
                mode="markers",
                name="您的配置",
                marker=dict(size=12, color="#BF3989", symbol="star"),
            ))
            fig_ef.update_layout(
                xaxis_title="年化波动率", yaxis_title="年化收益率",
                height=300, margin=dict(t=10, b=10),
            )
            st.plotly_chart(fig_ef, use_container_width=True)


def render_portfolio_diagnosis():
    st.markdown("# 持仓健康度诊断")
    st.markdown("从收益风险比、资产分散度、行业集中度、风格暴露四个维度评估持仓健康度。")

    user_id = st.session_state["user_id"]
    holdings = get_holdings(user_id)

    if not holdings:
        st.warning("暂无持仓，请先在持仓管理中添加。")
        if st.button("去添加持仓", type="primary"):
            st.session_state["nav_page"] = "💼 持仓管理"
            st.rerun()
        return

    st.markdown("#### 当前持仓概览")
    total = sum(h["amount"] for h in holdings)
    for h in holdings:
        st.markdown(f"- {h['fund_name']}（{h['fund_code']}）-{h['fund_type']} - {h['amount']:,.0f}元 ({h['amount']/total*100:.1f}%)")
    st.markdown(f"**持仓总额**：{total:,.0f} 元")

    if st.button("开始诊断", type="primary"):
        with st.spinner("正在分析持仓数据..."):
            result = diagnose_portfolio(holdings)

        if "error" in result:
            st.error(result["error"])
            return

        score = result["total_score"]
        rating = result["rating"]

        st.markdown("### 诊断结果")
        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            color = "#1A7F37" if score >= 85 else "#BF8700" if score >= 55 else "#CF222E"
            st.markdown(f"""
            <div style="text-align:center; padding:20px; border-radius:12px; background:#F6F8FA;">
                <div style="font-size:0.8rem; color:#6A737D;">综合评分</div>
                <div style="font-size:2.8rem; font-weight:bold; color:{color};">{score}</div>
                <div style="font-size:1rem; font-weight:600; color:{color};">{rating}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_s2:
            dims = result["dimensions"]
            dim_list = [
                ("收益风险比", dims["return_risk"]),
                ("资产分散度", dims["diversification"]),
                ("行业集中度", dims["concentration"]),
                ("风格暴露", dims["style"]),
            ]
            for name, info in dim_list:
                pct = info["score"] / info["max"]
                bar_color = "#1A7F37" if pct >= 0.8 else "#BF8700" if pct >= 0.5 else "#CF222E"
                st.markdown(f"**{name}** ({info['score']}/{info['max']})")
                st.progress(pct)

        st.markdown("### 关键指标")
        metrics = result["metrics"]
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st_metric("夏普比率", f"{metrics['sharpe']:.2f}")
        with col_m2:
            st_metric("索提诺比率", f"{metrics['sortino']:.2f}")
        with col_m3:
            st_metric("年化波动率", f"{metrics['volatility']*100:.1f}%")
        with col_m4:
            st_metric("最大回撤", f"{metrics['max_drawdown']*100:.1f}%")

        if result["risk_points"]:
            st.markdown("### 风险点提示")
            for rp in result["risk_points"]:
                st.warning(rp)

        st.markdown("### AI 调仓建议")
        with st.spinner("AI 正在生成调仓建议..."):
            interpretation = generate_interpretation(result, {}, "diagnosis")
        st.info(interpretation)


def render_market_daily():
    st.markdown("# 每日市场解读")
    st.markdown(f"**{datetime.now().strftime('%Y年%m月%d日')}**")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("刷新数据"):
            st.rerun()

    with st.spinner("正在获取市场数据..."):
        market_data = get_market_overview()
        events = get_macro_events()

    st.markdown("### 市场概览")
    cols = st.columns(len(market_data)) if market_data else st.columns(4)
    for i, (code, info) in enumerate(market_data.items()):
        with cols[i]:
            chg = info["change_pct"]
            delta_color = "normal" if chg == 0 else ("normal" if abs(chg) < 0.01 else "inverse")
            st_metric(
                info["name"], f"{info['close']:,.2f}",
                f"{chg:+.2f}%",
            )

    st.markdown("### 核心事件")
    if events:
        for ev in events:
            st.markdown(f"- **{ev.get('title', '')}**：{ev.get('value', '')}")
    else:
        st.info("今日暂无重大宏观事件")

    st.markdown("### AI 市场解读")
    user_id = st.session_state["user_id"]
    holdings = get_holdings(user_id)
    with st.spinner("AI 正在生成市场解读..."):
        summary = generate_market_summary(market_data, events, holdings)
    st.info(summary)


def render_ai_chat():
    st.markdown("# AI 投顾问答")
    st.markdown("向 AI 投顾助手提问投资基础知识、基金产品规则、资产配置逻辑等问题。")

    st.caption("不提供具体个股买卖建议 · 不承诺收益 · 不预测点位")

    user_id = st.session_state["user_id"]
    user_info = get_user_info(user_id)
    risk_level = user_info.get("risk_level")
    holdings = get_holdings(user_id)
    holdings_summary = ", ".join(f"{h['fund_name']}({h['amount']}元)" for h in holdings) if holdings else "暂无持仓"

    for msg in st.session_state.get("chat_messages", []):
        role = msg["role"]
        avatar = "🧑" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.write(msg["content"])

    st.markdown("**快捷问题**")
    quick_qs = ["什么是指数基金？", "什么是夏普比率？", "如何选择基金？", "资产配置的基本原则是什么？"]
    q_cols = st.columns(len(quick_qs))
    for i, q in enumerate(quick_qs):
        if q_cols[i].button(q, key=f"quick_{i}"):
            st.session_state["pending_question"] = q
            st.rerun()

    user_input = st.chat_input("输入您的问题...")
    if "pending_question" in st.session_state:
        user_input = st.session_state.pop("pending_question")

    if user_input:
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user", avatar="🧑"):
            st.write(user_input)

        with st.spinner("AI 正在思考..."):
            chat_history = get_chat_history(user_id, limit=10)
            result = chat_answer(
                user_input,
                {"risk_level": risk_level, "holdings_summary": holdings_summary},
                chat_history,
            )

        answer = result["answer"]
        is_blocked = result.get("is_blocked", False)
        save_chat(user_id, user_input, answer, is_blocked)

        st.session_state["chat_messages"].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant", avatar="🤖"):
            st.write(answer)


def main():
    init_session()
    page = render_sidebar()

    nav_override = st.session_state.pop("nav_page", None)
    if nav_override:
        page = nav_override

    if page == "🏠 首页":
        render_home()
    elif page == "📋 风险测评":
        render_risk_assessment()
    elif page == "💼 持仓管理":
        render_portfolio_manager()
    elif page == "📊 资产配置":
        render_asset_allocation()
    elif page == "🔍 持仓诊断":
        render_portfolio_diagnosis()
    elif page == "📰 市场解读":
        render_market_daily()
    elif page == "💬 智能问答":
        render_ai_chat()


if __name__ == "__main__":
    main()
