import time
import random
import string
import hashlib
import os
import socket


def generate_session_id(prefix: str = "", length: int = 32) -> str:
    """
    生成唯一会话ID

    组成规则（可根据需求调整）：
    1. 前缀（可选，如业务标识）
    2. 时间戳（精确到毫秒，确保时序性）
    3. 随机字符串（增加随机性）
    4. 机器/进程标识（避免分布式环境冲突）

    参数:
        prefix: 会话ID前缀（如"stock_watcher_"）
        length: 最终会话ID的总长度（建议≥20，过短可能影响唯一性）

    返回:
        唯一会话ID字符串
    """
    # 1. 基础组成部分
    timestamp = f"{int(time.time() * 1000):013d}"  # 13位毫秒级时间戳（确保时序）

    # 2. 机器/进程标识（简化版，避免同一机器多进程冲突）
    pid = os.getpid()  # 进程ID
    hostname = socket.gethostname()  # 机器名（分布式环境可区分不同服务器）
    machine_hash = hashlib.md5(hostname.encode()).hexdigest()[:4]  # 机器名哈希前4位
    process_id = f"{pid % 1000:03d}"  # 进程ID后3位（简化）
    machine_process = f"{machine_hash}{process_id}"  # 7位标识

    # 3. 随机字符串（补足长度，增强唯一性）
    remaining_length = length - len(prefix) - len(timestamp) - len(machine_process)
    if remaining_length < 4:  # 确保随机部分至少4位，避免长度不足
        remaining_length = 4
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=remaining_length))

    # 4. 拼接所有部分
    session_id = f"{prefix}{timestamp}{machine_process}{random_str}"

    # 截取或补全到指定长度（防止超长）
    return session_id[:length]


# 示例使用
if __name__ == "__main__":
    # 生成带前缀的会话ID（用于股票盯盘场景）
    stock_session = generate_session_id(prefix="stock_", length=32)
    print("股票盯盘会话ID:", stock_session)

    # 生成默认会话ID
    default_session = generate_session_id()
    print("默认会话ID:", default_session)

    # 测试并发唯一性（模拟10个并发会话）
    sessions = [generate_session_id(prefix="test_") for _ in range(10)]
    print("\n10个会话ID是否唯一:", len(set(sessions)) == 10)