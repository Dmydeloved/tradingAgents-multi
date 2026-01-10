import os
from typing import List

from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage, HumanMessage

from webServer.tools.data_tools import agent_tools

# ====================== 大模型初始化 ======================
llm = ChatOpenAI(
    model="deepseek-chat",  # 你要用的 DeepSeek 模型
    api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 直接写死 key
    base_url="https://api.deepseek.com/v1"  # DeepSeek API 地址
)


# ====================== Prompt模板（核心逻辑）======================
# 行业分析Agent Prompt
INDUSTRY_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content="""
你是专业的股票行业分析师，负责对股票所属行业进行深度分析。工作流程如下：
1. 首先调用stock_industry_query工具，根据输入的股票列表获取每只股票的所属行业；
2. 对相同行业的股票进行分组，避免重复分析；
3. 针对每个行业，调用industry_data_query工具获取行业数据（需先确认行业代码，申万一级行业代码参考：如食品饮料801120、医药生物801150）；
4. 基于行业数据，从以下维度进行分析：
   - 行业景气度：营收/利润增速趋势，是否处于上升周期；
   - 估值合理性：当前PE/PB分位（与历史3年对比），是否高估/低估；
   - 政策环境：政策支持力度或限制因素；
   - 竞争格局：行业集中度、龙头企业优势；
   - 风险提示：行业面临的主要风险（如产能过剩、政策变化）。
5. 输出格式要求（Markdown）：
# 行业分析报告（股票列表：{stock_list_str}）
## 一、行业分布
- 股票代码1：行业名称
- 股票代码2：行业名称
...
## 二、各行业分析
### （行业名称1）
1. 景气度分析：xxx
2. 估值分析：xxx
3. 政策影响：xxx
4. 竞争格局：xxx
5. 风险提示：xxx
### （行业名称2）
...
## 三、总结建议
基于行业分析，对输入股票的行业层面投资价值排序及建议：xxx
"""),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    HumanMessage(content="{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

# 宏观分析Agent Prompt
MACRO_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessage(content="""
你是专业的宏观经济分析师，负责分析宏观经济对股票的影响。工作流程如下：
1. 首先调用stock_industry_query工具，根据输入的股票列表获取每只股票的所属行业；
2. 识别这些行业对应的核心宏观驱动因子（如地产行业对应利率、消费行业对应CPI、出口企业对应汇率）；
3. 调用macro_data_query工具获取相关宏观指标数据（如利率、CPI、GDP增速等）；
4. 基于宏观数据，从以下维度进行分析：
   - 经济周期定位：当前处于经济周期的哪个阶段，对各行业的影响；
   - 货币政策影响：利率/流动性变化对行业融资成本、估值的影响；
   - 财政政策影响：财政支出方向（如基建、消费）与行业相关性；
   - 通胀影响：CPI/PPI变化对行业盈利的影响（如上游行业受益于PPI上涨）；
   - 宏观风险：系统性风险（如经济衰退、汇率波动）对行业的冲击。
5. 输出格式要求（Markdown）：
# 宏观分析报告（股票列表：{stock_list_str}）
## 一、股票所属行业及核心宏观因子
- 股票代码1（行业名称）：核心宏观因子（如利率、CPI）
- 股票代码2（行业名称）：核心宏观因子（如GDP、汇率）
...
## 二、宏观经济数据概览
### （核心指标1）
- 数据趋势：xxx
- 当前水平：xxx（与历史分位对比）
### （核心指标2）
...
## 三、宏观对各行业的影响分析
### （行业名称1）
1. 经济周期影响：xxx
2. 货币政策影响：xxx
3. 通胀影响：xxx
4. 潜在风险：xxx
### （行业名称2）
...
## 四、投资建议
基于宏观分析，对输入股票的宏观层面投资价值判断及建议：xxx
"""),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    HumanMessage(content="{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])


# ====================== Agent初始化 ======================
class StockAnalysisAgents:
    def __init__(self, llm, tools):
        self.llm = llm
        self.tools = tools
        self.industry_agent = self._init_industry_agent()
        self.macro_agent = self._init_macro_agent()

    def _init_industry_agent(self) -> AgentExecutor:
        """初始化行业分析Agent"""
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=INDUSTRY_AGENT_PROMPT
        )
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True, handle_parsing_errors="返回'解析错误，请重试'")

    def _init_macro_agent(self) -> AgentExecutor:
        """初始化宏观分析Agent"""
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=MACRO_AGENT_PROMPT
        )
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True, handle_parsing_errors="返回'解析错误，请重试'")

    def run_industry_analysis(self, stock_list: List[str]) -> str:
        """
        运行行业分析（支持多股票）
        :param stock_list: 股票代码列表
        :return: 结构化分析报告（Markdown）
        """
        stock_list_str = ", ".join(stock_list)
        input_msg = f"请分析以下股票的行业情况：{stock_list_str}"
        # 填充prompt中的stock_list_str变量
        formatted_prompt = INDUSTRY_AGENT_PROMPT.format(
            input=input_msg,
            stock_list_str=stock_list_str,
            chat_history=[],
            agent_scratchpad=[]
        )
        # 运行Agent
        result = self.industry_agent.invoke({
            "input": input_msg,
            "stock_list_str": stock_list_str
        })
        return result["output"]

    def run_macro_analysis(self, stock_list: List[str]) -> str:
        """
        运行宏观分析（支持多股票）
        :param stock_list: 股票代码列表
        :return: 结构化分析报告（Markdown）
        """
        stock_list_str = ", ".join(stock_list)
        input_msg = f"请分析宏观经济对以下股票的影响：{stock_list_str}"
        result = self.macro_agent.invoke({
            "input": input_msg,
            "stock_list_str": stock_list_str
        })
        return result["output"]

    def run_combined_analysis(self, stock_list: List[str]) -> str:
        """
        组合分析（行业+宏观）
        :return: 综合分析报告
        """
        industry_report = self.run_industry_analysis(stock_list)
        macro_report = self.run_macro_analysis(stock_list)
        # 合并报告
        combined_report = f"""
# 股票综合分析报告（行业+宏观）
## 股票列表：{', '.join(stock_list)}

---
## 第一部分：行业分析
{industry_report.replace('# 行业分析报告（股票列表：xxx）', '').strip()}

---
## 第二部分：宏观分析
{macro_report.replace('# 宏观分析报告（股票列表：xxx）', '').strip()}

---
## 综合投资建议
基于行业景气度和宏观经济环境，对股票的综合投资评级（高/中/低）及操作建议：
1. 股票代码1：评级 → 建议（如：逢低买入/观望/减持）
2. 股票代码2：评级 → 建议
...
（注：综合评级需结合行业增长潜力、估值合理性、宏观政策支持力度及潜在风险）
"""
        return combined_report


# ====================== 实例化与使用 ======================
if __name__ == "__main__":
    # 初始化Agent
    analysis_agents = StockAnalysisAgents(llm=llm, tools=agent_tools)

    # 测试股票列表（A股+港股）
    test_stocks = ["600519.SH", "000858.SZ", "00700.HK"]  # 贵州茅台、五粮液、腾讯控股

    # 1. 运行行业分析
    industry_report = analysis_agents.run_industry_analysis(test_stocks)
    print("=" * 50 + " 行业分析报告 " + "=" * 50)
    print(industry_report)

    # 2. 运行宏观分析
    macro_report = analysis_agents.run_macro_analysis(test_stocks)
    print("\n" + "=" * 50 + " 宏观分析报告 " + "=" * 50)
    print(macro_report)

    # 3. 运行综合分析
    combined_report = analysis_agents.run_combined_analysis(test_stocks)
    print("\n" + "=" * 50 + " 综合分析报告 " + "=" * 50)
    print(combined_report)