from langchain_openai import ChatOpenAI

from tradingagents.agents.utils.agent_utils import Toolkit
from webServer.agentAnalyst.social_media_agent_analyst import SocialMediaAnalyst


def get_social_media_report(state:dict):
    llm = ChatOpenAI(
        model="deepseek-chat",  # DeepSeek 模型
        api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 测试用 key
        base_url="https://api.deepseek.com/v1",
    )
    toolkit = Toolkit()
    social_media_agent = SocialMediaAnalyst(llm, toolkit)
    social_media_result = social_media_agent.run(state)
    return social_media_result