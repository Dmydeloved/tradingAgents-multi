from webServer.utils.mongodb import get_mongo_client
from webServer.utils.redis_client import RedisClient

mongo_client = get_mongo_client()
mongo_db = mongo_client['multiAgent']

redis_client = RedisClient()