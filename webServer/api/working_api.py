import datetime

from flask import Blueprint, request, g
from langchain_openai import ChatOpenAI

from tradingagents.agents.utils.agent_utils import Toolkit
from webServer.agentAnalyst.coordinator_agent import MultiCoordinatorAgent
from webServer.api.user_api import login_required
from webServer.services.conversation_manager_service import ConversationManager
from webServer.services.market_service import get_report
from webServer.services.scheduler.tasks.StockAnalysisTask import normalize_report_template
from webServer.tools.mongodb_tools import str_to_objectid
from webServer.tools.report_format_tools import get_time_label, get_report_template
from webServer.tools.session_tools import generate_session_id
from webServer.utils import mongo_db
from webServer.utils.response import success, fail
collection = mongo_db['stock_news']
user_collection = mongo_db['user']
work_bp = Blueprint("work",__name__)
conv_manager = ConversationManager()
@work_bp.route("/get/report",methods=["POST"])
@login_required
def get_work_report():
    from webServer.run import app
    try:
        # request.get_json() 会解析请求体中的JSON，返回字典；若解析失败返回None
        request_data = request.get_json()
        if not request_data:
            raise ValueError("请求体格式错误，请使用JSON格式并确保Content-Type为application/json")

        # 2. 从JSON数据中获取参数（替代原request.args.get()）
        # trade_date：可选，默认当天；若传递则取传递值
        trade_date = request_data.get('trade_date', '')
        if not trade_date:  # 若未传递或值为空
            trade_date = datetime.date.today().isoformat()

        # company_of_interest：必填，股票代码
        company_of_interest = request_data.get('company_of_interest', '')
        if not company_of_interest:  # 严格校验不能为空
            raise ValueError("股票代码（company_of_interest）不允许为空，请提供有效的股票代码")

        # messages：可选，列表类型（默认空列表）
        messages = request_data.get('messages', [])
        # 可选：校验messages是否为列表（避免客户端传错类型）
        if not isinstance(messages, list):
            raise ValueError("messages必须是列表类型")
        state = {
            "trade_date":trade_date,
            "company_of_interest":company_of_interest,
            "messages":messages
        }
        print(f"user_id:{g.user_id}")
        user = user_collection.find_one({"_id": str_to_objectid(g.user_id)})
        label = get_time_label()
        session_id = generate_session_id(prefix="stock_", length=32)
        report = ""
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
            # 3. 构造任务参数（从配置中获取或使用默认值）

            conv_manager.add_user_message(session_id=session_id, content=f"{state}")
            ## TODO 从用户配中获取模版
            user_report_template = normalize_report_template(user)
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
            company_code = state.get("company_of_interest", [])
            trade_date = state.get("trade_date", "")
            print(f"开始执行【{company_code}】{trade_date}的股票分析任务")
            report = multi_coordinator_agent.run(prompt)  # 关键：传原始字典而非字符串
            conv_manager.add_assistant_message(session_id=session_id, content=report)
            state["report"] = report
            state["label"] = label
            state["session_id"] = session_id
            state['user_id'] = g.user_id
            state["is_read"] = "NO"
            state['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 5. 保存结果到MongoDB
            result = collection.insert_one(state)
            print(f"插入成功，文档ID：{result.inserted_id}")
        except Exception as e:
            print(f"股票分析任务执行失败：{str(e)}")
            company_code = state.get("company_of_interest", "000001")  # 平安银行
            trade_date = state.get("trade_date", "2025-09-19")  # 可动态调整为当日

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
        return success(report)
    except Exception as e:
        print(str(e))
        return fail(str(e))
