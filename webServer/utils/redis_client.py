import json
import redis
from typing import Any, Optional


class RedisClient:
    """
    简单 Redis 客户端（无连接池）
    - 启动时自动校验连接
    - 连接成功自动打印信息
    """

    def __init__(
        self,
        host: str = "8.130.110.113",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = "05280528",
        decode_responses: bool = True
    ):
        try:
            # 直接创建 Redis 实例（无连接池）
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
            )

            # 校验连接（重要）
            self.client.ping()

            print(f"✅ Redis Connected Successfully → {host}:{port}/{db}")

        except Exception as e:
            print("❌ Redis Connection Failed")
            print(f"Reason: {e}")
            # 将错误抛出，便于上层处理
            raise e

    # -------------------------
    # 字符串（含 JSON）
    # -------------------------
    def set(self, key: str, value: Any, ex: Optional[int] = None):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self.client.set(key, value, ex=ex)

    def get(self, key: str):
        value = self.client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return value

    def delete(self, key: str):
        return self.client.delete(key)

    # -------------------------
    # Hash
    # -------------------------
    def hset(self, key: str, field: str, value: Any):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self.client.hset(key, field, value)

    def hget(self, key: str, field: str):
        value = self.client.hget(key, field)
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return value

    def hgetall(self, key: str):
        result = self.client.hgetall(key)
        for k, v in result.items():
            try:
                result[k] = json.loads(v)
            except Exception:
                pass
        return result

    # -------------------------
    # List
    # -------------------------
    def lpush(self, key: str, value: Any):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self.client.lpush(key, value)

    def rpush(self, key: str, value: Any):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self.client.rpush(key, value)

    def lrange(self, key: str, start=0, end=-1):
        values = self.client.lrange(key, start, end)
        result = []
        for v in values:
            try:
                result.append(json.loads(v))
            except Exception:
                result.append(v)
        return result

    # -------------------------
    # Key 控制
    # -------------------------
    def expire(self, key: str, seconds: int):
        return self.client.expire(key, seconds)

    def exists(self, key: str) -> bool:
        return self.client.exists(key) == 1

    def keys(self, pattern: str = "*"):
        return self.client.keys(pattern)


    def scan_iter(self, match=None, count=None):
        """转发 redis 的 scan_iter"""
        return self.client.scan_iter(match=match, count=count)
