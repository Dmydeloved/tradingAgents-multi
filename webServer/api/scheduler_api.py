from flask import Blueprint, request

from webServer.tools.mongodb_tools import convert_objectId
from webServer.utils import mongo_db
from webServer.utils.response import success, fail

collection = mongo_db['scheduler']

scheduler_bp = Blueprint("scheduler",__name__)

@scheduler_bp.route("/list",methods=["POST"])
def get_scheduler_list():
    """
    分页查询 scheduler 集合数据（从请求体中获取参数）
    请求示例：
    {
        "page": 1,
        "size": 10
    }
    """
    from webServer.run import app
    try:
        # 获取请求体
        data = request.get_json(force=True) or {}
        page = int(data.get("page", 1))
        size = int(data.get("size", 10))
        skip = (page - 1) * size

        # 查询总数
        total = collection.count_documents({})

        # 查询分页数据
        cursor = collection.find({}).skip(skip).limit(size).sort("_id", -1)
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
        app.logger.info(f"分页查询 scheduler 集合成功：{result}")
        return success(result)

    except Exception as e:
        app.logger.error(f"分页查询 scheduler 集合失败: {e}")
        return fail(data=str(e))