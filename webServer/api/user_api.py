import json
from operator import index

import bcrypt
import jwt
import time
from flask import Blueprint, request, g

from webServer.services.scheduler.tasks.user_rule import run
from webServer.tools.mongodb_tools import convert_objectId, str_to_objectid
from webServer.utils import mongo_db
from webServer.utils.response import success, fail
from functools import wraps

# 连接用户集合
user_collection = mongo_db['user']
user_rule_collection = mongo_db['user_rule']
# JWT 密钥（建议配置到环境变量）
JWT_SECRET = 'klm9dPyYddfJvjF7KZJ8By8iakO2NJLoUsfKjdj1u7YXsdSIv4aoeXhMMGUhF8iciHvVJMXRxy2BNGQloanFvg'
JWT_EXPIRE = 3600 * 24  # token有效期24小时

user_bp = Blueprint("user", __name__)


# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return fail(msg="请提供token", code=401)
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get('user_id')
            g.user_id = user_id
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return fail(msg="token已过期", code=401)
        except Exception as e:
            return fail(msg="token无效", code=401)

    return decorated_function


@user_bp.route("/register", methods=["POST"])
def user_register():
    """
    用户注册接口
    请求示例：
    {
        "name": "张三",
        "account": "zhangsan",
        "password": "123456",
        "user_investment_profile": {
            "personalized_investment_goals": {...},
            "current_holdings": {...},
            "watchlist": {...}
        }
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        name = data.get("name")
        account = data.get("account")
        password = data.get("password")
        user_invest = data.get("user_investment_profile", {})

        # 检查账号是否已存在
        if user_collection.count_documents({"account": account}):
            return fail(msg="账号已存在", code=400)

        # 密码加密
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # 构造用户数据
        user_data = {
            "name": name,
            "account": account,
            "password": hashed_pw.decode('utf-8'),
            "user_investment_profile": json.dumps(user_invest, ensure_ascii=False),
            "status": "生效",
            "date": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # 插入数据库
        result = user_collection.insert_one(user_data)
        app.logger.info(f"用户注册成功，ID: {result.inserted_id}")
        return success(msg="注册成功")

    except Exception as e:
        app.logger.error(f"用户注册失败: {e}")
        return fail(data=str(e))


@user_bp.route("/login", methods=["POST"])
def user_login():
    """
    用户登录接口
    请求示例：
    {
        "account": "zhangsan",
        "password": "123456"
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        account = data.get("account")
        password = data.get("password")

        # 查询用户
        user = user_collection.find_one({"account": account})
        if not user:
            return fail(msg="账号或密码错误", code=401)

        # 验证密码
        if not bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
            return fail(msg="账号或密码错误", code=401)

        # 生成token
        token = jwt.encode(
            {"user_id": str(user["_id"]), "exp": int(time.time()) + JWT_EXPIRE},
            JWT_SECRET,
            algorithm="HS256"
        )
        app.logger.info(f"用户 {account} 登录成功")
        return success(data={"token": token, "name": user["name"]})

    except Exception as e:
        app.logger.error(f"用户登录失败: {e}")
        return fail(data=str(e))


@user_bp.route("/investment/profile", methods=["GET"])
@login_required
def get_investment_profile():
    """
    获取当前用户投资配置
    请求头：Authorization: Bearer {token}
    """
    from webServer.run import app
    try:
        user = user_collection.find_one({"_id": str_to_objectid(g.user_id)})
        if not user:
            return fail(msg="用户不存在", code=404)
        user = convert_objectId(user)
        # 解析JSON字符串为字典
        import json
        user["user_investment_profile"] = json.loads(user["user_investment_profile"])
        app.logger.info(f"用户 {g.user_id} 获取投资配置成功")
        return success(data=user)

    except Exception as e:
        app.logger.error(f"获取投资配置失败: {e}")
        return fail(data=str(e))

@user_bp.route("/rules", methods=["GET"])
@login_required
def get_user_rules():
    """
    获取当前用户投资配置
    请求头：Authorization: Bearer {token}
    """
    from webServer.run import app
    try:
        user_rule = user_rule_collection.find_one({"user_id": g.user_id})
        if not user_rule:
            return fail(msg="用户规则不存在", code=404)
        user_rule = convert_objectId(user_rule)
        # 解析JSON字符串为字典
        import json
        rules = user_rule["rule_list"]
        app.logger.info(f"用户 {g.user_id} 获取盯盘规则 rules:{rules}")
        return success(data=rules)

    except Exception as e:
        app.logger.error(f"获取投资配置失败: {e}")
        return fail(data=str(e))

@user_bp.route("/investment/update_profile", methods=["POST"])
@login_required
def update_investment_profile():
    """
    更新当前用户投资配置
    请求头：Authorization: Bearer {token}
    请求示例：
    {
        "personalized_investment_goals": {...},
        "current_holdings": {...},
        "watchlist": {...}
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        invest_str = data.get("user_investment_profile",{})
        # report_template = data.get("user_report_template","")
        # 转换为JSON字符串存储
        if not invest_str:
            return fail(msg="更新失败，配置数据不存在")
        invest_str = json.dumps(invest_str, ensure_ascii=False, indent=2)

        result = user_collection.update_one(
            {"_id": str_to_objectid(g.user_id)},
            {"$set": {"user_investment_profile": invest_str}}
        )
        if result.modified_count == 0:
            return fail(msg="更新失败，用户不存在或数据未变更")

        app.logger.info(f"用户 {g.user_id} 更新投资配置成功")
        run(g.user_id)
        return success(msg="更新成功")

    except Exception as e:
        app.logger.error(f"更新投资配置失败: {e}")
        return fail(data=str(e))

@user_bp.route("/update/user_rules", methods=["POST"])
@login_required
def update_user_rules():
    """
    更新当前用户投资配置
    请求头：Authorization: Bearer {token}
    请求示例：
    {
        'rule_list': {
            event_type: "Macro",
            event_subtype: "macro_央行政策",
            related_stock: "央行政策",
            event_description: "央行发布重要货币政策",
            trigger_condition: "中国人民银行宣布调整存款准备金率、基准利率或发布重要货币政策报告"
        }
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        user_rules = data.get("rule_list","")
        if user_rules != "":
            result = user_rule_collection.update_one(
                {"_id": str_to_objectid(g.user_id)},
                {"$set": {"rule_list": user_rules}}
            )
        else:
            result = {'modified_count': 0}
        if result.modified_count == 0:
            return fail(msg="更新失败，用户不存在或数据未变更")

        app.logger.info(f"用户 {g.user_id} 更新用户规则成功")
        return success(msg="更新成功")

    except Exception as e:
        app.logger.error(f"更新投资配置失败: {e}")
        return fail(data=str(e))

@user_bp.route("/update/report_template", methods=["POST"])
@login_required
def update_report_template():
    """
    更新当前用户投资配置
    请求头：Authorization: Bearer {token}
    请求示例：
    {
        "personalized_investment_goals": {...},
        "current_holdings": {...},
        "watchlist": {...}
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        report_template = data.get("user_report_template","")
        result = user_collection.update_one(
            {"_id": str_to_objectid(g.user_id)},
            {"$set": {"report_template": report_template}}
        )
        if result.modified_count == 0:
            return fail(msg="更新失败，用户不存在或数据未变更")

        app.logger.info(f"用户 {g.user_id} 更新报告模版成功")
        return success(msg="更新成功")

    except Exception as e:
        app.logger.error(f"更新投资配置失败: {e}")
        return fail(data=str(e))

@user_bp.route("/list", methods=["POST"])
def get_user_list():
    """
    分页查询用户集合数据
    请求示例：
    {
        "page": 1,
        "size": 10
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True) or {}
        page = int(data.get("page", 1))
        size = int(data.get("size", 10))
        skip = (page - 1) * size

        # 排除密码字段
        projection = {"password": 0}

        # 查询总数
        total = user_collection.count_documents({})

        # 查询分页数据
        cursor = user_collection.find({}, projection).skip(skip).limit(size).sort("_id", -1)
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
        app.logger.info(f"分页查询用户集合成功：{result}")
        return success(result)

    except Exception as e:
        app.logger.error(f"分页查询用户集合失败: {e}")
        return fail(data=str(e))


# ---------------------- 新增修改用户信息接口 ----------------------
@user_bp.route("/update_info", methods=["POST"])
@login_required
def update_user_info():
    """
    修改用户名称和/或密码
    请求头：Authorization: Bearer {token}
    请求示例1（仅改名称）：
    {
        "name": "李四"
    }
    请求示例2（仅改密码）：
    {
        "old_password": "123456",
        "new_password": "654321"
    }
    请求示例3（改名称+密码）：
    {
        "name": "李四",
        "old_password": "123456",
        "new_password": "654321"
    }
    """
    from webServer.run import app
    try:
        data = request.get_json(force=True)
        new_name = data.get("name")
        old_password = data.get("old_password")
        new_password = data.get("new_password")

        # 1. 校验参数：如果传了新密码必须传旧密码，反之亦然
        if (old_password and not new_password) or (new_password and not old_password):
            return fail(msg="修改密码时必须同时提供旧密码和新密码", code=400)

        # 2. 查询当前用户信息
        user = user_collection.find_one({"_id": str_to_objectid(g.user_id)})
        if not user:
            return fail(msg="用户不存在", code=404)

        # 3. 构造更新数据字典
        update_data = {}

        # 4. 处理名称修改
        if new_name:
            update_data["name"] = new_name

        # 5. 处理密码修改
        if old_password and new_password:
            # 验证旧密码
            if not bcrypt.checkpw(old_password.encode('utf-8'), user["password"].encode('utf-8')):
                return fail(msg="旧密码错误", code=401)
            # 加密新密码
            hashed_new_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            update_data["password"] = hashed_new_pw.decode('utf-8')

        # 6. 校验是否有需要更新的数据
        if not update_data:
            return fail(msg="未提供需要修改的信息", code=400)

        # 7. 更新数据库
        result = user_collection.update_one(
            {"_id": str_to_objectid(g.user_id)},
            {"$set": update_data}
        )

        # 8. 校验更新结果
        if result.modified_count == 0:
            return fail(msg="更新失败，数据未变更或用户不存在", code=400)

        app.logger.info(f"用户 {g.user_id} 修改个人信息成功，更新内容：{list(update_data.keys())}")
        return success(msg="信息修改成功")

    except Exception as e:
        app.logger.error(f"用户 {g.user_id} 修改个人信息失败: {e}")
        return fail(data=str(e))