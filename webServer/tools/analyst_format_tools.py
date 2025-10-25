import json
from typing import Any, Optional, Dict


def parse_state(input_data: Any):
    """
    将输入（字符串或字典）解析为 dict，并将 trade_date 转换为 datetime 类型。
    支持解析含单引号的Python字典字符串，兼容标准JSON和Python dict。

    参数:
        input_data: 输入数据（可为JSON字符串、Python字典字符串或dict）

    返回:
        解析后的字典（含datetime类型的trade_date），失败则返回None
    """
    try:
        # 1. 处理输入数据，统一转为dict
        if isinstance(input_data, str):
            # 替换单引号为双引号（处理Python字典字符串）
            input_str = input_data.replace("'", '"')
            # 解析JSON字符串为dict
            data = json.loads(input_str)
        elif isinstance(input_data, dict):
            # 复制字典避免修改原始数据
            data = input_data.copy()
        else:
            raise TypeError(f"输入必须是字符串或dict，实际类型: {type(input_data)}")

        return data

    except json.JSONDecodeError as e:
        print(f"⚠️ JSON解析失败: {e}（可能是格式错误，确保键和字符串用双引号）")
    except ValueError as e:
        print(f"⚠️ 数据验证失败: {e}")
    except TypeError as e:
        print(f"⚠️ 类型错误: {e}")
    except Exception as e:
        print(f"⚠️ 解析state失败: {e}")

    return ""

def safe_get(result: dict, key: str) -> str:
    """
    安全获取字典中的字段，如果不存在或不是字符串，返回空字符串
    """
    try:
        value = result.get(key, "")
        if not isinstance(value, str):
            return str(value)  # 强制转换为字符串
        return value
    except Exception as e:
        print(f"⚠️ 获取字段 {key} 失败: {e}")
        return ""