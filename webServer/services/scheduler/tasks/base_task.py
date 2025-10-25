# services/scheduler/tasks/base_task.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTask(ABC):
    """任务基类，所有定时任务必须继承"""
    def __init__(self, args: Dict[str, Any] = None):
        self.args = args or {}

    @abstractmethod
    def run(self) -> None:
        """任务执行逻辑（子类必须实现）"""
        pass

    def before_run(self) -> None:
        """任务执行前的准备"""
        from webServer.utils.logger import get_logger
        logger = get_logger()
        logger.info(f"任务【{self.__class__.__name__}】开始执行，参数：{self.args}")

    def after_run(self) -> None:
        """任务执行后的清理"""
        from webServer.utils.logger import get_logger
        logger = get_logger()
        logger.info(f"任务【{self.__class__.__name__}】执行完成")