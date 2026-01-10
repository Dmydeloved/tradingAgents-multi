from typing import List, Dict
from webServer.utils import redis_client


class ConversationManager:

    def __init__(self, max_history: int = 20):
        """
        :param redis_client: 注入你的 RedisClient
        :param max_history: 最大历史条数（防止 token 爆炸）
        """
        self.redis = redis_client
        self.max_history = max_history

    def _make_key(self, session_id: str):
        return f"chat:history:{session_id}"

    # -------------------------
    # 获取历史
    # -------------------------
    def get_history(self, session_id: str) -> List[Dict]:
        key = self._make_key(session_id)
        history = self.redis.get(key)
        return history

    # -------------------------
    # 保存历史
    # -------------------------
    def save_history(self, session_id: str, history: List[Dict]):
        # 压缩历史长度
        if len(history) > self.max_history:
            history = [history[0]] + history[-(self.max_history - 1):]

        self.redis.set(self._make_key(session_id), history)

    # -------------------------
    # 追加用户消息
    # -------------------------
    def add_user_message(self, session_id: str, content: str):
        history = self.get_history(session_id)
        if history is None:
            history = []
        history.append({"role": "user", "content": content})
        self.save_history(session_id, history)

    # -------------------------
    # 追加模型回复
    # -------------------------
    def add_assistant_message(self, session_id: str, content: str):
        history = self.get_history(session_id)
        history.append({"role": "assistant", "content": content})
        self.save_history(session_id, history)

    # -------------------------
    # 获取会话上下文（用于 LLM 调用）
    # -------------------------
    def build_messages(self, session_id: str) -> List[Dict]:
        return self.get_history(session_id)

    # -------------------------
    # 根据 user_id 获取所有会话记录
    # -------------------------
    def get_all_sessions_by_user(self, user_id: str) -> Dict[str, List[Dict]]:
        pattern = f"chat:history:{user_id}_*"

        sessions = {}
        for key in self.redis.scan_iter(pattern):
            raw = key.split("chat:history:")[1]  # 例如 "1001_abcd1234"
            session_id = raw[len(user_id) + 1:]  # 去掉 "1001_" 只保留 "abcd1234"
            sessions[session_id] = self.redis.get(key)

        return sessions
