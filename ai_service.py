import json
import logging
import re
from typing import Optional

from config import LLM_CONFIG, COMPLIANCE_KEYWORDS, DISCLAIMER, RISK_LEVEL_MAP

logger = logging.getLogger(__name__)


def _call_llm(prompt: str, system_prompt: str = "", question: str = "") -> str:
    api_key = LLM_CONFIG.get("api_key", "")
    if not api_key or not api_key.startswith("sk-"):
        return _fallback_response(question or prompt)

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=LLM_CONFIG.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=LLM_CONFIG.get("model", "qwen-plus"),
            messages=messages,
            temperature=LLM_CONFIG.get("temperature", 0.7),
            max_tokens=LLM_CONFIG.get("max_tokens", 1500),
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"LLM 调用失败: {e}")
        return _fallback_response(question or prompt)


def _fallback_response(question: str) -> str:
    q = question
    if "资产配置" in q or "怎么配置" in q or "配置方案" in q:
        return (
            "资产配置就是把钱分到不同类型的资产里，降低风险、稳定收益。"
            "简单来说就是\"不把鸡蛋放在一个篮子里\"。"
            "一般来说，风险承受能力越低，债券和货币基金的比例就越高；"
            "风险承受能力越高，股票型基金的比例可以越高。"
            "你可以使用系统的「资产配置」功能，输入金额和期限就能得到个性化方案。\n\n"
            f"{DISCLAIMER}"
        )
    if "持仓诊断" in q or "调仓" in q or "我的持仓" in q:
        return (
            "持仓诊断就是帮你检查当前的投资组合是否健康。"
            "主要看四个方面：赚的钱够不够承担风险（收益风险比）、"
            "有没有分散到不同资产（分散度）、会不会太集中在某个行业（集中度）、"
            "风格是不是太偏科（风格暴露）。"
            "你可以使用系统的「持仓诊断」功能，上传持仓就能得到详细评分。\n\n"
            f"{DISCLAIMER}"
        )
    if "市场" in q and ("解读" in q or "行情" in q or "怎么样" in q):
        return (
            "市场短期涨跌很难预测，但长期来看会反映经济基本面。"
            "建议不要因为一两天的涨跌就频繁操作，"
            "保持长期投资心态，做好资产配置才是关键。"
            "你可以使用系统的「市场解读」功能，每天查看市场动态。\n\n"
            f"{DISCLAIMER}"
        )
    if "指数基金" in q:
        return (
            "指数基金就是\"打包买一篮子股票\"的基金。"
            "比如沪深300指数基金，相当于你一次性买了"
            "沪深两市最大的300家公司的一小部分。"
            "好处是费用低、不用自己选股，跟着大盘走。"
            "适合长期定投，是普通投资者的好选择。\n\n"
            f"{DISCLAIMER}"
        )
    if "夏普比率" in q:
        return (
            "夏普比率就是衡量\"冒一份险能赚多少钱\"的指标。"
            "简单说，就是每承担一单位风险，能获得多少超额收益。"
            "夏普比率越高越好，说明同样风险下收益更高，"
            "或者同样收益下风险更低。一般大于1就算不错了。\n\n"
            f"{DISCLAIMER}"
        )
    if "基金" in q and ("选择" in q or "怎么选" in q or "推荐" in q):
        return (
            "选基金不能只看收益率，要综合考虑几个方面："
            "第一是基金类型是否符合你的风险承受能力；"
            "第二是基金经理的长期业绩是否稳定；"
            "第三是费率高低，长期来看费用影响很大；"
            "第四是基金规模，太大太小都不太好。"
            "建议先做风险测评，再根据配置方案选择对应类型的基金。\n\n"
            f"{DISCLAIMER}"
        )
    if "风险" in q:
        return (
            "投资风险就是可能亏钱的可能性。"
            "风险和收益是一对好兄弟——想赚更多就要承担更多风险。"
            "降低风险的方法主要有：分散投资（不集中在一个地方）、"
            "长期持有（时间消化波动）、定期定投（摊平成本）。\n\n"
            f"{DISCLAIMER}"
        )
    if "定投" in q:
        return (
            "定投就是定期定额买入基金，比如每个月固定买1000元。"
            "好处是不用判断时机，跌的时候买的份额多，"
            "涨的时候买的份额少，长期下来成本比较平均。"
            "适合没时间盯盘的上班族，坚持3年以上效果更好。\n\n"
            f"{DISCLAIMER}"
        )
    return (
        "这是一个很好的投资问题。由于 AI 服务当前不可用，"
        "建议你尝试使用系统的核心功能："
        "「风险测评」了解自己的风险承受能力、"
        "「资产配置」获取个性化方案、"
        "「持仓诊断」检查当前持仓健康度。"
        "投资有风险，入市需谨慎，保持学习心态很重要。\n\n"
        f"{DISCLAIMER}"
    )


def compliance_check(text: str, check_type: str = "input") -> dict:
    matched_rules = []

    for rule_name, keywords in COMPLIANCE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched_rules.append(rule_name)
                break

    if check_type == "input":
        import re as _re
        stock_pattern = _re.search(r"[0-9]{6}", text)
        stock_advice_words = COMPLIANCE_KEYWORDS.get("stock_advice", [])
        if stock_pattern and any(w in text for w in stock_advice_words):
            if "stock_advice" not in matched_rules:
                matched_rules.append("stock_advice")

    if matched_rules:
        return {
            "passed": False,
            "matched_rules": matched_rules,
            "suggestion": "抱歉，根据合规要求，我无法回答此类问题。我可以帮你了解投资基础知识、资产配置方案或持仓诊断。"
        }
    return {"passed": True, "matched_rules": [], "suggestion": ""}


def generate_interpretation(quant_result: dict, context: dict, task_type: str) -> str:
    risk_level = context.get("risk_level", 3)
    level_info = RISK_LEVEL_MAP[risk_level - 1] if 1 <= risk_level <= 5 else RISK_LEVEL_MAP[2]
    risk_label = level_info["label"]

    if task_type == "allocation":
        prompt = f"""请根据以下资产配置结果，用通俗易懂的语言生成方案解读。

风险等级：{risk_label}
投资金额：{context.get("amount", 0)} 元
投资期限：{context.get("period", 12)} 个月
配置方案：{json.dumps(quant_result.get("weights", {}), ensure_ascii=False)}
预期年化收益率：{quant_result.get("expected_return", 0)*100:.1f}%
预期收益金额：{quant_result.get("expected_return_amount", 0):.0f} 元
最大回撤：{quant_result.get("max_drawdown", 0)*100:.1f}%
最大可能亏损：{quant_result.get("max_loss_amount", 0):.0f} 元
夏普比率：{quant_result.get("sharpe", 0)}

请按以下要点撰写（300字以内）：
1. 用3-5句话解释"为什么这么配"，将每类资产用生活化比喻说明其角色
2. 说明"可能赚多少/亏多少"，用具体金额而非百分比表达
3. 给出持有期限内的注意事项
4. 末尾附带免责声明

语气：温和、专业、像朋友聊天。不出现"保本""稳赚"等承诺性表述。"""
        system = "你是一位擅长用大白话解释金融配置的智能投顾。"

    elif task_type == "diagnosis":
        prompt = f"""请根据以下持仓诊断结果，生成通俗化的调仓建议。

诊断评分：{quant_result.get("total_score", 0)}/100
评级：{quant_result.get("rating", "")}
风险点：{json.dumps(quant_result.get("risk_points", []), ensure_ascii=False)}
调仓建议动作：{json.dumps(quant_result.get("advice_actions", []), ensure_ascii=False)}
分项得分：{json.dumps(quant_result.get("dimensions", {}), ensure_ascii=False)}

请用通俗语言解释评分含义，说明调仓逻辑，避免堆砌专业术语。200字以内。
末尾附带免责声明。"""
        system = "你是一位擅长用大白话解释持仓风险的智能投顾。"

    else:
        prompt = ""
        system = ""

    if not prompt:
        return DISCLAIMER

    response = _call_llm(prompt, system, task_type)

    if DISCLAIMER not in response:
        response += f"\n\n{DISCLAIMER}"

    output_check = compliance_check(response, "output")
    if not output_check["passed"]:
        logger.warning(f"AI 输出合规拦截: {output_check['matched_rules']}")
        response = _fallback_response(task_type)

    return response


def generate_market_summary(market_data: dict, events: list, user_holdings: list) -> str:
    market_desc = "\n".join(
        f"- {info['name']}：收盘 {info['close']:.2f}，涨跌幅 {info['change_pct']:+.2f}%"
        for info in market_data.values()
    )
    event_desc = "\n".join(f"- {e.get('title', '')}：{e.get('value', '')}" for e in events)
    holdings_desc = "\n".join(f"- {h['fund_name']}（{h['fund_type']}）：{h['amount']}元" for h in user_holdings) if user_holdings else "暂无持仓"

    prompt = f"""请生成今日市场解读。

日期：今日
市场数据：
{market_desc}

宏观事件：
{event_desc}

用户持仓：
{holdings_desc}

请按以下要点撰写（300字以内）：
1. 用一句话概括当日市场情绪
2. 列出2-3个核心事件并各附一句话解读
3. 关联用户持仓说明影响
4. 明日关注提示

客观中立，不做情绪化解读，不预测短期点位。末尾附带免责声明。"""

    response = _call_llm(prompt, "你是一位客观中立的市场复盘编辑。", "市场解读")
    if DISCLAIMER not in response:
        response += f"\n\n{DISCLAIMER}"
    return response


def chat_answer(question: str, user_context: dict, chat_history: list) -> dict:
    input_check = compliance_check(question, "input")
    if not input_check["passed"]:
        block_reply = input_check["suggestion"] + f"\n\n{DISCLAIMER}"
        return {"answer": block_reply, "is_blocked": True, "block_reason": input_check["matched_rules"]}

    risk_level = user_context.get("risk_level")
    level_label = "未测评"
    if risk_level and 1 <= risk_level <= 5:
        level_label = RISK_LEVEL_MAP[risk_level - 1]["label"]

    holdings = user_context.get("holdings_summary", "暂无持仓")

    history_text = ""
    if chat_history:
        recent = chat_history[-5:]
        history_text = "\n".join(
            f"用户：{h['question']}\n助手：{h['answer'][:100]}..." for h in recent
        )

    prompt = f"""用户问题：{question}

当前对话历史：
{history_text}

用户风险等级：{level_label}
用户持仓摘要：{holdings}

请回答用户问题。用日常语言，避免堆砌专业术语。需要使用术语时附带一句话解释。语气温和专业。
不推荐具体个股，不承诺收益，不预测点位。
末尾附带免责声明。"""

    system = """你是阿尔法智投的AI投顾助手，擅长用通俗易懂的语言解答投资问题。
你可以回答：投资基础知识、基金产品规则、资产配置逻辑、市场现象解读。
禁止行为：不推荐具体个股买卖，不承诺收益，不预测具体点位，不提供内幕信息。"""

    response = _call_llm(prompt, system, question)

    output_check = compliance_check(response, "output")
    if not output_check["passed"]:
        response = f"根据合规要求，我无法提供此类建议。建议你了解投资基础知识或使用系统的资产配置功能。\n\n{DISCLAIMER}"
        return {"answer": response, "is_blocked": True, "block_reason": output_check["matched_rules"]}

    if DISCLAIMER not in response:
        response += f"\n\n{DISCLAIMER}"

    return {"answer": response, "is_blocked": False, "block_reason": None}
