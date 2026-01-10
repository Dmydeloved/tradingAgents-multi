import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
import abc
import pandas as pd
import numpy as np
import akshare as ak
from datetime import datetime, timedelta


# ==================== 基础枚举/数据类 ====================
class EventType(str, Enum):
    """事件类型枚举"""
    TRADING = "trading"  # 市场交易类
    CAPITAL_FLOW = "capital_flow"  # 资金流向类
    COMPANY = "company"  # 公司事件
    INDUSTRY = "industry"  # 行业周期
    MACRO = "macro"  # 宏观事件
    SENTIMENT = "sentiment"  # 情绪事件
    NEWS = "news"  # 新闻事件


class ImpactLevel(str, Enum):
    """影响等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TriggerRule:
    """事件触发规则详情"""
    metric: str  # 触发指标名称
    value: float  # 实际值
    threshold: float  # 阈值
    operator: str  # 比较运算符 (>=, <=, >, <)
    calc_formula: str = ""  # 计算公式（仅用于说明）

    def to_dict(self) -> Dict:
        return {
            "metric": self.metric,
            "value": round(self.value, 4),
            "threshold": round(self.threshold, 4),
            "operator": self.operator,
            "calc_formula": self.calc_formula
        }


@dataclass
class FinancialEvent:
    """金融事件基类"""
    event_id: str
    symbol: str
    event_type: EventType
    event_subtype: str
    event_time: str
    data_source: str = "akshare"
    trigger_rule: Optional[TriggerRule] = None
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = None
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    event_description: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        result = {
            "event_id": self.event_id,
            "symbol": self.symbol,
            "event_type": self.event_type.value,
            "event_subtype": self.event_subtype,
            "event_time": self.event_time,
            "data_source": self.data_source,
            "sentiment": self.sentiment,
            "impact_level": self.impact_level.value,
            "event_description": self.event_description,
            "raw_data": self.raw_data
        }
        if self.trigger_rule:
            result['trigger_rule'] = self.trigger_rule.to_dict()
        return result

    @staticmethod
    def generate_event_id(symbol: str, event_time: str, event_subtype: str) -> str:
        """生成事件ID"""
        time_str = event_time.replace("-", "").replace(":", "").replace(" ", "_")[:15]
        return f"{symbol}_{time_str}_{event_subtype}"



