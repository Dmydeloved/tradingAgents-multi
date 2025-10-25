from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.utils.agent_utils import Toolkit
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool
from webServer.tools.analyst_format_tools import parse_state, safe_get


class MarketAnalyst:
    def __init__(self, llm: ChatOpenAI, toolkit: Toolkit):
        self.llm = llm
        self.toolkit = toolkit

    def run(self,state:dict):
        market_agent_analyst = create_market_analyst(self.llm,self.toolkit)
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
        market_report = market_agent_analyst(state)

        return market_report.get("market_report","")

    def as_tool(self):
        return Tool(
            name="market_analyst",
            func = lambda state:self.run(state),
            description=(
                "该工具用于对指定股票进行市场趋势与技术指标的分析，生成详细的市场分析报告。\n\n"
                "【功能说明】\n"
                "自动调用市场分析师节点，对输入的股票代码和日期进行行情数据抓取、指标计算（如MA、MACD、RSI、布林带等），"
                "并结合历史走势与交易量变化生成技术面分析结论与投资建议。\n\n"
                "【入参说明（state）】\n"
                "- state: Dict[str, Any]\n"
                "  包含分析上下文信息的字典，常见字段如下：\n"
                "  • trade_date (str)：分析日期，例如 '2025-10-01'\n"
                "  • company_of_interest (str)：待分析的股票代码，例如 'AAPL' 或 '600519.SS'\n"
                "  • messages (List[Message])：对话历史，用于上下文理解\n\n"
                "【返回结果】\n"
                "返回一个字典对象，包含：\n"
                "market_report (str)：最终生成的中文市场分析报告，内容包括：\n"
            )
        )