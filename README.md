# 阿尔法智投 AI 智能投资顾问系统

> 2026 秋《AI + 工程管理》课程项目 · 团队：阿尔法炼丹房

## 项目简介

阿尔法智投是一款结合金融工程量化能力与 AI 大语言模型的陪伴式普惠智能投顾工具。系统以 Markowitz 均值-方差模型 + Black-Litterman 模型为量化底座，通过 AI 将专业量化结果转化为通俗易懂的投资建议。

## 快速开始

### 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 安装依赖

```bash
cd alpha-robo-advisor
pip install -r requirements.txt
```

### 配置 AI 模型（可选）

系统支持通过环境变量配置 LLM。不配置时自动降级为规则模板回复。

```bash
# 使用通义千问（推荐）
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export LLM_MODEL="qwen-plus"

# 或使用 OpenAI
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"
```

### 启动应用

```bash
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

## 项目结构

```
alpha-robo-advisor/
├── app.py              # Streamlit 前端（6 页面 + 侧边栏导航）
├── config.py           # 全局配置（风险等级、约束条件、题目、标的池、LLM 配置）
├── db.py               # 数据库初始化与 CRUD 操作（SQLite）
├── data_layer.py       # 数据层（AkShare 接口 + 数据清洗 + 缓存）
├── quant_engine.py     # 量化引擎（Markowitz + BL 模型 + 持仓诊断评分）
├── ai_service.py       # AI 服务层（LLM 调用 + 提示词 + 合规校验）
├── requirements.txt
└── README.md
```

## 四层架构

| 层 | 文件 | 职责 |
|---|---|---|
| 数据层 | data_layer.py | 行情数据采集（AkShare）、清洗、缓存（SQLite） |
| 量化引擎层 | quant_engine.py | 组合优化、风险计算、持仓四维度评分 |
| AI 服务层 | ai_service.py | LLM 对接、提示词工程、合规校验 |
| 应用展示层 | app.py | Streamlit 交互界面、结果可视化 |

## 核心功能

1. **风险测评** — 10 题标准化测评，5 维度加权评分，映射 5 档风险等级
2. **持仓管理** — 手动添加/删除基金持仓，自动查询基本信息
3. **资产配置** — Markowitz + BL 模型生成最优配置，AI 通俗化解读
4. **持仓诊断** — 四维度评分（收益风险比/资产分散度/行业集中度/风格暴露）
5. **市场解读** — 每日自动拉取行情，AI 提炼核心观点并关联持仓
6. **智能问答** — 对话式投顾，合规校验拦截违规问题

## 量化模型

- **Markowitz 均值-方差模型**：基于近 500 个交易日历史收益计算协方差矩阵，SLSQP 求解带约束二次优化
- **Black-Litterman 模型**：在均衡收益基础上加入市场观点，贝叶斯修正后验收益
- **约束条件**：5 档风险等级对应不同的权益/黄金/债券/现金上下限
- **有效前沿**：50 个目标收益点生成前沿曲线

## 合规声明

- 不提供具体个股买卖建议
- 不承诺收益、不说"保本""稳赚"
- 不预测具体点位
- 所有回答附带"投资有风险，入市需谨慎"免责声明

## 技术栈

| 技术 | 用途 |
|---|---|
| Streamlit | 前端交互界面 |
| AkShare | 行情数据采集 |
| SQLite | 本地数据存储 |
| SciPy | 组合优化求解 |
| NumPy / Pandas | 数据计算 |
| OpenAI SDK | LLM 调用（兼容通义千问等） |
| Plotly | 可视化图表 |
