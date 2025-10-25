from tradingagents.agents.utils.agent_utils import Toolkit
from webServer.agentAnalyst.coordinator_agent import CoordinatorAgent
from .base_task import BaseTask
from langchain_openai import ChatOpenAI
from webServer.utils import mongo_db
import datetime

collection = mongo_db['scheduler']

class StockAnalysisTask(BaseTask):
    """股票分析定时任务：调用协调Agent并存储结果到MongoDB"""

    def run(self) -> None:
        """执行股票分析任务"""
        try:
            # 1. 初始化LLM和工具
            llm = ChatOpenAI(
                model="deepseek-chat",
                api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",
                base_url="https://api.deepseek.com/v1",
            )
            toolkit = Toolkit()  # 假设你已有Toolkit类

            # 2. 初始化Agent
            coordinator_agent = CoordinatorAgent(llm, toolkit)

            # 3. 构造任务参数（从配置中获取或使用默认值）

            company_code = self.args.get("company_of_interest", "000001")  # 平安银行
            trade_date = self.args.get("trade_date", datetime.date.today().isoformat())  # 可动态调整为当日
            print(f"time:{trade_date}")

            state = {
                "trade_date": trade_date,
                "company_of_interest": company_code,
                "messages": [
                    {"role": "user", "content": "请对平安银行做一个全面分析，并给出投资建议。"}
                ]
            }

            # 4. 调用协调Agent执行分析（注意：直接传字典，不要转字符串）
            self.logger.info(f"开始执行【{company_code}】{trade_date}的股票分析任务")
            report = coordinator_agent.run(f"{state}")  # 关键：传原始字典而非字符串

            state["report"] = report
            # 5. 保存结果到MongoDB
            result = collection.insert_one(state)
            self.logger.info(f"插入成功，文档ID：{ result.inserted_id}")

        except Exception as e:
            self.logger.error(f"股票分析任务执行失败：{str(e)}", exc_info=True)
            company_code = self.args.get("company_of_interest", "000001")  # 平安银行
            trade_date = self.args.get("trade_date", "2025-09-19")  # 可动态调整为当日

            state = {
                "trade_date": trade_date,
                "company_of_interest": company_code,
                "messages": [
                    {"role": "user", "content": "请对平安银行做一个全面分析，并给出投资建议。"}
                ],
                "report":str(e)
            }
            result = collection.insert_one(state)
            self.logger.info(f"插入成功，文档ID：{result.inserted_id}")

