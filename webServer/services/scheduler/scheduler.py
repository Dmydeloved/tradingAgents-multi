# services/scheduler/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app, Flask
from webServer.config import scheduler_config  # 假设 utils 中有日志和配置工具
from webServer.services.scheduler.tasks.StockAnalysisTask import StockAnalysisTask
from datetime import datetime

scheduler = None  # 全局调度器实例


def init_scheduler(app: Flask) -> None:
    """初始化定时任务调度器，并注册任务"""
    global scheduler
    scheduler = BackgroundScheduler()
    logger = app.logger

    # 从配置加载任务调度规则
    schedule_config = scheduler_config.load_schedule()

    # 注册任务
    for task_config in schedule_config.get("tasks", []):
        task_id = task_config["task_id"]
        # 检查任务开关（假设 config 中有 TASK_SWITCH 配置）
        if not scheduler_config.TASK_SWITCH.get(task_id, False):
            logger.info(f"任务【{task_id}】已关闭，跳过注册")
            continue

        # 根据任务ID获取任务类
        task_cls = _get_task_class(task_id)
        if not task_cls:
            logger.error(f"未找到任务类：{task_id}")
            continue

        # 任务执行包装器：注入 Flask 应用上下文
        def task_wrapper(*args, **kwargs):
            with app.app_context():
                task = task_cls(*args, **kwargs)
                task.logger = app.logger
                task.run()

        # 根据配置添加定时规则（cron 或 interval）
        if "cron" in task_config:
            trigger = CronTrigger.from_crontab(task_config["cron"])
            scheduler.add_job(
                task_wrapper,
                trigger=trigger,
                args=[task_config.get("args", {})],
                name=task_config["name"],
                id=task_id
            )
            logger.info(f"注册Cron任务【{task_id}】，规则：{task_config['cron']}")
        elif "interval" in task_config:
            trigger = IntervalTrigger(seconds=task_config["interval"])
            scheduler.add_job(
                task_wrapper,
                trigger=trigger,
                args=[task_config.get("args", {})],
                name=task_config["name"],
                id=task_id,
                next_run_time = datetime.now()
            )
            logger.info(f"注册Interval任务【{task_id}】，间隔：{task_config['interval']}秒")

    # 启动调度器
    scheduler.start()
    logger.info("定时任务调度器启动成功")


def _get_task_class(task_id: str):
    """根据任务ID获取任务类"""
    task_map = {
        "stock_analysis": StockAnalysisTask
        # "data_sync": data_sync_task.DataSyncTask,
        # "report_generate": report_task.ReportGenerateTask
    }
    return task_map.get(task_id)