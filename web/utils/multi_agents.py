import datetime
from tabnanny import verbose
from typing import List, Dict

from langchain.agents import initialize_agent
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from tradingagents.agents.utils.agent_utils import Toolkit
from langchain.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
import json
from datetime import datetime

def parse_state(input_data):
    """
    将输入（字符串或字典）解析为 dict，并将 trade_date 转换为 datetime 类型。
    如果解析失败，返回空字符串，并打印错误信息。
    """
    try:
        # 如果是字符串，尝试转为 dict
        if isinstance(input_data, str):
            data = json.loads(input_data)
        elif isinstance(input_data, dict):
            data = input_data.copy()  # 避免修改原始 dict
        else:
            raise TypeError(f"输入必须是 JSON 字符串或 dict，实际类型: {type(input_data)}")

        # 检查 trade_date
        if "trade_date" in data and isinstance(data["trade_date"], str):
            try:
                data["trade_date"] = datetime.strptime(data["trade_date"], "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"trade_date 格式错误: {data['trade_date']} (期望 YYYY-MM-DD)")

        return data

    except Exception as e:
        print(f"⚠️ 解析 state 失败: {e}")
        return ""

def safe_get(result: dict, key: str) -> str:
    """
    安全获取字典中的字段，如果不存在或不是字符串，返回空字符串
    """
    try:
        value = result.get(key, "")
        if not isinstance(value, str):
            return str(value)  # 强制转换为字符串
        return value
    except Exception as e:
        print(f"⚠️ 获取字段 {key} 失败: {e}")
        return ""


llm = ChatOpenAI(
    model="deepseek-chat",  # 你要用的 DeepSeek 模型
    api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 直接写死 key
    base_url="https://api.deepseek.com/v1"  # DeepSeek API 地址
)
toolkit = Toolkit()


def market_agent(state):

    market_node = create_market_analyst(llm, toolkit)

    result = market_node(state)
    print("=== market agent 返回结果 ===")
    print(result["market_report"])
    return result["market_report"]

def social_agent(state):
    social_node = create_social_media_analyst(llm,toolkit)
    result = social_node(state)
    print("=== social agent 返回结果 ===")
    print(result["sentiment_report"])


class MarketAnalystAgent():
    def __init__(self):
        self.llm = llm
        self.toolkit = toolkit

    def run(self, state):
        market_node = create_market_analyst(llm, toolkit)
        # 校验参数
        temp_state = parse_state(state)
        if temp_state == "":
            return ""
        else:
            state = temp_state
        required_keys = ["trade_date", "company_of_interest", "messages"]
        try:
            # 确保输入是字典类型
            if not isinstance(state, dict):
                return "错误：输入不是字典类型"

            # 检查是否包含所有必需的键
            missing_keys = [key for key in required_keys if key not in state]
            if missing_keys:
                return f"错误：字典缺少必需的键：{', '.join(missing_keys)}"
        except Exception as e:
            return f"处理股票字典时出错: {str(e)}"
        result = market_node(state)
        print("=== market agent 返回结果 ===")
        report = safe_get(result,"market_report")
        print(report)
        return report

    def as_tool(self):
        return Tool(
            name="market_analyst",
            func = lambda state: self.run(state),
            description="对指定股票进行市场和技术分析，输出为市场分析报告"
        )

class SocialAnalystAgent():
    def __init__(self):
        self.llm = llm
        self.toolkit = toolkit

    def run(self,state):
        social_node = create_social_media_analyst(self.llm,self.toolkit)
        required_keys = ["trade_date", "company_of_interest", "messages"]
        temp_state = parse_state(state)
        if temp_state == "":
            return ""
        else:
            state = temp_state
        try:
            # 确保输入是字典类型
            if not isinstance(state, dict):
                return "错误：输入不是字典类型"

            # 检查是否包含所有必需的键
            missing_keys = [key for key in required_keys if key not in state]
            if missing_keys:
                return f"错误：字典缺少必需的键：{', '.join(missing_keys)}"
        except Exception as e:
            return f"处理股票字典时出错: {str(e)}"
        result = social_node(state)
        print("=== social agent 返回结果 ===")
        report = safe_get(result,"sentiment_report")
        print(report)
        return report

    def as_tool(self):
        return Tool(
            name="social_analyst",
            func= lambda state: self.run(state),
            description="根据股票代码分析中国社交媒体的投资者情绪，输出详细报告"
        )

class NewsAnalystAgent():
    def __init__(self):
        self.llm = llm
        self.toolkit = toolkit

    def run(self,state):
        news_node = create_news_analyst(self.llm,self.toolkit)
        required_keys = ["trade_date", "company_of_interest", "messages"]
        temp_state = parse_state(state)
        if temp_state == "":
            return ""
        else:
            state = temp_state
        try:
            # 确保输入是字典类型
            if not isinstance(state, dict):
                return "错误：输入不是字典类型"

            # 检查是否包含所有必需的键
            missing_keys = [key for key in required_keys if key not in state]
            if missing_keys:
                return f"错误：字典缺少必需的键：{', '.join(missing_keys)}"
        except Exception as e:
            return f"处理股票字典时出错: {str(e)}"
        result = news_node(state)
        print("=== news analyst 返回结果 ===")
        report = safe_get(result,"news_report")
        print(report)
        return report


    def as_tool(self):
        return Tool(
            name="news_analyst",
            func=lambda state: self.run(state),
            description="根据股票代码和日期分析相关新闻，评估对股价的影响。"
        )

class FundamentalAnalystAgent():
    def __init__(self):
        self.llm = llm
        self.toolkit = toolkit

    def run(self,state):
        fundament_node = create_fundamentals_analyst(self.llm,self.toolkit)
        temp_state = parse_state(state)
        if temp_state == "":
            return ""
        else:
            state = temp_state
        required_keys = ["trade_date", "company_of_interest", "messages"]
        try:
            # 确保输入是字典类型
            if not isinstance(state, dict):
                return "错误：输入不是字典类型"

            # 检查是否包含所有必需的键
            missing_keys = [key for key in required_keys if key not in state]
            if missing_keys:
                return f"错误：字典缺少必需的键：{', '.join(missing_keys)}"
        except Exception as e:
            return f"处理股票字典时出错: {str(e)}"
        result = fundament_node(state)
        print("=== fundamental analyst 返回结果 ===")
        report = safe_get(result,"fundamentals_report")
        print(report)
        return report


    def as_tool(self):
        return Tool(
            name="fundamental_analyst",
            func=lambda state: self.run(state),
            description="根据股票代码和日期进行基本面分析，返回详细的中文分析报告（含投资建议）。"
        )

class CollaborationAgent:
    def __init__(self):
        self.llm = llm
        self.tools = [
            MarketAnalystAgent().as_tool(),
            SocialAnalystAgent().as_tool(),
            NewsAnalystAgent().as_tool(),
            FundamentalAnalystAgent().as_tool()
        ]
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent="zero-shot-react-description",
            verbose=True
        )

    def run(self,message):
        return self.agent.run(message)
# class CollaborationAgent:
#     def __init__(self, llm, toolkit):
#         self.llm = llm
#         self.toolkit = toolkit
#
#         # 这里收集所有可用的子Agent工具
#         self.sub_agents = [
#             MarketAnalystAgent().as_tool(),
#             SocialAnalystAgent().as_tool(),
#             NewsAnalystAgent().as_tool(),
#             FundamentalAnalystAgent().as_tool()
#         ]
#
#         # 提示词：告诉大模型如何调度子Agent
#         self.prompt = ChatPromptTemplate.from_messages(
#             [
#                 ("system", """你是一个协作型投研助理，可以调用以下专家Agent进行分析：
# - market_analyst: 市场技术分析
# - social_analyst: 中国社交媒体情绪分析
# - news_analyst: 新闻及媒体分析
# - fundamental_analyst: 基本面分析
#
# 请根据输入的股票代码和日期，合理调用子Agent工具，并整合它们的输出，写成一份最终综合分析报告（中文，包含投资建议）。"""),
#                 MessagesPlaceholder("messages")
#             ]
#         )
#
#     def run(self, state: dict):
#         # 绑定四个工具
#         chain = self.prompt | self.llm.bind_tools(self.sub_agents)
#
#         # 执行，输入用户消息
#         result = chain.invoke(state.get("messages", []))
#
#         return {
#             "final_report": result.content
#         }

if __name__ == "__main__":
    collab_agent = CollaborationAgent()

    state = {
        "trade_date": "2025-09-19",
        "company_of_interest": "000001",
        "messages": [
            {"role": "user", "content": "请对平安银行做一个全面分析，并给出投资建议。"}
        ]
    }

    result = collab_agent.run(f"{state}")
    print("=== 综合报告 ===")
    print(result["final_report"])
