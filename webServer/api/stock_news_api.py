import datetime
import json
import time
import akshare as ak
import pandas as pd
from bson import json_util
from flask import Blueprint, request, g

from webServer.api.user_api import login_required
from webServer.tools.mongodb_tools import convert_objectId, str_to_objectid
from webServer.utils import mongo_db
from webServer.utils.response import success, fail
from functools import wraps

# 连接消息集合（假设集合名为message）
message_collection = mongo_db['stock_news']
events_collection = mongo_db['events']

# 创建蓝图
message_bp = Blueprint("message", __name__)



@message_bp.route("/list", methods=["POST"])
@login_required
def get_message_list():
    """
    分页查询消息列表，按时间倒序排列（最新在前）
    请求示例：
    {
        "page": 1,
        "size": 10
    }
    请求头：Authorization: Bearer {token}
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True) or {}
        page = int(data.get("page", 1))
        size = int(data.get("size", 10))
        skip = (page - 1) * size
        print(g.user_id)
        # 查询总数（可根据需要添加用户筛选条件）
        total = message_collection.count_documents({
            # 如需要只查询当前用户的消息，可添加以下条件
            "user_id": g.user_id
        })

        # 按时间倒序查询分页数据
        cursor = message_collection.find({
            # 如需要只查询当前用户的消息，可添加以下条件
            "user_id": g.user_id
        }).skip(skip).limit(size).sort("date", -1)

        results = convert_objectId(list(cursor))
        result = {
            "current_data": results,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            }
        }
        app.logger.info(f"用户 {g.user_id} 分页查询消息成功")
        return success(result)

    except Exception as e:
        app.logger.error(f"分页查询消息失败: {e}")
        return fail(data=str(e))


@message_bp.route("/update_read", methods=["POST"])
@login_required
def update_message_read():
    """
    根据ID修改消息is_read字段为yes
    请求示例：
    {
        "id": "60d21b4667d0d8992e610c85"
    }
    请求头：Authorization: Bearer {token}
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        message_id = data.get("id")

        if not message_id:
            return fail(msg="消息ID不能为空", code=400)

        # 转换为ObjectId
        try:
            obj_id = str_to_objectid(message_id)
        except Exception as e:
            return fail(msg="无效的消息ID格式", code=400)

        # 更新消息状态
        result = message_collection.update_one(
            {"_id": obj_id},
            {"$set": {
                "is_read": "yes",
                "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }}
        )

        if result.modified_count == 0:
            return fail(msg="更新失败，消息不存在或已为已读状态")

        app.logger.info(f"用户 {g.user_id} 更新消息 {message_id} 为已读成功")
        return success(msg="更新成功")

    except Exception as e:
        app.logger.error(f"更新消息已读状态失败: {e}")
        return fail(data=str(e))


@message_bp.route("/by_day", methods=["POST"])
@login_required
def get_message_by_day():
    """
    按天查询消息
    请求示例：
    {
        "day": "2025-10-30"
    }
    请求头：Authorization: Bearer {token}
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        day = data.get("day")

        if not day:
            return fail(msg="请提供日期参数day", code=400)

        # 验证日期格式
        try:
            day_struct = time.strptime(day, "%Y-%m-%d")
            day = time.strftime("%Y-%m-%d", day_struct)
        except ValueError:
            return fail(msg="日期格式错误，请使用YYYY-MM-DD", code=400)

        # 构造当天的时间范围
        start_time = f"{day} 00:00:00"
        end_time = f"{day} 23:59:59"

        print(g.user_id)
        # 查询当天的消息
        cursor = message_collection.find({
            # 如需要只查询当前用户的消息，可添加以下条件
            "user_id": g.user_id,
            "date": {
                "$gte": start_time,
                "$lte": end_time
            }
        }).sort("date", -1)

        print(json.dumps(cursor.explain(), indent=2, default=json_util.default))
        results = convert_objectId(list(cursor))
        app.logger.info(f"用户 {g.user_id} 查询 {day} 的消息成功")
        return success(data={
            "day": day,
            "count": len(results),
            "messages": results
        })

    except Exception as e:
        app.logger.error(f"按天查询消息失败: {e}")
        return fail(data=str(e))

# @message_bp.route("/big_message", methods=["GET"])
# def get_big_message():
#     """
#     获取全球股票信息（新浪），封装成列表，每个元素包含时间和内容
#     :return: 列表，每个元素为 {"时间": str, "内容": str}
#     """
#     try:
#         # 获取原始数据
#         stock_info_global_sina_df = ak.stock_info_global_sina()
#
#         # 初始化结果列表
#         result_list = []
#
#         # 遍历DataFrame的每一行
#         for idx, row in stock_info_global_sina_df.iterrows():
#             # 提取时间和内容（根据实际列名调整key）
#             item = {
#                 "时间": row.get("时间", "") if "时间" in row else "",  # 兼容列名可能的变化
#                 "内容": row.get("内容", "") if "内容" in row else ""
#             }
#             result_list.append(item)
#
#         return success(data={
#             "count": len(result_list),
#             "messages": result_list
#         })
#     except Exception as e:
#         return fail(data=str(e))
#
# @message_bp.route("/industry", methods=["GET"])
# def get_industry_board():
#     """
#     行业板块完整数据（东方财富）
#     返回 ak.stock_board_industry_name_em 的全部字段
#     """
#     try:
#         df = ak.stock_board_industry_name_em()
#
#         result = []
#
#         for idx, row in df.iterrows():
#             item = row.to_dict()
#             result.append(item)
#
#         return success(data=result)
#     except Exception as e:
#         return fail(data=str(e))
#
#
# @message_bp.route("/stock/news", methods=["GET"])
# def get_stock_news():
#     """
#     个股新闻核心数据
#     """
#     try:
#         # 1. 调用 akshare 接口获取数据
#         df = ak.stock_info_global_cls(symbol="全部")
#
#         # 2. 处理空数据场景
#         if df.empty:
#             return success(data=[], msg="暂无股票新闻数据")
#
#         # 3. 遍历数据并序列化（核心：处理时间类型）
#         result = []
#         for idx, row in df.iterrows():
#             item = row.to_dict()
#
#             # 4. 遍历所有字段，将时间/日期类型转为字符串
#             for key, value in item.items():
#                 # 处理 datetime/time 类型
#                 if isinstance(value, (pd.Timestamp, pd.Timedelta, datetime.datetime, datetime.time)):
#                     # 统一格式：日期时间转 "%Y-%m-%d %H:%M:%S"，纯时间转 "%H:%M:%S"
#                     if isinstance(value, (pd.Timestamp, datetime.datetime)):
#                         item[key] = value.strftime("%Y-%m-%d %H:%M:%S")
#                     elif isinstance(value, (datetime.time, pd.Timedelta)):
#                         item[key] = value.strftime("%H:%M:%S")
#                 # 处理 numpy 数值类型（可选，避免 JSON 序列化问题）
#                 elif "numpy" in str(type(value)):
#                     item[key] = value.item()
#
#             result.append(item)
#
#         return success(data=result)
#
#     except Exception as e:
#         # 打印详细异常（便于调试）
#         print(f"接口异常：{str(e)}")
#         return fail(data=str(e), msg="获取股票新闻失败")
#
# @message_bp.route("/market/emotion", methods=["GET"])
# def get_market_emotion():
#     """
#     市场情绪（雪球关注度）
#     """
#     try:
#         df = ak.stock_hot_follow_xq(symbol="最热门")
#
#         result = []
#         for idx, row in df.iterrows():
#             if int(idx) >= 1000:
#                 break
#             item=row.to_dict()
#             result.append(item)
#
#         return success(data=result)
#     except Exception as e:
#         return fail(data=str(e))

@message_bp.route("/macro", methods=["GET"])
def get_macro_message():

    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        start_time = f"{today} 00:00:00"
        end_time = f"{today} 23:59:59"
        query = {
            "event_type": "macro",
            "event_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }

        events = list(events_collection.find(query))
        results = convert_objectId(events)

        return success(data={
            "count": len(events),
            "messages": results
        })
    except Exception as e:
        return fail(data=str(e))

@message_bp.route("/industry", methods=["GET"])
def get_industry_message():
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        start_time = f"{today} 00:00:00"
        end_time = f"{today} 23:59:59"
        query = {
            "event_type": "industry",
            "event_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }

        events = list(events_collection.find(query))
        results = convert_objectId(events)

        return success(data={
            "count": len(events),
            "messages": results
        })
    except Exception as e:
        return fail(data=str(e))


@message_bp.route("/company", methods=["GET"])
def get_company_message():
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        start_time = f"{today} 00:00:00"
        end_time = f"{today} 23:59:59"
        query = {
            "event_type": "company",
            "event_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }

        events = list(events_collection.find(query))
        results = convert_objectId(events)

        return success(data={
            "count": len(events),
            "messages": results
        })
    except Exception as e:
        return fail(data=str(e))

@message_bp.route("/trading", methods=["GET"])
def get_trading_message():
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        start_time = f"{today} 00:00:00"
        end_time = f"{today} 23:59:59"
        query = {
            "event_type": "trading",
            "event_time": {
                "$gte": start_time,
                "$lte": end_time
            }
        }

        events = list(events_collection.find(query))
        results = convert_objectId(events)

        return success(data={
            "count": len(events),
            "messages": results
        })
    except Exception as e:
        return fail(data=str(e))