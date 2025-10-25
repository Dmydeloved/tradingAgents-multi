from webServer.utils.mongodb import get_mongo_client

mongo_client = get_mongo_client()
mongo_db = mongo_client['multiAgent']