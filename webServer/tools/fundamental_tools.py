# -------------------
# 控制逻辑
# -------------------
from typing import Dict, Any, List

from webServer.utils.Agentstate import AgentState
from langgraph.graph import END

def should_continue_fundamentals(state: AgentState):
    """Determine if fundamentals analysis should continue."""
    messages = state["messages"]
    if not messages:
        return END

    last_message = messages[-1]

    # 只有 AIMessage 才有 tool_calls 属性
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_fundamentals"
    return END


def create_initial_state(company_name: str, trade_date: str) -> Dict[str, Any]:
    return {
        "messages": [("human", company_name)],
        "company_of_interest": company_name,
        "trade_date": str(trade_date),
        "investment_debate_state": "",
        "risk_debate_state": "",
        "market_report": "",
        "fundamentals_report": "",
        "sentiment_report": "",
        "news_report": "",
    }

def create_initial_multi_state(company_list: List[str], trade_date: str) -> Dict[str, Any]:
    """
    创建初始状态，支持多只股票。

    Args:
        company_list: 股票代码或名称列表
        trade_date: 交易日期
    """
    return {
        "messages": [("human", f"分析股票列表: {', '.join(company_list)}")],  # ✅ 人类消息展示股票集合
        "company_of_interest": company_list,  # ✅ 改为列表
        "trade_date": str(trade_date),
        "investment_debate_state": "",
        "risk_debate_state": "",
        "market_report": "",
        "fundamentals_report": "",
        "sentiment_report": "",
        "news_report": "",
    }
