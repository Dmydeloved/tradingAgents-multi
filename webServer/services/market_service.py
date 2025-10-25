from langchain_openai import ChatOpenAI

from tradingagents.agents.utils.agent_utils import Toolkit
from webServer.agentAnalyst.market_agent_analyst import MarketAnalyst


def get_report(state:dict):
    llm = ChatOpenAI(
        model="deepseek-chat",  # DeepSeek 模型
        api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 测试用 key
        base_url="https://api.deepseek.com/v1",
    )
    toolkit = Toolkit()
    market_agent = MarketAnalyst(llm, toolkit)
    market_result = market_agent.run(state)
    return market_result