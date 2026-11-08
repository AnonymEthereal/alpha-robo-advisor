import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
DB_PATH = os.path.join(BASE_DIR, "alpha_advisor.db")

RISK_FREE_RATE = 0.015
TRADING_DAYS = 252

RISK_CONSTRAINTS = {
    1: {"equity_max": 0.10, "gold_max": 0.05, "bond_min": 0.50, "cash_min": 0.20, "target_vol": 0.03},
    2: {"equity_max": 0.30, "gold_max": 0.10, "bond_min": 0.40, "cash_min": 0.15, "target_vol": 0.05},
    3: {"equity_max": 0.60, "gold_max": 0.15, "bond_min": 0.25, "cash_min": 0.10, "target_vol": 0.08},
    4: {"equity_max": 0.80, "gold_max": 0.15, "bond_min": 0.10, "cash_min": 0.05, "target_vol": 0.12},
    5: {"equity_max": 0.95, "gold_max": 0.20, "bond_min": 0.00, "cash_min": 0.00, "target_vol": 0.16},
}

RISK_LEVEL_MAP = [
    {"max": 22, "level": 1, "label": "保守型", "desc": "建议以货币基金和债券为主，权益类不超过10%"},
    {"max": 34, "level": 2, "label": "稳健型", "desc": "建议债券打底，少量配置权益类资产"},
    {"max": 46, "level": 3, "label": "平衡型", "desc": "建议均衡配置股债金，权益类不超过60%"},
    {"max": 58, "level": 4, "label": "成长型", "desc": "建议权益类为主，辅以债券和黄金"},
    {"max": 70, "level": 5, "label": "进取型", "desc": "可高配权益类和黄金，追求长期增值"},
]

RISK_QUESTIONS = [
    {"id": 1, "dim": "experience", "text": "您的投资经验如何？", "options": [
        {"text": "从未投资过", "score": 1}, {"text": "偶尔购买银行理财或货币基金", "score": 3},
        {"text": "有基金/股票投资经验，超过1年", "score": 5}, {"text": "长期投资，熟悉多种金融工具", "score": 7}]},
    {"id": 2, "dim": "experience", "text": "您目前主要持有哪类投资产品？", "options": [
        {"text": "只有银行存款", "score": 1}, {"text": "货币基金/银行理财", "score": 3},
        {"text": "基金（股票型/混合型）", "score": 5}, {"text": "股票+基金+其他金融工具", "score": 7}]},
    {"id": 3, "dim": "loss", "text": "如果您的投资在一个月内亏损20%，您会？", "options": [
        {"text": "立即全部卖出，不再投资", "score": 1}, {"text": "部分卖出，减少损失", "score": 3},
        {"text": "持有不动，等待回本", "score": 5}, {"text": "逢低加仓，摊薄成本", "score": 7}]},
    {"id": 4, "dim": "loss", "text": "您能接受的最大年度亏损幅度是？", "options": [
        {"text": "不能接受任何亏损", "score": 1}, {"text": "5%以内", "score": 3},
        {"text": "10%-20%", "score": 5}, {"text": "20%以上也能接受", "score": 7}]},
    {"id": 5, "dim": "period", "text": "您期望的投资期限是？", "options": [
        {"text": "3个月以内", "score": 1}, {"text": "3-12个月", "score": 3},
        {"text": "1-3年", "score": 5}, {"text": "3年以上", "score": 7}]},
    {"id": 6, "dim": "period", "text": "这笔资金的预期使用时间是？", "options": [
        {"text": "随时可能要用", "score": 1}, {"text": "6个月内要用", "score": 3},
        {"text": "1-2年后用", "score": 5}, {"text": "3年以上才用", "score": 7}]},
    {"id": 7, "dim": "source", "text": "这笔投资资金的主要来源是？", "options": [
        {"text": "日常结余，随时要生活用", "score": 1}, {"text": "工资结余，比较稳定", "score": 3},
        {"text": "年终奖/积蓄，短期不用", "score": 5}, {"text": "长期闲置资金", "score": 7}]},
    {"id": 8, "dim": "source", "text": "您的收入稳定性如何？", "options": [
        {"text": "不稳定，时有时无", "score": 1}, {"text": "基本稳定，但不高", "score": 3},
        {"text": "稳定且逐年增长", "score": 5}, {"text": "高收入且非常稳定", "score": 7}]},
    {"id": 9, "dim": "cognition", "text": "您对\u201c风险与收益成正比\u201d的理解程度？", "options": [
        {"text": "不太理解，觉得风险大的也应该能保本", "score": 1}, {"text": "听说过，但不太确定含义", "score": 3},
        {"text": "理解，愿意承担一定风险换取更高收益", "score": 5}, {"text": "深刻理解，能主动管理风险", "score": 7}]},
    {"id": 10, "dim": "cognition", "text": "您如何看待投资亏损？", "options": [
        {"text": "无法接受，投资就不该亏钱", "score": 1}, {"text": "可以理解，但会焦虑不安", "score": 3},
        {"text": "正常现象，是投资的成本", "score": 5}, {"text": "是机会，亏损时反而加仓", "score": 7}]},
]

DIM_WEIGHTS = {"experience": 0.20, "loss": 0.25, "period": 0.20, "source": 0.15, "cognition": 0.20}

ASSET_CATEGORIES = ["货币基金", "债券型基金", "宽基指数基金", "黄金ETF"]

MARKET_EQUILIBRIUM_WEIGHTS = [0.15, 0.35, 0.40, 0.10]
RISK_AVERSION = 2.5
BL_TAU = 0.05

FUND_POOL = {
    "货币基金": [
        {"code": "003171", "name": "兴全货币A", "type": "货币型"},
        {"code": "004137", "name": "博时合惠B", "type": "货币型"},
        {"code": "000198", "name": "嘉实货币A", "type": "货币型"},
    ],
    "债券型基金": [
        {"code": "003838", "name": "博时安怡18个月定开债", "type": "债券型"},
        {"code": "519152", "name": "浦银安盛普丰纯债A", "type": "债券型"},
        {"code": "006327", "name": "中欧纯债添益A", "type": "债券型"},
    ],
    "宽基指数基金": [
        {"code": "110020", "name": "易方达沪深300ETF联接A", "type": "指数型"},
        {"code": "161017", "name": "富国中证500指数", "type": "指数型"},
        {"code": "001592", "name": "天弘创业板ETF联接A", "type": "指数型"},
    ],
    "黄金ETF": [
        {"code": "000216", "name": "华安黄金易ETF联接A", "type": "黄金型"},
        {"code": "002610", "name": "博时黄金ETF联接C", "type": "黄金型"},
    ],
}

COMPLIANCE_KEYWORDS = {
    "stock_advice": ["买入", "卖出", "加仓", "减仓", "抄底", "清仓", "满仓"],
    "return_promise": ["保本", "稳赚", "一定涨", "零风险", "包赚", "稳赢"],
    "point_prediction": ["会涨到", "会跌到", "点位预测", "目标价"],
    "insider": ["内幕", "消息面", "主力动向", "庄家"],
}

LLM_CONFIG = {
    "model": os.environ.get("LLM_MODEL", "qwen-plus"),
    "api_key": os.environ.get("LLM_API_KEY", ""),
    "base_url": os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "temperature": 0.7,
    "max_tokens": 1500,
}

DISCLAIMER = "投资有风险，入市需谨慎。以上数据基于历史回测，不代表未来实际收益。"

INDICES = {
    "sh000001": {"name": "上证综指", "symbol": "sh000001"},
    "sz399001": {"name": "深证成指", "symbol": "sz399001"},
    "sh000300": {"name": "沪深300", "symbol": "sh000300"},
    "sz399006": {"name": "创业板指", "symbol": "sz399006"},
}
