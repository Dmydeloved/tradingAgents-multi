import datetime

from flask import Blueprint, request
from webServer.services.market_service import get_report
from webServer.utils.response import success, fail

market_bp = Blueprint("market",__name__)

@market_bp.route("/get/report",methods=["POST"])
def get_market_report():
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
        app.logger.info(f"用户开始获取market report，trade_date:{trade_date},company_of_interest:{company_of_interest}")
        market_report = get_report(state)
    except Exception as e:
        app.logger.error(f"生成market report失败，原因：{str(e)}")
        return fail(data=str(e))
    return success(market_report)