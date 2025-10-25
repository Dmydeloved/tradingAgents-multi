# -------------------
# 控制逻辑
# -------------------
from typing import Dict, Any

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