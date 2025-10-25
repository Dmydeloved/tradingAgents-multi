import datetime

from langchain_openai import ChatOpenAI

from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.utils.agent_utils import Toolkit

def market_agent(state):
    llm = ChatOpenAI(
        model="deepseek-chat",  # 你要用的 DeepSeek 模型
        api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 直接写死 key
        base_url="https://api.deepseek.com/v1"  # DeepSeek API 地址
    )
    toolkit = Toolkit()
    market_node = create_market_analyst(llm, toolkit)


    result = market_node(state)
    print("=== 返回结果 ===")
    print(result["market_report"])
    return result