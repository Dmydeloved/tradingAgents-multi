# utils/config.py
import yaml
from pathlib import Path

# 项目根目录（根据实际情况调整）
BASE_DIR = Path(__file__).parent.parent

# 加载调度配置
def load_schedule():
    config_path = BASE_DIR / "config" / "schedule.yaml"  # 假设配置在 config/ 目录
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# 任务开关配置（可从环境变量或配置文件读取）
TASK_SWITCH = {
    "data_sync": True,
    "report_generate": True,
    "stock_analysis": True,
    "before_stock_analysis":True,
    "noon_stock_analysis": True,
    "after_stock_analysis": True,
    "user_rule_task": True,
    "events_find_task": True
}

if __name__ == "__main__":
    config_yaml = load_schedule()
    print(config_yaml)
    print(Path(__file__))
    print(BASE_DIR)