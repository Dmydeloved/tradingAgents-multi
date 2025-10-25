from langchain_core.tools import Tool
from webServer.tools.analyst_format_tools import parse_state
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.utils.agent_utils import Toolkit
from langchain_openai import ChatOpenAI


class NewsAnalyst:
    def __init__(self, llm: ChatOpenAI, toolkit: Toolkit):
        self.llm = llm
        self.toolkit = toolkit

    def run(self,state:dict):
        news_agent_analyst = create_news_analyst(self.llm,self.toolkit)
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
        news_report = news_agent_analyst(state)

        return news_report.get("news_report","")

    def as_tool(self):
        return Tool(
            name="news_analyst",
            func = lambda state:self.run(state),
            description=(
                "该工具用于根据股票代码和日期分析相关新闻，评估对股价的影响。\n\n"
                "【入参说明（state）】\n"
                "- state: Dict[str, Any]\n"
                "  包含分析上下文信息的字典，常见字段如下：\n"
                "  • trade_date (str)：分析日期，例如 '2025-10-01'\n"
                "  • company_of_interest (str)：待分析的股票代码，例如 'AAPL' 或 '600519.SS'\n"
                "  • messages (List[Message])：对话历史，用于上下文理解\n\n"
                "【返回结果】\n"
                "返回一个字典对象，包含：\n"
                "news_report (str)：最终生成的中文市场分析报告，内容包括：\n"
            )
        )