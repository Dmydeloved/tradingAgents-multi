from typing import Annotated

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """自定义 Agent 状态，继承自 MessagesState，确保和 langgraph 兼容"""

    company_of_interest: Annotated[str, "目标公司代码或名称"]
    trade_date: Annotated[str, "交易日期"]

    investment_debate_state: Annotated[str, "投资讨论状态"]
    risk_debate_state: Annotated[str, "风险讨论状态"]

    market_report: Annotated[str, "市场分析报告"]
    fundamentals_report: Annotated[str, "基本面分析报告"]
    sentiment_report: Annotated[str, "情绪分析报告"]
    news_report: Annotated[str, "新闻报告"]