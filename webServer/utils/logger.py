import logging
from logging.handlers import RotatingFileHandler
import os

from flask import current_app


def setup_logger(app):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"), maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    file_handler.setFormatter(formatter)

    app.logger.addHandler(file_handler)

def get_logger():
    """获取日志记录器（优先使用 Flask 的 app.logger，否则用自定义 logger）"""
    try:
        return current_app.logger
    except RuntimeError:
        # 无应用上下文时，使用自定义 logger
        logger = logging.getLogger("flask_scheduler")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger