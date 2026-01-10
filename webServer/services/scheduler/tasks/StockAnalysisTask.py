import json

from tradingagents.agents.utils.agent_utils import Toolkit
from webServer.agentAnalyst.coordinator_agent import CoordinatorAgent, MultiCoordinatorAgent
from webServer.services.conversation_manager_service import ConversationManager
from webServer.services.scheduler.tasks.base_task import BaseTask
from webServer.tools.mongodb_tools import convert_objectId
from webServer.tools.report_format_tools import get_report_template, get_time_label
from webServer.tools.session_tools import generate_session_id
from webServer.tools.time_task_tools import get_state
from langchain_openai import ChatOpenAI
from webServer.utils import mongo_db
import datetime

collection = mongo_db['stock_news']
user_collection = mongo_db['user']
conv_manager = ConversationManager()

class StockAnalysisTask(BaseTask):
    """股票分析定时任务：调用协调Agent并存储结果到MongoDB"""

    def run(self) -> None:
        label = get_time_label()
        session_id = generate_session_id(prefix="stock_", length=32)
        """执行股票分析任务"""
        try:
            print("开始生成定时报告")
            # 1. 初始化LLM和工具
            llm = ChatOpenAI(
                model="deepseek-chat",
                api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",
                base_url="https://api.deepseek.com/v1",
            )
            toolkit = Toolkit()  # 假设你已有Toolkit类

            # 2. 初始化Agent
            multi_coordinator_agent = MultiCoordinatorAgent(llm, toolkit)
            # 获取全部用户信息
            users = user_collection.find({"status": "生效"})

            # 3. 处理结果：将ObjectId类型的_id转为字符串
            active_users = convert_objectId(list(users))
            print(f"成功查询到 {len(active_users)} 个生效用户")
            for active_user in active_users:
                try:
                    # 3. 构造任务参数（从配置中获取或使用默认值）
                    ### TODO 从数据库中动态获取
                    user_id, state = get_state(active_user)
                    conv_manager.add_user_message(session_id=session_id, content=f"{state}")
                    ## TODO 从用户配中获取模版
                    user_report_template = normalize_report_template(active_user)
                    report_form = get_report_template(user_report_template)

                    prompt = f"""
                    请根据以下信息生成分析报告：
            
                    【背景数据（供工具调用时参考）】
                    {state}
            
                    【最终报告必须严格遵循的格式】
                    {report_form}
            
                    要求：
                    1. 工具调用时可使用背景数据中的 trade_date（交易日）、company_list（关注公司）等信息。
                    2. 最终输出的报告结构、模块必须完全匹配上述格式，不遗漏任何要求的板块。
                    3. 报告内容需结合工具调用结果和背景数据（如重点分析 company_list 中的公司）。
                    """
                    # 4. 调用协调Agent执行分析（注意：直接传字典，不要转字符串）
                    company_code = state.get("company_of_interest",[])
                    trade_date = state.get("trade_date","")
                    print(f"开始执行【{company_code}】{trade_date}的股票分析任务")
                    report = multi_coordinator_agent.run(prompt)  # 关键：传原始字典而非字符串
                    conv_manager.add_assistant_message(session_id=session_id,content=report)
                    state["report"] = report
                    state["label"] = label
                    state["session_id"] = session_id
                    state['user_id'] = user_id
                    state["is_read"] = "NO"
                    state['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 5. 保存结果到MongoDB
                    result = collection.insert_one(state)
                    print(f"插入成功，文档ID：{ result.inserted_id}")
                except Exception as e:
                    print(f"user:{active_user['_id']} 股票分析任务执行失败：{str(e)}")
                    continue
        except Exception as e:
            print(f"股票分析任务执行失败：{str(e)}")
            company_code = self.args.get("company_of_interest", "000001")  # 平安银行
            trade_date = self.args.get("trade_date", "2025-09-19")  # 可动态调整为当日

            state = {
                "trade_date": trade_date,
                "company_of_interest": company_code,
                "messages": [
                    {"role": "user", "content": "请对平安银行做一个全面分析，并给出投资建议。"}
                ],
                "report": str(e),
                "label": get_time_label(),
                "session_id": session_id,
                "user_id": "admin",
                "is_read": "NO",
                'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            result = collection.insert_one(state)
            print(f"插入成功，文档ID：{result.inserted_id}")


def normalize_report_template(active_user: dict) -> dict:
    """
    将 active_user 中的 report_template 规范化为 dict
    - 支持 dict / JSON 字符串
    - 任何异常或为空时，返回空 dict {}
    """
    report_template = active_user.get("report_template")

    if not report_template:
        return {}

    # 已经是 dict
    if isinstance(report_template, dict):
        return report_template

    # JSON 字符串
    if isinstance(report_template, str):
        try:
            parsed = json.loads(report_template)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    # 其他未知类型
    return {}
if __name__ == "__main__":
    stock_analysis = StockAnalysisTask()
    stock_analysis.run()