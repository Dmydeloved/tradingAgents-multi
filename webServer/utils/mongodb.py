from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
# mongo client
def get_mongo_client():
    """连接本地 MongoDB（无认证）"""
    try:
        # 默认连接本地 27017 端口，无用户名密码
        client = MongoClient(host='8.130.110.113', port=5701)

        # 检查连接是否成功
        client.admin.command('ping')  # 发送 ping 命令测试连接
        print("✅ MongoDB 连接成功")
        return client
    except ConnectionFailure as e:
        print("❌ MongoDB 连接失败:", e)
        return None