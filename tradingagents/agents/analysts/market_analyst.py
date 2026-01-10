from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
import time
import json
import traceback

# 导入分析模块日志装饰器
from tradingagents.utils.tool_logging import log_analyst_module

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
from webServer.tools import StockDataFetcher

logger = get_logger("default")

# 导入Google工具调用处理器
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler


def _get_company_name(ticker: str, market_info: dict) -> str:
    """
    根据股票代码获取公司名称

    Args:
        ticker: 股票代码
        market_info: 市场信息字典

    Returns:
        str: 公司名称
    """
    try:
        if market_info['is_china']:
            # 中国A股：使用统一接口获取股票信息
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)

            # 解析股票名称
            if "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.debug(f"📊 [DEBUG] 从统一接口获取中国股票名称: {ticker} -> {company_name}")
                return company_name
            else:
                logger.warning(f"⚠️ [DEBUG] 无法从统一接口解析股票名称: {ticker}")
                return f"股票代码{ticker}"

        elif market_info['is_hk']:
            # 港股：使用改进的港股工具
            try:
                from tradingagents.dataflows.improved_hk_utils import get_hk_company_name_improved
                company_name = get_hk_company_name_improved(ticker)
                logger.debug(f"📊 [DEBUG] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                return company_name
            except Exception as e:
                logger.debug(f"📊 [DEBUG] 改进港股工具获取名称失败: {e}")
                # 降级方案：生成友好的默认名称
                clean_ticker = ticker.replace('.HK', '').replace('.hk', '')
                return f"港股{clean_ticker}"

        elif market_info['is_us']:
            # 美股：使用简单映射或返回代码
            us_stock_names = {
                'AAPL': '苹果公司',
                'TSLA': '特斯拉',
                'NVDA': '英伟达',
                'MSFT': '微软',
                'GOOGL': '谷歌',
                'AMZN': '亚马逊',
                'META': 'Meta',
                'NFLX': '奈飞'
            }

            company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
            logger.debug(f"📊 [DEBUG] 美股名称映射: {ticker} -> {company_name}")
            return company_name

        else:
            return f"股票{ticker}"

    except Exception as e:
        logger.error(f"❌ [DEBUG] 获取公司名称失败: {e}")
        return f"股票{ticker}"


def create_market_analyst_react(llm, toolkit):
    """使用ReAct Agent模式的市场分析师（适用于通义千问）"""
    @log_analyst_module("market_react")
    def market_analyst_react_node(state):
        logger.debug(f"📈 [DEBUG] ===== ReAct市场分析师节点开始 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"📈 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")

        # 检查是否为中国股票
        def is_china_stock(ticker_code):
            import re
            return re.match(r'^\d{6}$', str(ticker_code))

        is_china = is_china_stock(ticker)
        logger.debug(f"📈 [DEBUG] 股票类型检查: {ticker} -> 中国A股: {is_china}")

        if toolkit.config["online_tools"]:
            # 在线模式，使用ReAct Agent
            if is_china:
                logger.info(f"📈 [市场分析师] 使用ReAct Agent分析中国股票")

                # 创建中国股票数据工具
                from langchain_core.tools import BaseTool

                class ChinaStockDataTool(BaseTool):
                    name: str = "get_china_stock_data"
                    description: str = f"获取中国A股股票{ticker}的市场数据和技术指标（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] ChinaStockDataTool调用，股票代码: {ticker}")
                            # 使用优化的缓存数据获取
                            from tradingagents.dataflows.optimized_china_data import get_china_stock_data_cached
                            return get_china_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化A股数据获取失败: {e}")
                            # 备用方案：使用原始API
                            try:
                                return toolkit.get_china_stock_data.invoke({
                                    'stock_code': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"获取股票数据失败: {str(e2)}"

                tools = [ChinaStockDataTool()]
                query = f"""请对中国A股股票{ticker}进行详细的技术分析。

执行步骤：
1. 使用get_china_stock_data工具获取股票市场数据
2. 基于获取的真实数据进行深入的技术指标分析
3. 直接输出完整的技术分析报告内容

重要要求：
- 必须输出完整的技术分析报告内容，不要只是描述报告已完成
- 报告必须基于工具获取的真实数据进行分析
- 报告长度不少于800字
- 包含具体的数据、指标数值和专业分析

报告格式应包含：
## 股票基本信息
## 技术指标分析
## 价格趋势分析
## 成交量分析
## 市场情绪分析
## 投资建议"""
            else:
                logger.info(f"📈 [市场分析师] 使用ReAct Agent分析美股/港股")

                # 创建美股数据工具
                from langchain_core.tools import BaseTool

                class USStockDataTool(BaseTool):
                    name: str = "get_us_stock_data"
                    description: str = f"获取美股/港股{ticker}的市场数据和技术指标（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] USStockDataTool调用，股票代码: {ticker}")
                            # 使用优化的缓存数据获取
                            from tradingagents.dataflows.optimized_us_data import get_us_stock_data_cached
                            return get_us_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化美股数据获取失败: {e}")
                            # 备用方案：使用原始API
                            try:
                                return toolkit.get_YFin_data_online.invoke({
                                    'symbol': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"获取股票数据失败: {str(e2)}"

                class FinnhubNewsTool(BaseTool):
                    name: str = "get_finnhub_news"
                    description: str = f"获取美股{ticker}的最新新闻和市场情绪（通过FINNHUB API）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] FinnhubNewsTool调用，股票代码: {ticker}")
                            return toolkit.get_finnhub_news.invoke({
                                'ticker': ticker,
                                'start_date': '2025-05-28',
                                'end_date': current_date
                            })
                        except Exception as e:
                            return f"获取新闻数据失败: {str(e)}"

                tools = [USStockDataTool(), FinnhubNewsTool()]
                query = f"""请对美股{ticker}进行详细的技术分析。

执行步骤：
1. 使用get_us_stock_data工具获取股票市场数据和技术指标（通过FINNHUB API）
2. 使用get_finnhub_news工具获取最新新闻和市场情绪
3. 基于获取的真实数据进行深入的技术指标分析
4. 直接输出完整的技术分析报告内容

重要要求：
- 必须输出完整的技术分析报告内容，不要只是描述报告已完成
- 报告必须基于工具获取的真实数据进行分析
- 报告长度不少于800字
- 包含具体的数据、指标数值和专业分析
- 结合新闻信息分析市场情绪

报告格式应包含：
## 股票基本信息
## 技术指标分析
## 价格趋势分析
## 成交量分析
## 新闻和市场情绪分析
## 投资建议"""

            try:
                # 创建ReAct Agent
                prompt = hub.pull("hwchase17/react")
                agent = create_react_agent(llm, tools, prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=10,  # 增加到10次迭代，确保有足够时间完成分析
                    max_execution_time=180  # 增加到3分钟，给更多时间生成详细报告
                )

                logger.debug(f"📈 [DEBUG] 执行ReAct Agent查询...")
                result = agent_executor.invoke({'input': query})

                report = result['output']
                logger.info(f"📈 [市场分析师] ReAct Agent完成，报告长度: {len(report)}")

            except Exception as e:
                logger.error(f"❌ [DEBUG] ReAct Agent失败: {str(e)}")
                report = f"ReAct Agent市场分析失败: {str(e)}"
        else:
            # 离线模式，使用原有逻辑
            report = "离线模式，暂不支持"

        logger.debug(f"📈 [DEBUG] ===== ReAct市场分析师节点结束 =====")

        return {
            "messages": [("assistant", report)],
            "market_report": report,
        }

    return market_analyst_react_node


def create_market_analyst(llm, toolkit):

    def market_analyst_node(state):
        logger.debug(f"📈 [DEBUG] ===== 市场分析师节点开始 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"📈 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📈 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")
        logger.debug(f"📈 [DEBUG] 现有市场报告: {state.get('market_report', 'None')}")

        # 根据股票代码格式选择数据源
        from tradingagents.utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(ticker)

        logger.debug(f"📈 [DEBUG] 股票类型检查: {ticker} -> {market_info['market_name']} ({market_info['currency_name']})")

        # 获取公司名称
        company_name = _get_company_name(ticker, market_info)
        logger.debug(f"📈 [DEBUG] 公司名称: {ticker} -> {company_name}")

        if toolkit.config["online_tools"]:
            # 使用统一的市场数据工具，工具内部会自动识别股票类型
            logger.info(f"📊 [市场分析师] 使用统一市场数据工具，自动识别股票类型")
            tools = [toolkit.get_stock_market_data_unified]
            # 安全地获取工具名称用于调试
            tool_names_debug = []
            for tool in tools:
                if hasattr(tool, 'name'):
                    tool_names_debug.append(tool.name)
                elif hasattr(tool, '__name__'):
                    tool_names_debug.append(tool.__name__)
                else:
                    tool_names_debug.append(str(tool))
            logger.debug(f"📊 [DEBUG] 选择的工具: {tool_names_debug}")
            logger.debug(f"📊 [DEBUG] 🔧 统一工具将自动处理: {market_info['market_name']}")
        else:
            tools = [
                toolkit.get_YFin_data,
                toolkit.get_stockstats_indicators_report,
            ]

        # 统一的系统提示，适用于所有股票类型
        system_message = (
            f"""你是一位专业的股票技术分析师。你必须对{company_name}（股票代码：{ticker}）进行详细的技术分析。

**股票信息：**
- 公司名称：{company_name}
- 股票代码：{ticker}
- 所属市场：{market_info['market_name']}
- 计价货币：{market_info['currency_name']}（{market_info['currency_symbol']}）

**工具调用指令：**
你有一个工具叫做get_stock_market_data_unified，你必须立即调用这个工具来获取{company_name}（{ticker}）的市场数据。
不要说你将要调用工具，直接调用工具。

**分析要求：**
1. 调用工具后，基于获取的真实数据进行技术分析
2. 分析移动平均线、MACD、RSI、布林带等技术指标
3. 考虑{market_info['market_name']}市场特点进行分析
4. 提供具体的数值和专业分析
5. 给出明确的投资建议
6. 所有价格数据使用{market_info['currency_name']}（{market_info['currency_symbol']}）表示

**输出格式：**
## 📊 股票基本信息
- 公司名称：{company_name}
- 股票代码：{ticker}
- 所属市场：{market_info['market_name']}

## 📈 技术指标分析
## 📉 价格趋势分析
## 💭 投资建议

请使用中文，基于真实数据进行分析。确保在分析中正确使用公司名称"{company_name}"和股票代码"{ticker}"。"""
        )


        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的股票技术分析师，与其他分析师协作。"
                    "使用提供的工具来获取和分析股票数据。"
                    "如果你无法完全回答，没关系；其他分析师会从不同角度继续分析。"
                    "执行你能做的技术分析工作来取得进展。"
                    "如果你有明确的技术面投资建议：**买入/持有/卖出**，"
                    "请在你的回复中明确标注，但不要使用'最终交易建议'前缀，因为最终决策需要综合所有分析师的意见。"
                    "你可以使用以下工具：{tool_names}。\n{system_message}"
                    "供你参考，当前日期是{current_date}。"
                    "我们要分析的是{company_name}（股票代码：{ticker}）。"
                    "请确保所有分析都使用中文，并在分析中正确区分公司名称和股票代码。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)
        prompt = prompt.partial(company_name=company_name)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        # 使用统一的Google工具调用处理器
        if GoogleToolCallHandler.is_google_model(llm):
            logger.info(f"📊 [市场分析师] 检测到Google模型，使用统一工具调用处理器")
            
            # 创建分析提示词
            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=ticker,
                company_name=company_name,
                analyst_type="市场分析",
                specific_requirements="重点关注市场数据、价格走势、交易量变化等市场指标。"
            )
            
            # 处理Google模型工具调用
            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="市场分析师"
            )
            
            return {
                "messages": [result],
                "market_report": report,
            }
        else:
            # 非Google模型的处理逻辑
            logger.debug(f"📊 [DEBUG] 非Google模型 ({llm.__class__.__name__})，使用标准处理逻辑")
            
            # 处理市场分析报告
            if len(result.tool_calls) == 0:
                # 没有工具调用，直接使用LLM的回复
                report = result.content
                logger.info(f"📊 [市场分析师] 直接回复，长度: {len(report)}")
            else:
                # 有工具调用，执行工具并生成完整分析报告
                logger.info(f"📊 [市场分析师] 工具调用: {[call.get('name', 'unknown') for call in result.tool_calls]}")

                try:
                    # 执行工具调用
                    from langchain_core.messages import ToolMessage, HumanMessage

                    tool_messages = []
                    for tool_call in result.tool_calls:
                        tool_name = tool_call.get('name')
                        tool_args = tool_call.get('args', {})
                        tool_id = tool_call.get('id')

                        logger.debug(f"📊 [DEBUG] 执行工具: {tool_name}, 参数: {tool_args}")

                        # 找到对应的工具并执行
                        tool_result = None
                        for tool in tools:
                            # 安全地获取工具名称进行比较
                            current_tool_name = None
                            if hasattr(tool, 'name'):
                                current_tool_name = tool.name
                            elif hasattr(tool, '__name__'):
                                current_tool_name = tool.__name__

                            if current_tool_name == tool_name:
                                try:
                                    if tool_name == "get_china_stock_data":
                                        # 中国股票数据工具
                                        tool_result = tool.invoke(tool_args)
                                    else:
                                        # 其他工具
                                        tool_result = tool.invoke(tool_args)
                                    logger.debug(f"📊 [DEBUG] 工具执行成功，结果长度: {len(str(tool_result))}")
                                    break
                                except Exception as tool_error:
                                    logger.error(f"❌ [DEBUG] 工具执行失败: {tool_error}")
                                    tool_result = f"工具执行失败: {str(tool_error)}"

                        if tool_result is None:
                            tool_result = f"未找到工具: {tool_name}"

                        # 创建工具消息
                        tool_message = ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_id
                        )
                        tool_messages.append(tool_message)

                    # 基于工具结果生成完整分析报告
                    analysis_prompt = f"""现在请基于上述工具获取的数据，生成详细的技术分析报告。

要求：
1. 报告必须基于工具返回的真实数据进行分析
2. 包含具体的技术指标数值和专业分析
3. 提供明确的投资建议和风险提示
4. 报告长度不少于800字
5. 使用中文撰写

请分析股票{ticker}的技术面情况，包括：
- 价格趋势分析
- 技术指标解读
- 支撑阻力位分析
- 成交量分析
- 投资建议"""

                    # 构建完整的消息序列
                    messages = state["messages"] + [result] + tool_messages + [HumanMessage(content=analysis_prompt)]

                    # 生成最终分析报告
                    final_result = llm.invoke(messages)
                    report = final_result.content

                    logger.info(f"📊 [市场分析师] 生成完整分析报告，长度: {len(report)}")

                    # 返回包含工具调用和最终分析的完整消息序列
                    return {
                        "messages": [result] + tool_messages + [final_result],
                        "market_report": report,
                    }

                except Exception as e:
                    logger.error(f"❌ [市场分析师] 工具执行或分析生成失败: {e}")
                    traceback.print_exc()

                    # 降级处理：返回工具调用信息
                    report = f"市场分析师调用了工具但分析生成失败: {[call.get('name', 'unknown') for call in result.tool_calls]}"

                    return {
                        "messages": [result],
                        "market_report": report,
                    }

            return {
                "messages": [result],
                "market_report": report,
            }

    return market_analyst_node

def create_multi_stocks_market_analyst(llm, toolkit):
    """
    创建多股票市场分析师节点
    一次性分析多只股票的市场表现与技术面对比
    """

    @log_analyst_module("multi_stocks_market")
    def multi_stocks_market_analyst_node(state):
        logger.debug("📊 [DEBUG] ===== 多股票市场分析师节点开始 =====")

        # 从状态中获取股票代码，确保结果为list集合（兼容单字符串输入）
        tickers = state.get("company_of_interest", [])  # 默认返回空列表，避免None

        # 处理单字符串输入（如 'AAPL' 转为 ['AAPL']）
        if isinstance(tickers, str):
            # 去除字符串首尾空格，若为空则返回空列表
            tickers = [tickers.strip()] if tickers.strip() else []
        # 处理非列表/非字符串的非法输入（直接转为空列表）
        elif not isinstance(tickers, list):
            tickers = []
        # 清理列表中的无效元素（空字符串、None等）
        tickers = [ticker.strip() for ticker in tickers if ticker and str(ticker).strip()]
        current_date = state["trade_date"]

        logger.debug(f"📈 [DEBUG] 输入股票列表: {tickers}")
        logger.debug(f"📈 [DEBUG] 当前日期: {current_date}")

        from tradingagents.utils.stock_utils import StockUtils

        # 获取所有股票的基本信息
        stocks_info = []
        for ticker in tickers:
            try:
                market_info = StockUtils.get_market_info(ticker)
                company_name = _get_company_name(ticker, market_info)
                stocks_info.append({
                    "ticker": ticker,
                    "company_name": company_name,
                    "market_info": market_info
                })
            except Exception as e:
                logger.error(f"❌ [DEBUG] 无法获取 {ticker} 的市场信息: {e}")
                stocks_info.append({
                    "ticker": ticker,
                    "company_name": "未知公司",
                    "market_info": {"market_name": "未知市场", "currency_name": "未知货币", "currency_symbol": ""}
                })

        # 工具选择
        if toolkit.config["online_tools"]:
            tools = [toolkit.get_stock_market_data_unified]
            logger.debug(f"📈 [DEBUG] 使用统一市场数据工具: get_stock_market_data_unified")
        else:
            tools = [toolkit.get_YFin_data, toolkit.get_stockstats_indicators_report]

        # 构造系统提示词
        stock_list_text = "\n".join([
            f"- {info['company_name']}（代码：{info['ticker']}，市场：{info['market_info']['market_name']}，货币：{info['market_info']['currency_name']}）"
            for info in stocks_info
        ])

        system_message = f"""
你是一位专业的股票技术分析师。你需要**一次性分析多只股票的市场表现与技术指标对比**。

**分析股票列表：**
{stock_list_text}

**分析目标：**
1. 调用工具一次性获取这些股票的市场数据
2. 分析它们的价格走势、波动性、成交量、技术指标（MA、MACD、RSI、布林带等）
3. 比较各股票的强弱表现与风险
4. 结合市场环境，判断板块或行业整体趋势
5. 最后给出每只股票的明确投资建议（买入 / 持有 / 卖出）
6. 所有价格使用各自市场对应的货币单位

**输出格式：**
## 📊 股票基本信息概览
（列出所有股票的市场、货币、主要指标简表）

## 📈 技术指标与走势对比
（对比各股票技术指标、波动性、成交量等）

## 💡 市场结构与板块分析
（指出这些股票是否属于相同板块或市场的联动关系）

## 💭 投资建议总结
（对每只股票给出建议，并说明理由）

请使用中文撰写完整分析报告。
"""

        # Prompt 模板
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的多股票市场分析师，擅长横向比较与趋势判断。\n"
                    "请使用提供的工具，获取多只股票的真实市场数据并进行系统性分析。\n"
                    "{system_message}\n"
                    "当前日期是 {current_date}。"
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message, current_date=current_date)
        chain = prompt | llm.bind_tools(tools)

        # 执行一次调用，获取所有股票数据（工具会内部识别多股票）
        result = chain.invoke(state.get("messages", []))

        # Google 模型特殊处理
        if GoogleToolCallHandler.is_google_model(llm):
            logger.info("📊 [多股票市场分析师] 检测到Google模型，使用统一工具调用处理器")

            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=", ".join([s["ticker"] for s in stocks_info]),
                company_name=", ".join([s["company_name"] for s in stocks_info]),
                analyst_type="多股票市场分析",
                specific_requirements="一次性对多只股票进行趋势、指标、风险和投资建议的对比分析。"
            )

            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="多股票市场分析师"
            )

            return {
                "messages": [result],
                "market_report": report,
            }

        # 非Google模型：执行工具调用后继续分析
        if len(result.tool_calls) == 0:
            report = result.content
            logger.info(f"📊 [多股票市场分析师] 无工具调用，直接输出分析结果。")
        else:
            from langchain_core.messages import ToolMessage, HumanMessage

            tool_messages = []
            for tool_call in result.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")

                logger.debug(f"📊 [DEBUG] 执行工具: {tool_name}, 参数: {tool_args}")
                for tool in tools:
                    current_tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))
                    if current_tool_name == tool_name:
                        try:
                            tool_result = tool.invoke(tool_args)
                            tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                        except Exception as e:
                            logger.error(f"❌ 工具执行失败: {e}")
                            tool_messages.append(ToolMessage(content=f"工具执行失败: {e}", tool_call_id=tool_id))

            # 生成综合多股分析
            analysis_prompt = f"""
现在请基于上述工具返回的数据，生成详细的多股票市场分析报告。
请你：
1. 比较这些股票的价格走势、波动性、技术指标和成交量差异
2. 指出表现最强和最弱的股票
3. 分析它们可能的板块联动或风险关联
4. 给出每只股票的投资建议（买入/持有/卖出）
5. 最后总结整体市场趋势

请使用中文撰写，内容不少于1000字。
"""
            messages = state.get("messages", []) + [result] + tool_messages + [HumanMessage(content=analysis_prompt)]
            final_result = llm.invoke(messages)
            report = final_result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return multi_stocks_market_analyst_node


# 使用akshare数据集，获取数据

def create_multi_stocks_market_analyst_ak(llm, toolkit):
    """
    创建多股票市场分析师节点
    一次性分析多只股票的市场表现与技术面对比
    """

    @log_analyst_module("multi_stocks_market")
    def multi_stocks_market_analyst_node(state):
        logger.debug("📊 [DEBUG] ===== 多股票市场分析师节点开始 =====")

        # 从状态中获取股票代码，确保结果为list集合（兼容单字符串输入）
        tickers = state.get("company_of_interest", [])  # 默认返回空列表，避免None

        # 处理单字符串输入（如 'AAPL' 转为 ['AAPL']）
        if isinstance(tickers, str):
            # 去除字符串首尾空格，若为空则返回空列表
            tickers = [tickers.strip()] if tickers.strip() else []
        # 处理非列表/非字符串的非法输入（直接转为空列表）
        elif not isinstance(tickers, list):
            tickers = []
        # 清理列表中的无效元素（空字符串、None等）
        tickers = [ticker.strip() for ticker in tickers if ticker and str(ticker).strip()]
        current_date = state["trade_date"]

        logger.info(f"📈 [DEBUG] 输入股票列表: {tickers}")
        logger.info(f"📈 [DEBUG] 当前日期: {current_date}")

        from tradingagents.utils.stock_utils import StockUtils

        # 获取所有股票的基本信息
        stocks_info = []
        for ticker in tickers:
            try:
                market_info = StockUtils.get_market_info(ticker)
                company_name = _get_company_name(ticker, market_info)
                stocks_info.append({
                    "ticker": ticker,
                    "company_name": company_name,
                    "market_info": market_info
                })
            except Exception as e:
                logger.error(f"❌ [DEBUG] 无法获取 {ticker} 的市场信息: {e}")
                stocks_info.append({
                    "ticker": ticker,
                    "company_name": "未知公司",
                    "market_info": {"market_name": "未知市场", "currency_name": "未知货币", "currency_symbol": ""}
                })

        # 工具选择
        if toolkit.config["online_tools"]:
            tools = [StockDataFetcher.get_stock_data]
            logger.info(f"📈 [DEBUG] 使用统一市场数据工具: get_stock_data")
        else:
            tools = [toolkit.get_YFin_data, toolkit.get_stockstats_indicators_report]

        # 构造系统提示词
        stock_list_text = "\n".join([
            f"- {info['company_name']}（代码：{info['ticker']}，市场：{info['market_info']['market_name']}，货币：{info['market_info']['currency_name']}）"
            for info in stocks_info
        ])

        system_message = f"""
你是一位专业的股票技术分析师。你需要**一次性分析多只股票的市场表现与技术指标对比**。

**分析股票列表：**
{stock_list_text}

你的任务是调用支持多股票批量查询的 get_stock_data 工具，一次性传入所有股票的 stock_code 列表，获取真实的市场历史数据。在全部数据成功获取后，输出完整的多股票横向分析报告。

--------------------------------------------
【工具调用规则 —— 必须严格执行】
--------------------------------------------
1. **仅需调用 get_stock_data 一次**，将列表中所有股票的 stock_code 以列表形式传入，无需逐只单独调用。
2. 工具参数必须完整提供，具体要求如下：
   - stock_codes：所有股票的 stock_code 组成的列表（格式：["code1", "code2", ...]）
   - start_time：按时间规则确定的统一开始时间（格式符合工具要求）
   - end_time：按时间规则确定的统一结束时间（格式符合工具要求）
   - period：按时间规则确定的统一数据周期
   - adjust：复权类型（无需复权则传空字符串 ""）

3. 工具返回结果为字典（键为股票代码，值为对应数据帧/None），需先校验所有股票数据是否获取成功：
   - 若单只股票数据为 None，需重新调用工具补充查询该股票
   - 若全部股票数据获取成功，再开始撰写最终分析报告

--------------------------------------------
【时间区间与周期选择规则 —— 必须严格执行】
--------------------------------------------
你需要根据“当前时间是否在开盘时间”来决定查询方式，所有股票共用同一套时间与周期参数：

### ✔ 情况 A：当前时间 **不是开盘时间**
请按照“日线周期 1d”获取过去 **1 年区间** 的历史数据：
- period = "1d"
- start_time = 当前日期往前 365 天（格式："YYYY-MM-DD"）
- end_time = 当前日期（格式："YYYY-MM-DD"）
例如：当前日期是 2025-11-18 → start_time = "2024-11-18"，end_time = "2025-11-18"

### ✔ 情况 B：当前时间 **处于开盘时间区间（例如 09:30 ~ 16:00）**
请使用“分钟级别数据”，查询当天开盘以来的所有分钟数据：
- period = "1m"（或你认为更合适的分钟线周期）
- start_time = 当前日期 + " 09:30:00"（格式："YYYY-MM-DD HH:MM:SS"）
- end_time = 当前实际时间（精确到分钟，格式："YYYY-MM-DD HH:MM"）
例如：start_time = "2025-11-18 09:30:00"，end_time = "2025-11-18 14:42:00"

你必须根据当前时间判断应使用“日线模式”或“分钟线模式”，并据此正确填写 get_stock_data 的参数。

--------------------------------------------
【你的分析目标】
--------------------------------------------
在所有股票数据成功获取并解析后，你需要完成以下分析：

1. 分析每只股票的：
   - 趋势（短期、中期、长期）
   - 波动率
   - 成交量结构
   - 支撑与压力位
   - 技术指标（MA 系列、MACD、RSI、BOLL、KDJ 等）

2. 对比多只股票的强弱表现，包括：
   - 价格动能
   - 技术指标信号强弱
   - 波动性差异
   - 成交量活跃度
   - 风险水平

3. 识别这些股票之间是否存在板块或行业联动关系，并评估板块强弱。

4. 最终对每只股票分别给出明确投资建议（买入 / 持有 / 卖出）及理由。

--------------------------------------------
【最终输出格式要求】
--------------------------------------------
在所有工具调用结束后，请按以下格式输出最终分析：

## 📊 股票基本信息概览
（列出所有股票的市场、货币、基础行情指标、技术指标简表）

## 📈 技术指标与走势对比
（MA / MACD / RSI / BOLL / 波动性 / 成交量 等横向比较）

## 💡 市场结构与板块联动分析
（分析是否属于同一行业板块、市场联动、指数相关性等）

## 💭 投资建议总结
（对每只股票给出“买入、持有、卖出”的清晰建议 + 依据）

--------------------------------------------
请使用地道、专业的中文撰写最终分析报告。
"""

        # Prompt 模板
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的多股票市场分析师，擅长横向比较与趋势判断。\n"
                    "请使用提供的工具，获取多只股票的真实市场数据并进行系统性分析。\n"
                    "{system_message}\n"
                    "当前日期是 {current_date}。"
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message, current_date=current_date)
        chain = prompt | llm.bind_tools(tools)

        # 执行一次调用，获取所有股票数据（工具会内部识别多股票）
        result = chain.invoke(state.get("messages", []))

        # Google 模型特殊处理
        if GoogleToolCallHandler.is_google_model(llm):
            logger.info("📊 [多股票市场分析师] 检测到Google模型，使用统一工具调用处理器")

            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=", ".join([s["ticker"] for s in stocks_info]),
                company_name=", ".join([s["company_name"] for s in stocks_info]),
                analyst_type="多股票市场分析",
                specific_requirements="一次性对多只股票进行趋势、指标、风险和投资建议的对比分析。"
            )

            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="多股票市场分析师"
            )

            return {
                "messages": [result],
                "market_report": report,
            }

        # 非Google模型：执行工具调用后继续分析
        if len(result.tool_calls) == 0:
            report = result.content
            logger.info(f"📊 [多股票市场分析师] 无工具调用，直接输出分析结果。")
        else:
            from langchain_core.messages import ToolMessage, HumanMessage

            tool_messages = []
            for tool_call in result.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")

                logger.debug(f"📊 [DEBUG] 执行工具: {tool_name}, 参数: {tool_args}")
                for tool in tools:
                    current_tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))
                    if current_tool_name == tool_name:
                        try:
                            tool_result = tool.invoke(tool_args)
                            tool_messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_id))
                        except Exception as e:
                            logger.error(f"❌ 工具执行失败: {e}")
                            tool_messages.append(ToolMessage(content=f"工具执行失败: {e}", tool_call_id=tool_id))

            # 生成综合多股分析
            analysis_prompt = f"""
现在请基于上述工具返回的数据，生成详细的多股票市场分析报告。
请你：
1. 比较这些股票的价格走势、波动性、技术指标和成交量差异
2. 指出表现最强和最弱的股票
3. 分析它们可能的板块联动或风险关联
4. 给出每只股票的投资建议（买入/持有/卖出）
5. 最后总结整体市场趋势

请使用中文撰写，内容不少于1000字。
"""
            messages = state.get("messages", []) + [result] + tool_messages + [HumanMessage(content=analysis_prompt)]
            final_result = llm.invoke(messages)
            report = final_result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return multi_stocks_market_analyst_node
