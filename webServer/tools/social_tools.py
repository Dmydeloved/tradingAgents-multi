from webServer.utils.Agentstate import AgentState
from langgraph.graph import END

def should_continue_social(state: AgentState):
    """Determine if social media analysis should continue."""
    messages = state["messages"]
    last_message = messages[-1]

    # 只有AIMessage才有tool_calls属性
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools_social"
    return END