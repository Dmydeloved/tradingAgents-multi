from langchain_core.tools import Tool
from langgraph.graph import END, START
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents.analysts.fundamentals_analyst import create_fundamentals_analyst, \
    create_multi_fundamentals_analyst
from tradingagents.agents.utils.agent_utils import Toolkit, create_msg_delete
from langchain_openai import ChatOpenAI

from webServer.tools.analyst_format_tools import parse_state
from webServer.tools.fundamental_tools import should_continue_fundamentals, create_initial_state, \
    create_initial_multi_state
from webServer.utils.Agentstate import AgentState, MultiAgentState


class FundamentalAnalyst:
    def __init__(self, llm: ChatOpenAI, toolkit: Toolkit):
        self.llm = llm
        self.toolkit = toolkit

    def run(self, state: dict):
        fundamental_node = create_fundamentals_analyst(self.llm, self.toolkit)
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
        delete_nodes = create_msg_delete()

        # 构建 ToolNode，注册你需要的工具
        tool_node = ToolNode(
            [
                self.toolkit.get_stock_fundamentals_unified,
                self.toolkit.get_finnhub_company_insider_sentiment,
                self.toolkit.get_finnhub_company_insider_transactions,
                self.toolkit.get_simfin_balance_sheet,
                self.toolkit.get_simfin_cashflow,
                self.toolkit.get_simfin_income_stmt,
            ]
        )


        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("Fundamentals Analyst", fundamental_node)
        workflow.add_node("Msg Clear Fundamental", delete_nodes)
        workflow.add_node("tools_fundamentals", tool_node)

        workflow.add_edge(START, "Fundamentals Analyst")

        # Add conditional edges for current analyst
        workflow.add_conditional_edges(
            "Fundamentals Analyst",
            should_continue_fundamentals,
            ["tools_fundamentals", END],
        )
        workflow.add_edge("tools_fundamentals", "Fundamentals Analyst")

        init_agent_state = create_initial_state(
            state["company_of_interest"], state["trade_date"]
        )

        args = {
            "stream_mode": "values",
            "config": {"recursion_limit": 100},
        }

        final_result = workflow.compile().invoke(init_agent_state, **args)
        return final_result.get("fundamentals_report","")

    def as_tool(self):
        return Tool(
            name="fundamental_analyst",
            func = lambda state:self.run(state),
            description=(
                "该工具根据股票代码和日期进行基本面分析，返回详细的中文分析报告（含投资建议）\n\n"
                "【入参说明（state）】\n"
                "- state: Dict[str, Any]\n"
                "  包含分析上下文信息的字典，常见字段如下：\n"
                "  • trade_date (str)：分析日期，例如 '2025-10-01'\n"
                "  • company_of_interest (str)：待分析的股票代码，例如 'AAPL' 或 '600519.SS'\n"
                "  • messages (List[Message])：对话历史，用于上下文理解\n\n"
                "【返回结果】\n"
                "返回一个字典对象，包含：\n"
                "fundamentals_report (str)：最终生成的中文市场分析报告，内容包括：\n"
            )
        )

class MultiFundamentalAnalyst:
    def __init__(self, llm: ChatOpenAI, toolkit: Toolkit):
        self.llm = llm
        self.toolkit = toolkit

    def run(self, state: dict):
        multi_fundamental_node = create_multi_fundamentals_analyst(self.llm, self.toolkit)
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
        delete_nodes = create_msg_delete()

        # 构建 ToolNode，注册你需要的工具
        tool_node = ToolNode(
            [
                self.toolkit.get_stock_fundamentals_unified,
                self.toolkit.get_finnhub_company_insider_sentiment,
                self.toolkit.get_finnhub_company_insider_transactions,
                self.toolkit.get_simfin_balance_sheet,
                self.toolkit.get_simfin_cashflow,
                self.toolkit.get_simfin_income_stmt,
            ]
        )


        workflow = StateGraph(MultiAgentState)

        # 添加节点
        workflow.add_node("Fundamentals Analyst", multi_fundamental_node)
        workflow.add_node("Msg Clear Fundamental", delete_nodes)
        workflow.add_node("tools_fundamentals", tool_node)

        workflow.add_edge(START, "Fundamentals Analyst")

        # Add conditional edges for current analyst
        workflow.add_conditional_edges(
            "Fundamentals Analyst",
            should_continue_fundamentals,
            ["tools_fundamentals", END],
        )
        workflow.add_edge("tools_fundamentals", "Fundamentals Analyst")

        init_agent_state = create_initial_multi_state(
            state["company_of_interest"], state["trade_date"]
        )

        args = {
            "stream_mode": "values",
            "config": {"recursion_limit": 100},
        }

        final_result = workflow.compile().invoke(init_agent_state, **args)
        return final_result.get("fundamentals_report","")

    def as_tool(self):
        return Tool(
            name="multi_fundamental_analyst",
            func = lambda state:self.run(state),
            description=(
                "该工具根据股票代码和日期进行基本面分析，返回详细的中文分析报告（含投资建议）\n\n"
                "【入参说明（state）】\n"
                "- state: Dict[str, Any]\n"
                "  包含分析上下文信息的字典，常见字段如下：\n"
                "  • trade_date (str)：分析日期，例如 '2025-10-01'\n"
                "  • company_of_interest (list)：待分析的股票代码列表，例如 ['AAPL', '600519.SS']，支持同时传入多只股票代码进行批量分析\n"
                "  • messages (List[Message])：对话历史，用于上下文理解\n\n"
                "【返回结果】\n"
                "返回一个字典对象，包含：\n"
                "fundamentals_report (str)：最终生成的中文市场分析报告，内容包括：\n"
            )
        )