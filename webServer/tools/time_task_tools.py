import datetime
import json

from webServer.tools.mongodb_tools import convert_objectId, str_to_objectid


def parse_investment_profile(user_investment_profile):
    """
    解析用户投资档案：拼接成自然语句 + 提取所有股票代码（去重）
    :param user_investment_profile: 用户投资档案字典（与注册接口请求体结构一致）
    :return: tuple (profile_text: 拼接后的语句, stock_codes: 所有股票代码列表)
    """
    # 1. 提取核心投资信息
    goals = user_investment_profile["personalized_investment_goals"]
    tenure = goals["investment_tenure"]
    expected = goals["expected_return"]
    risk = goals["risk_tolerance"]

    # 2. 提取持仓信息并拼接
    holdings = user_investment_profile["current_holdings"]["holdings_list"]
    holding_texts = []
    holding_codes = []
    for h in holdings:
        code = h["stock_code"]
        name = h["stock_name"]
        qty = h["holding_quantity"]
        price = h["purchase_price"]
        holding_texts.append(f"{name}（{code}）{qty}股，买入均价{price}元")
        holding_codes.append(code)

    # 3. 提取自选股信息并拼接
    watchlist = user_investment_profile["watchlist"]["watchlist_list"]
    watch_texts = []
    watch_codes = []
    for w in watchlist:
        code = w["stock_code"]
        name = w["stock_name"]
        watch_texts.append(f"{name}（{code}）")
        watch_codes.append(code)

    # 4. 拼接完整语句
    profile_text = (
        f"用户投资目标为{tenure['tenure_description']}，投资期限{tenure['specific_years']}年（{tenure['tenure_type']}），"
        f"预期年化收益率{expected['annualized_return_rate']}%，收益稳定性要求{expected['return_stability']}；"
        f"风险承受能力为{risk['risk_level']}，可接受最大年亏损{risk['loss_tolerance_ratio']}%，{risk['risk_description']}。"
        f"当前持仓包括：{('、'.join(holding_texts))}；"
        f"自选关注股票包括：{('、'.join(watch_texts))}。"
    )

    # 5. 提取所有股票代码（去重，保持原始顺序）
    all_stock_codes = []
    seen_codes = set()
    # 先加持仓代码，再加自选股代码（避免重复）
    for code in holding_codes + watch_codes:
        if code not in seen_codes:
            seen_codes.add(code)
            all_stock_codes.append(code)

    return profile_text, all_stock_codes

def get_state(user):
    # from webServer.utils import mongo_db
    # user_collection = mongo_db['user']
    # user = user_collection.find_one({"_id": str_to_objectid("691ea11916441e5b365f450f")})
    user_investment_profile = user.get("user_investment_profile")
    investment_profile = json.loads(user_investment_profile)
    profile_text, stock_codes = parse_investment_profile(investment_profile)
    date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state = {
        "trade_date": date_time,
        "company_of_interest": stock_codes,
        "messages":[
            {"role":"user","content":profile_text}
        ]
    }
    # user_id = "691ea11916441e5b365f450f"
    print(f"user_id:{user['_id']}, state:{json.dumps(state, ensure_ascii=False, indent=2)}")
    return user['_id'], state

if __name__ == "__main__":
    print("asdfa")
    # state = get_state()
    # print(json.dumps(state, ensure_ascii=False, indent=2))