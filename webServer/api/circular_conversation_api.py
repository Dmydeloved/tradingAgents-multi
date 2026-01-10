from flask import Blueprint, request, g
from langchain_openai import ChatOpenAI

from webServer.api.user_api import login_required
from webServer.services.conversation_manager_service import ConversationManager
from webServer.tools.session_tools import generate_session_id
from webServer.utils.response import fail, success

chat_bp = Blueprint("chat",__name__)

conv_manager = ConversationManager()

llm = ChatOpenAI(
    model="deepseek-chat",  # DeepSeek 模型
    api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 测试用 key
    base_url="https://api.deepseek.com/v1",
)

@chat_bp.route("/get/reply",methods=["POST"])
@login_required
def chat() -> str:
    from webServer.run import app
    try:
        # request.get_json() 会解析请求体中的JSON，返回字典；若解析失败返回None
        request_data = request.get_json()
        if not request_data:
            raise ValueError("请求体格式错误，请使用JSON格式并确保Content-Type为application/json")

        session_id = request_data.get('session_id', '')
        if not session_id:
            session_id = generate_session_id()

        user_input = request_data.get('user_input', '')
        if not user_input:  # 严格校验不能为空
            raise ValueError("用户输入不允许为空，请提供用户需求")

        session_id = f"{g.user_id}_{ session_id}"
        # 1. 用户消息写入历史
        conv_manager.add_user_message(session_id, user_input)

        # 2. 获取完整会话消息
        messages = conv_manager.build_messages(session_id)

        # 3. 调用模型
        resp = llm.invoke(messages)
        reply = resp.content

        # 4. 写入模型回复
        conv_manager.add_assistant_message(session_id, reply)
        app.logger.info(f"reply:{reply}")
    except Exception as e:
        app.logger.error(f"生成market report失败，原因：{str(e)}")
        return fail(data=str(e))
    return success(reply)


@chat_bp.route("/get/historyList",methods=["GET"])
@login_required
def history_list() -> str:
    from webServer.run import app
    try:
        history_messages = conv_manager.get_all_sessions_by_user(g.user_id)
    except Exception as e:
        app.logger.error(f"生成market report失败，原因：{str(e)}")
        return fail(data=str(e))
    return success(history_messages)


@chat_bp.route("/get/history",methods=["POST"])
@login_required
def history() -> str:
    from webServer.run import app
    try:
        request_data = request.get_json()
        if not request_data:
            raise ValueError("请求体格式错误，请使用JSON格式并确保Content-Type为application/json")

        session_id = request_data.get('session_id', '')
        if not session_id:
            session_id = generate_session_id()
        session_id = f"{g.user_id}_{session_id}"
        history_messages = conv_manager.get_history(session_id)
    except Exception as e:
        app.logger.error(f"生成market report失败，原因：{str(e)}")
        return fail(data=str(e))
    return success(history_messages)