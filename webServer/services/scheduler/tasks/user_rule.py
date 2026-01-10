import datetime

import json

from langchain_openai import ChatOpenAI

from webServer.services.scheduler.tasks.base_task import BaseTask
from webServer.tools.llm_request_tools import gpt
from webServer.tools.mongodb_tools import str_to_objectid, convert_objectId
from webServer.utils import mongo_db

rule_collection = mongo_db['user_rule']
user_collection = mongo_db['user']
event_collection = mongo_db['events']
stock_collection = mongo_db['stock_news']


def get_prompt(user_data_json):
  prompt = f'''
  你是一名专业的金融投资事件规划助手，需要基于用户的当前持仓、关注列表和投资目标，
为用户生成“金融事件规划”。

用户信息如下（JSON格式）：
{user_data_json}

请严格按照下列事件类型、事件子类型、及 related_stock 填写规则生成事件，
不允许创造未定义的事件类型、子事件或分类名称。

==================== 一、事件类型与子事件定义 ====================

1.【市场交易类事件（Trading）】
event_subtype：
- price_rise_abnormal
- price_fall_abnormal
- volume_abnormal
- limit_up
- limit_down
- ma_break_up
- ma_break_down
- volatility_abnormal
related_stock：
- 股票代码（如 600519）

2.【资金流向类事件（Capital）】
event_subtype：
- northbound_inflow_abnormal
- northbound_outflow_abnormal
- margin_balance_abnormal
- block_trade_price_deviation
related_stock：
- 股票代码或行业名称（如 银行）

3.【公司事件（Company）】
event_subtype：
- performance_forecast
- financial_report_change
- share_unlock
- trading_halt
- trading_resume
related_stock：
- 股票代码

4.【行业事件（Industry）】
event_subtype：
- industry_price_rise_abnormal
- industry_price_fall_abnormal
- industry_capital_inflow_abnormal
- industry_capital_outflow_abnormal
- industry_consistency_rise
- industry_consistency_fall
- industry_leader_fluctuation
related_stock（必须从以下完整列表中选择）：
零售、综合、饮料制造、包装印刷、食品加工制造、种植业与林业、厨卫电器、
房地产、汽车服务及其他、服装家纺、钢铁、家居用品、教育、互联网电商、
化学原料、环保设备、工业金属、汽车零部件、旅游及酒店、金属新材料、
纺织制造、农产品加工、能源金属、美容护理、电机、环境治理、燃气、
贸易、小金属、造纸、化学制药、养殖业、建筑材料、专用设备、农化制品、
轨交设备、文化传媒、化学纤维、通用设备、电网设备、机场航运、建筑装饰、
小家电、化学制品、多元金融、公路铁路运输、汽车整车、石油加工贸易、
计算机设备、工程机械、中药、军工装备、医疗服务、其他社会服务、塑料制品、
港口航运、军工电子、游戏、风电设备、生物制品、IT服务、白色家电、电池、
光伏设备、电力、物流、黑色家电、其他电源设备、自动化设备、光学光电子、
通信服务、消费电子、医疗器械、非金属材料、白酒、油气开采及服务、
通信设备、软件开发、证券、其他电子、电子化学品、影视院线、医药商业、
煤炭开采加工、保险、银行、橡胶制品、元件、贵金属、半导体

5.【宏观事件（Macro）】
event_subtype（必须从以下完整列表中选择）：
macro_央行政策、macro_经济增长、macro_通胀数据、macro_金融监管、
macro_国际局势、macro_产业政策、macro_资本市场、macro_综合宏观新闻
related_stock（必须从以下完整列表中选择）：
央行政策、经济增长、通胀数据、金融监管、国际局势、产业政策、
资本市场、综合宏观新闻

6.【情绪事件（Sentiment）】
event_subtype：
- attention_surge
- attention_explosion
- attention_drop
- attention_collapse
- ranking_rise_abnormal
- ranking_drop_abnormal
- hot_list_entry
- hot_list_top10
- hot_list_top1
related_stock：
- 股票代码或行业名称

7.【新闻事件（News）】
event_subtype：
- positive_news
- negative_news
- neutral_news
- regulatory_news
- major_news
- emergency_news
related_stock：
- 股票代码、行业名称或宏观分类（如 宏观事件列表）

==================== 二、生成规则 ====================
- 仅生成与用户持仓、关注列表或投资目标直接相关的事件
- 每条事件必须包含触发条件
- 不生成投资建议，仅做事件规划
- 同一标的可生成多条不同类型事件

==================== 三、输出格式 ====================
请直接输出 JSON 数组（JSON 字符串），格式如下：

[
  {{
    "event_type": "Trading / Capital / Company / Industry / Macro / Sentiment / News",
    "event_subtype": "必须来自枚举列表",
    "related_stock": "必须符合事件类型对应规则",
    "event_description": "事件客观描述",
    "trigger_condition": "触发事件的具体条件"
  }}
]

==================== 严格要求 ====================
- 仅输出 JSON
- 不输出任何解释性文字或注释
- JSON 必须可被 json.loads() 解析

    '''

  return prompt


def get_user_rule(user_data):
    llm = ChatOpenAI(
        model="deepseek-chat",  # 你要用的 DeepSeek 模型
        api_key="sk-88658b1575c14130ad1dfde6f12ef2fb",  # 直接写死 key
        base_url="https://api.deepseek.com/v1"  # DeepSeek API 地址
    )
    prompt = get_prompt(user_data)
    resp = llm.invoke(prompt)
    data = json.loads(resp.content)
    print(type(data))
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data

def run(user_id):
    """
     核心执行方法：查询用户数据 -> 生成规则 -> 存储规则
     :param user_id: 用户唯一标识
     :return: 存储后的规则文档ID
     """
    # 1. 校验入参
    if not user_id:
        raise ValueError("user_id不能为空")

    # 2. 从MongoDB查询用户数据
    try:
        user_doc = user_collection.find_one({"_id": str_to_objectid(user_id)}, {"user_investment_profile": 1})
        if not user_doc:
            raise ValueError(f"未找到user_id为{user_id}的用户数据")

        # 提取用户投资档案
        user_investment_profile = user_doc.get("user_investment_profile")
        if not user_investment_profile:
            raise ValueError(f"用户{user_id}的user_investment_profile字段为空")

    except Exception as e:
        raise Exception(f"查询用户数据失败：{str(e)}")

    # 3. 生成用户规则
    try:
        user_rule_list = get_user_rule(user_investment_profile)
    except Exception as e:
        raise Exception(f"生成用户规则失败：{str(e)}")

    # 4. 存储规则到user_rule集合
    try:
        # 构造存储的文档结构（包含元信息，便于后续维护）
        rule_doc = {
            "user_id": user_id,  # 关联用户ID
            "rule_list": user_rule_list,  # 生成的规则列表
            "create_time": datetime.datetime.now(),  # 创建时间
            "update_time": datetime.datetime.now(),  # 更新时间
            "status": "active"  # 规则状态：active/expired等
        }

        # 先删除该用户已有的规则（可选，根据业务需求决定是覆盖还是追加）
        rule_collection.delete_many({"user_id": user_id})

        # 插入新规则
        insert_result = rule_collection.insert_one(rule_doc)
        print(f"用户{user_id}的规则已成功存储，文档ID：{insert_result.inserted_id}")
        return insert_result.inserted_id

    except Exception as e:
        raise Exception(f"存储用户规则失败：{str(e)}")

def get_recent_events_by_user_rule(user_id):
    """
    根据用户ID获取其规则匹配的近5分钟内的事件数据（related_stock直接匹配symbol）
    :param user_id: 用户唯一标识
    :return: 结构化的匹配结果
    """
    # 1. 入参校验
    if not user_id:
        raise ValueError("user_id不能为空")

    # 2. 计算时间范围：当前时间前5分钟
    now = datetime.datetime.now()
    five_minutes_ago = now - datetime.timedelta(minutes=5)
    five_minutes_ago_str = five_minutes_ago.strftime("%Y-%m-%d %H:%M:%S")

    # 3. 查询用户的规则列表
    try:
        user_rule_doc = rule_collection.find_one({"user_id": user_id}, {"rule_list": 1})
        if not user_rule_doc or not user_rule_doc.get("rule_list"):
            return {
                "user_id": user_id,
                "rule_matched_count": 0,
                "total_event_count": 0,
                "matched_events": []
            }
        user_rule_list = user_rule_doc["rule_list"]
        print(f"user_rule_list:{user_rule_list}")
    except Exception as e:
        raise Exception(f"查询用户规则失败：{str(e)}")

    # 4. 遍历规则，匹配近5分钟的事件
    matched_result = {
        "user_id": user_id,
        "rule_matched_count": 0,
        "total_event_count": 0,
        "matched_events": []
    }

    for rule in user_rule_list:
        # 提取规则中的关键匹配条件（统一转小写，避免大小写不一致）
        rule_event_type = rule.get("event_type", "").lower()
        rule_event_subtype = rule.get("event_subtype", "").lower()
        rule_related_stock = rule.get("related_stock", "").strip()

        # 跳过条件不完整的规则
        if not all([rule_event_type, rule_event_subtype, rule_related_stock]):
            continue

        # 构造事件查询条件（核心修改：仅匹配symbol字段）
        query_conditions = {
            "event_type": rule_event_type,          # 匹配事件类型
            "event_subtype": rule_event_subtype,    # 匹配事件子类型
            "symbol": rule_related_stock,           # 直接匹配symbol字段（不再做分支处理）
            "event_time": {"$gte": five_minutes_ago_str}  # 时间范围过滤
        }

        # 查询事件集合
        try:
            # 按event_time降序排列（最新的事件在前）
            events_cursor = event_collection.find(query_conditions).sort("event_time", -1)
            # 转换为列表并二次精确校验时间
            matched_events = []
            for event in events_cursor:
                try:
                    event_time = datetime.datetime.strptime(event["event_time"], "%Y-%m-%d %H:%M:%S")
                    if event_time >= five_minutes_ago:
                        # 转换ObjectId为字符串，方便JSON序列化
                        event["_id"] = str(event["_id"])
                        matched_events.append(event)
                except ValueError as e:
                    print(f"事件{event.get('event_id')}的时间格式解析失败：{str(e)}，跳过该事件")
                    continue

            # 统计匹配结果
            if matched_events:
                matched_result["rule_matched_count"] += 1
                matched_result["total_event_count"] += len(matched_events)
                matched_result["matched_events"].append({
                    "rule": rule,
                    "events": matched_events
                })
        except Exception as e:
            print(f"查询规则[{rule_event_type}/{rule_event_subtype}/{rule_related_stock}]匹配的事件失败：{str(e)}")
            continue

    return matched_result


def generate_and_save_reminder(user_id):
    """
    生成用户事件提醒并落库（仅非“暂无提醒”的内容落库）
    :param user_id: 用户唯一标识
    :return: 落库统计结果（dict）
    """
    # 初始化统计结果
    stats = {
        "user_id": user_id,
        "total_rule_event_pairs": 0,  # 处理的规则-事件对总数
        "gpt_no_reminder_count": 0,   # GPT返回“暂无提醒”的数量
        "saved_reminder_count": 0,    # 成功落库的提醒数量
        "failed_count": 0,            # 处理失败的数量
        "saved_ids": []               # 落库的文档ID列表
    }

    # 1. 获取用户匹配的规则和事件
    try:
        matched_result = get_recent_events_by_user_rule(user_id)
#         matched_result = {
#   "user_id": "691ea11916441e5b365f450f",
#   "rule_matched_count": 1,
#   "total_event_count": 1,
#   "matched_events": [
#     {
#       "rule": {
#         "event_type": "Macro",
#         "event_subtype": "macro_央行政策",
#         "related_stock": "央行政策",
#         "event_description": "央行发布重要货币政策",
#         "trigger_condition": "中国人民银行宣布调整存款准备金率、基准利率或发布重要货币政策报告"
#       },
#       "events": [
#         {
#           "_id": "694518c001a14c7e13500a40",
#           "event_id": "央行政策_20251219_171930_macro_央行政策",
#           "event_time": "2025-12-19 17:19:30",
#           "data_source": "akshare",
#           "event_description": "【央行政策】【意大利议会委员会批准将黄金储备归为人民财产】意大利议会一个委员会批准了一项针对明年预算的修正案，该修正案声明该国央行持有的黄金储备属于“人民”，此举无视了欧洲...",
#           "event_subtype": "macro_央行政策",
#           "event_type": "macro",
#           "impact_level": "critical",
#           "raw_data": {
#             "新闻时间": "2025-12-19 17:19:30",
#             "新闻内容": "【意大利议会委员会批准将黄金储备归为人民财产】意大利议会一个委员会批准了一项针对明年预算的修正案，该修正案声明该国央行持有的黄金储备属于“人民”，此举无视了欧洲央行的批评。自上个月意大利总理梅洛尼领导的右翼政党“意大利兄弟党”提出这项修正案以来，欧洲央行已两次介入，警告称此举可能损害意大利央行的独立性。意大利参议院预算委员会周五批准的文本中写道：“意大利央行资产负债表上所示的，由其管理和持有的黄金储备，属于意大利人民。”这项拟议立法在生效前还需要经过多个批准程序，其中包含旨在澄清其不会凌驾于保护央行独立性的欧盟规则之上的措辞。意大利央行在其网站上表示，它拥有世界第三大国家黄金储备，仅次于美国和德国。",
#             "匹配分类": "央行政策",
#             "匹配关键词": [
#               "央行",
#               "欧洲央行"
#             ],
#             "匹配数量": 2
#           },
#           "sentiment": "neutral",
#           "symbol": "央行政策",
#           "trigger_rule": {
#             "metric": "宏观关键词匹配数",
#             "value": 2.0,
#             "threshold": 1.0,
#             "operator": ">=",
#             "calc_formula": ""
#           }
#         }
#       ]
#     }
#   ]
# }
        matched_items = matched_result["matched_events"]
        if not matched_items:
            print(f"用户{user_id}暂无匹配的规则和事件，无需生成提醒")
            return stats
    except Exception as e:
        raise Exception(f"获取用户匹配规则/事件失败：{str(e)}")

    # 2. 遍历每个规则-事件对（每个规则取第一个事件，保证一对一）
    for item in matched_items:
        rule = item["rule"]
        events = item["events"]
        # 取第一个事件（按时间降序，最新的事件），实现“每个规则对应一个事件”
        if not events:
            continue
        event = events[0]
        stats["total_rule_event_pairs"] += 1

        # 3. 调用GPT生成提醒
        try:
            reminder_content = gpt(rule, event)
            print(f"规则[{rule['event_type']}/{rule['event_subtype']}]GPT返回：{reminder_content}")

            # 4. 判断是否落库（非“暂无提醒”则落库）
            if reminder_content == "暂无提醒":
                stats["gpt_no_reminder_count"] += 1
                continue

            # 构造落库数据（严格按你提供的字段格式）
            save_data = {
                "trade_date": event["event_time"],  # 事件发生时间
                "company_of_interest": event["symbol"],  # 标的代码
                "report": reminder_content,  # GPT生成的提醒内容
                "label": "事件提醒",  # 固定标签
                "user_id": user_id,  # 当前用户ID
                "is_read": "NO",  # 未读状态
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 提醒生成时间
            }

            # 5. 插入stock_collection
            insert_result = stock_collection.insert_one(save_data)
            stats["saved_reminder_count"] += 1
            stats["saved_ids"].append(str(insert_result.inserted_id))
            print(f"提醒已落库，文档ID：{insert_result.inserted_id}")

        except Exception as e:
            print(f"处理规则[{rule['event_type']}/{rule['event_subtype']}]失败：{str(e)}")
            stats["failed_count"] += 1
            continue

    return stats

class UserRuleTask(BaseTask):
    def run(self):
        # 查询所有用户
        try:
            users = user_collection.find({"status": "生效"})

            # 3. 处理结果：将ObjectId类型的_id转为字符串
            active_users = convert_objectId(list(users))
            print(f"成功查询到 {len(active_users)} 个生效用户")
            for active_user in active_users:
                temp_results = generate_and_save_reminder(active_user['_id'])
                print(json.dumps(temp_results, ensure_ascii=False, indent=2))
        except Exception as e:
            print("及时提醒定时任务执行失败\n")
            print(str(e))


# 测试示例（可选）
if __name__ == "__main__":
    # try:
    #     # 替换为实际的用户ID
    #     run(user_id="691ea11916441e5b365f450f")
    # except Exception as e:
    #     print(f"执行失败：{str(e)}")

    results = generate_and_save_reminder(user_id="691ea11916441e5b365f450f")
    print(json.dumps(results,ensure_ascii=False,indent=2))