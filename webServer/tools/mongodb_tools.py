# ===== ObjectId 转字符串 =====
def convert_objectId(data):
    if isinstance(data, list):
        return [{**item, "_id": str(item["_id"])} for item in data]
    elif isinstance(data, dict):
        data["_id"] = str(data["_id"])
        return data
    return data