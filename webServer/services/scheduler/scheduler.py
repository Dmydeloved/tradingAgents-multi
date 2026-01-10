# services/scheduler/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from flask import current_app, Flask
from webServer.config import scheduler_config  # 假设 utils 中有日志和配置工具
from webServer.services.scheduler.tasks.StockAnalysisTask import StockAnalysisTask
from datetime import datetime
from webServer.services.scheduler.tasks.after_stock_analysis import AfterStockAnalysisTask
from webServer.services.scheduler.tasks.before_stock_analysis import BeforeStockAnalysisTask
from webServer.services.scheduler.tasks.events_find_task import EventReminderTask
from webServer.services.scheduler.tasks.noon_stock_analysis import NoonStockAnalysisTask
from webServer.services.scheduler.tasks.user_rule import UserRuleTask

scheduler = None  # 全局调度器实例


def init_scheduler(app: Flask) -> None:
    """初始化定时任务调度器，并注册任务"""
    global scheduler
    if hasattr(app, 'scheduler') and app.scheduler.running:
        return
    scheduler = BackgroundScheduler()
    logger = app.logger

    # 从配置加载任务调度规则
    schedule_config = scheduler_config.load_schedule()

    # 注册任务
    for task_config in schedule_config.get("tasks", []):
        task_id = task_config["task_id"]
        if scheduler.get_job(task_id):
            logger.error(f"任务 {task_id} 已存在，跳过重复注册")
            continue
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
        # def task_wrapper(*args, **kwargs):
        #     with app.app_context():
        #         task = task_cls(*args, **kwargs)
        #         task.logger = app.logger
        #         task.run()
        def task_wrapper(*args, task_cls=task_cls, **kwargs):  # 关键修改：添加默认参数
            with app.app_context():
                task = task_cls(*args, **kwargs)  # 使用绑定的默认参数
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
    for job in scheduler.get_jobs():
        logger.info(f"任务ID: {job.id}, 名称: {job.name}, 下次执行时间: {job.next_run_time}, 状态: {job}")


def _get_task_class(task_id: str):
    """根据任务ID获取任务类"""
    task_map = {
        "before_stock_analysis": StockAnalysisTask,
        "noon_stock_analysis": StockAnalysisTask,
        "after_stock_analysis": StockAnalysisTask,
        "user_rule_task": UserRuleTask,
        "events_find_task": EventReminderTask
    }
    task_class = task_map.get(task_id)
    # 打印task_id及对应类名称（未找到时提示"未匹配到任务类"）
    class_name = task_class.__name__ if task_class else "未匹配到任务类"
    print(f"task_id: {task_id} -> 对应任务类: {class_name}")
    return task_class
#
# from apscheduler.schedulers.background import BackgroundScheduler
# from apscheduler.triggers.cron import CronTrigger
# from apscheduler.triggers.interval import IntervalTrigger
# from apscheduler.executors.pool import ThreadPoolExecutor
# from flask import Flask
# from datetime import datetime, time
# from pytz import timezone
#
# from webServer.config import scheduler_config
# from webServer.services.scheduler.tasks.StockAnalysisTask import StockAnalysisTask
# from webServer.services.scheduler.tasks.events_find_task import EventReminderTask
# from webServer.services.scheduler.tasks.user_rule import UserRuleTask
#
# TZ = timezone("Asia/Shanghai")
# scheduler = None
#
#
# # =========================
# # 启动补跑工具函数
# # =========================
# def should_run_on_start(cron_expr: str, now: datetime) -> bool:
#     """
#     判断是否需要在启动时补跑一次
#     规则：
#     - 仅支持形如：minute hour * * 1-5
#     """
#     parts = cron_expr.split()
#     if len(parts) != 5:
#         return False
#
#     minute, hour, _, _, dow = parts
#
#     if dow != "1-5":
#         return False
#
#     try:
#         cron_time = time(int(hour), int(minute))
#     except ValueError:
#         return False
#
#     # 当前是工作日，且已经过了 cron 时间
#     return now.weekday() < 5 and now.time() > cron_time
#
#
# def run_task_once(app: Flask, task_cls, args: dict, task_name: str):
#     """立即补跑一次任务"""
#     app.logger.info(f"【启动补跑】执行任务：{task_name}")
#     with app.app_context():
#         task = task_cls(args)
#         task.logger = app.logger
#         task.run()
#
#
# # =========================
# # Scheduler 初始化
# # =========================
# def init_scheduler(app: Flask) -> None:
#     global scheduler
#
#     if hasattr(app, "scheduler") and app.scheduler.running:
#         return
#
#     scheduler = BackgroundScheduler(
#         timezone=TZ,
#         executors={
#             "default": ThreadPoolExecutor(max_workers=20)
#         },
#         job_defaults={
#             "coalesce": True,
#             "max_instances": 1,
#             "misfire_grace_time": 300
#         }
#     )
#     app.scheduler = scheduler
#     logger = app.logger
#
#     now = datetime.now(TZ)
#     schedule_data = scheduler_config.load_schedule()
#
#     for task_config in schedule_data.get("tasks", []):
#         task_id = task_config["task_id"]
#
#         if not scheduler_config.TASK_SWITCH.get(task_id, False):
#             logger.info(f"任务【{task_id}】已关闭，跳过")
#             continue
#
#         task_cls = _get_task_class(task_id)
#         if not task_cls:
#             logger.error(f"未找到任务类：{task_id}")
#             continue
#
#         # ===== 解决闭包问题 =====
#         def make_task_wrapper(task_cls):
#             def task_wrapper(task_args=None):
#                 with app.app_context():
#                     task = task_cls(task_args or {})
#                     task.logger = app.logger
#                     task.run()
#             return task_wrapper
#
#         task_wrapper = make_task_wrapper(task_cls)
#         task_args = task_config.get("args", {})
#
#         # ===== Cron 任务 =====
#         if "cron" in task_config:
#             cron_expr = task_config["cron"]
#             trigger = CronTrigger.from_crontab(cron_expr, timezone=TZ)
#
#             scheduler.add_job(
#                 func=task_wrapper,
#                 trigger=trigger,
#                 id=task_id,
#                 name=task_config.get("name", task_id),
#                 args=[task_args]
#             )
#
#             logger.info(f"注册 Cron 任务【{task_id}】，规则：{cron_expr}")
#
#             # ===== 启动补跑判断 =====
#             if should_run_on_start(cron_expr, now):
#                 run_task_once(app, task_cls, task_args, task_id)
#
#         # ===== Interval 任务 =====
#         elif "interval" in task_config:
#             trigger = IntervalTrigger(seconds=task_config["interval"])
#             scheduler.add_job(
#                 func=task_wrapper,
#                 trigger=trigger,
#                 id=task_id,
#                 name=task_config.get("name", task_id),
#                 args=[task_args],
#                 next_run_time=now
#             )
#             logger.info(f"注册 Interval 任务【{task_id}】，间隔 {task_config['interval']} 秒")
#
#     scheduler.start()
#     logger.info("定时任务调度器启动成功")
#
#     # 打印最终状态
#     for job in scheduler.get_jobs():
#         logger.info(
#             f"任务ID: {job.id}, "
#             f"名称: {job.name}, "
#             f"下次执行时间: {job.next_run_time}, "
#             f"Trigger: {job.trigger}"
#         )
#
#
# def _get_task_class(task_id: str):
#     task_map = {
#         "before_stock_analysis": StockAnalysisTask,
#         "noon_stock_analysis": StockAnalysisTask,
#         "after_stock_analysis": StockAnalysisTask,
#         "user_rule_task": UserRuleTask,
#         "events_find_task": EventReminderTask
#     }
#     task_class = task_map.get(task_id)
#     name = task_class.__name__ if task_class else "未匹配到任务类"
#     print(f"task_id: {task_id} -> 对应任务类: {name}")
#     return task_class
#
