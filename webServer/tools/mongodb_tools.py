from bson import ObjectId  # 需导入bson的ObjectId类型


def convert_objectId(data):
    """
    转换MongoDB的ObjectId为字符串
    支持：列表（含多个文档）、单个文档（字典）、单独的_id（ObjectId或字符串）
    """
    # 1. 处理列表（多个文档）
    if isinstance(data, list):
        return [{**item, "_id": str(item["_id"])} for item in data if "_id" in item]

    # 2. 处理单个文档（字典）
    elif isinstance(data, dict):
        if "_id" in data:
            data["_id"] = str(data["_id"])
        return data

    # 其他类型直接返回
    return data

def str_to_objectid(id_str):
    """
    将字符串转换为MongoDB的ObjectId类型
    :param id_str: 待转换的字符串（需符合ObjectId格式：24位十六进制字符）
    :return: 转换后的ObjectId对象，若转换失败返回None
    """
    try:
        # 校验字符串格式并转换
        if isinstance(id_str, str) and len(id_str) == 24:
            return ObjectId(id_str)
        else:
            # 长度不符，直接返回None
            return None
    except Exception as e:
        # 格式不符（如含非十六进制字符），返回None
        return None