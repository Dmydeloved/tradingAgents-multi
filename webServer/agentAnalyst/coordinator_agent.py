import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent
from langchain_core.tools import Tool
from tradingagents.agents.utils.agent_utils import Toolkit
from webServer.agentAnalyst.fundamental_agent_analyst import FundamentalAnalyst
from webServer.agentAnalyst.market_agent_analyst import MarketAnalyst
from webServer.agentAnalyst.news_agent_analyst import NewsAnalyst
from webServer.agentAnalyst.social_media_agent_analyst import SocialMediaAnalyst


class CoordinatorAgent():
    def __init__(self, llm: ChatOpenAI, toolkit: Toolkit):
        self.llm = llm
        self.toolkit = toolkit
        market_analyst = MarketAnalyst(llm, toolkit)
        fundamental_analyst = FundamentalAnalyst(llm, toolkit)
        news_analyst = NewsAnalyst(llm, toolkit)
        social_media_analyst = SocialMediaAnalyst(llm, toolkit)
        self.tools = [
            market_analyst.as_tool(),
            fundamental_analyst.as_tool(),
            news_analyst.as_tool(),
            social_media_analyst.as_tool()
        ]
        custom_prompt = """
        你需要根据用户问题，选择调用工具或直接回答。
        - 如果需要调用工具，必须输出：
          Thought: 你的思考过程
          Action: 工具名称（如 Market Analysis）
          Action Input: 工具所需参数（JSON格式）

        - 如果可以直接回答，必须输出：
          Thought: 你的思考过程
          Final Answer: 你的最终回答（中文）

        严格遵守上述格式，否则无法被解析！
        """
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent="zero-shot-react-description",
            verbose=True,
            handle_parsing_errors=True
            # agent_kwargs={
            #     "system_message": custom_prompt  # 注入自定义提示词
            # }
        )

    @staticmethod
    def build_coordinator_agent(llm, toolkit):
        # 初始化各个子Agent
        market_agent = MarketAnalyst(llm, toolkit)
        # fundamental_agent = FundamentalAnalyst(llm, toolkit)
        # news_agent = NewsAnalyst(llm, toolkit)
        # social_media_agent = SocialMediaAnalyst(llm, toolkit)



        # 把每个子Agent封装成一个Tool
        tools = [

            # Tool(
            #     name="Market Analysis",
            #     func=lambda state: market_agent.run(state),
            #     description=(
            #         "该工具用于对指定股票进行市场趋势与技术指标的分析，生成详细的市场分析报告。\n\n"
            #         "【功能说明】\n"
            #         "自动调用市场分析师节点，对输入的股票代码和日期进行行情数据抓取、指标计算（如MA、MACD、RSI、布林带等），"
            #         "并结合历史走势与交易量变化生成技术面分析结论与投资建议。\n\n"
            #         "【入参说明（AnalysisInput）】\n"
            #         "- state: Dict[str, Any]\n"
            #         "  包含分析上下文信息的字典，常见字段如下：\n"
            #         "  • trade_date (str)：分析日期，例如 '2025-10-01'\n"
            #         "  • company_of_interest (str)：待分析的股票代码，例如 'AAPL' 或 '600519.SS'\n"
            #         "  • messages (List[Message])：对话历史，用于上下文理解\n\n"
            #         "【返回结果】\n"
            #         "返回一个字典对象，包含：\n"
            #         "  • messages (List)：模型与工具交互的完整消息序列（包括工具调用、回复、结果）\n"
            #         "  • market_report (str)：最终生成的中文市场分析报告，内容包括：\n"
            #         "      - 📊 股票基本信息\n"
            #         "      - 📈 技术指标分析\n"
            #         "      - 📉 价格趋势分析\n"
            #         "      - 💭 投资建议（买入/持有/卖出）\n\n"
            #         "【典型输出示例】\n"
            #         "{\n"
            #         "  'messages': [...],\n"
            #         "  'market_report': '## 📊 股票基本信息...\\n## 📈 技术指标分析...\\n## 💭 投资建议: 持有'\n"
            #         "}"
            #     )
            # ),
            # Tool(
            #     name="Fundamental Analysis",
            #     func=lambda input: fundamental_agent.run(input),
            #     args_schema=AnalysisInput,
            #     description="分析公司基本面、财务状况"
            # ),
            # Tool(
            #     name="News Analysis",
            #     func=lambda input: news_agent.run(input),
            #     args_schema=AnalysisInput,
            #     description="分析新闻情绪和事件影响"
            # ),
            # Tool(
            #     name="Social Media Analysis",
            #     func=lambda input: social_media_agent.run(input),
            #     args_schema=AnalysisInput,
            #     description="分析社交媒体舆论情绪"
            # ),
        ]

        # 创建协调Agent
        coordinator_agent = initialize_agent(
            tools=tools,
            llm=llm,
            agent="chat-zero-shot-react-description",
            verbose=True
        )

        return coordinator_agent

    def run(self, state):
        return self.agent.run(state)
        # coordinator_agent = self.build_coordinator_agent(self.llm, self.toolkit)

        # 调用 agent
        # result = coordinator_agent.invoke({"input": state})
        #
        # return result