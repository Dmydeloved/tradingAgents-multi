from typing import List

from webServer.tools.company_event import CompanyEventDetector
from webServer.tools.event import EventType, FinancialEvent
from webServer.tools.industry_event import IndustryBoardEventDetector
from webServer.tools.sentiment_event import SentimentEventDetector
from webServer.tools.trading_event import TradingEventDetector
from webServer.tools.news_event import MacroNewsEventDetector

class EventManager:
    """事件管理器 - 统一管理所有事件检测器"""

    def __init__(self):
        self.detectors = {
            EventType.TRADING: TradingEventDetector(),
            EventType.COMPANY: CompanyEventDetector(),
            EventType.INDUSTRY: IndustryBoardEventDetector(),
            EventType.SENTIMENT: SentimentEventDetector(),
            EventType.NEWS: MacroNewsEventDetector(),
        }

    def detect_all_events(self, symbol: str) -> List[FinancialEvent]:
        """检测某只股票的所有事件"""
        all_events = []

        # 检测交易类事件
        all_events.extend(self.detectors[EventType.TRADING].detect(symbol))

        # 检测公司事件
        all_events.extend(self.detectors[EventType.COMPANY].detect(symbol))

        # 检测行业事件
        all_events.extend(self.detectors[EventType.INDUSTRY].detect())

        # 检测情绪事件
        all_events.extend(self.detectors[EventType.SENTIMENT].detect(symbol=None))

        # 检测新闻事件
        all_events.extend(self.detectors[EventType.NEWS].detect())

        return all_events

if __name__ == "__main__":
    events = []
    symbol = "000001"

    trading_detector = TradingEventDetector()
    trading_events = trading_detector.detect(symbol)
    events.extend(trading_events)

    # 1. 初始化检测器（可自定义阈值）
    sent_detector = SentimentEventDetector(
        config={
            'rank_rise_threshold': 1000,    # 排名上升≥100位触发
            'rank_drop_threshold': -1000,   # 排名下降≥100位触发
            'top1_threshold': 1,           # 榜首阈值
            'top10_threshold': 10,         # 前10阈值
            'top50_threshold': 50,         # 前50阈值
            'top100_threshold': 100,       # 前100阈值
            'price_rise_threshold': 9.0,   # 涨幅≥9%触发
            'price_fall_threshold': -9.0,  # 跌幅≤-9%触发
        }
    )

    # 2. 检测事件（可指定股票代码，如symbol="SH688226"，不指定则检测所有）
    sent_events = sent_detector.detect(symbol=None)
    events.extend(sent_events)

    news_detector = MacroNewsEventDetector(
        config={
            'min_match_count': 1,  # 匹配1个关键词即触发
            'lookback_limit': 100,  # 最多处理100条新闻
            'critical_impact_keywords': ["美联储", "欧洲央行", "通胀目标", "GDP增速", "大幅加息"],
        }
    )

    # 2. 检测宏观新闻事件（无需传入股票代码）
    news_events = news_detector.detect()
    events.extend(news_events)

    # 1. 初始化检测器（可自定义阈值）
    industry_detector = IndustryBoardEventDetector(
        config={
            "price_rise_threshold": 3.0,  # 涨幅异常阈值3%
            "price_fall_threshold": -0.7,  # 跌幅异常阈值-0.7%
            "capital_inflow_threshold": 30.0,  # 资金流入阈值30亿
            "capital_outflow_threshold": -10.0,  # 资金流出阈值-10亿
            "rise_consistency_threshold": 0.8,  # 上涨一致性80%
            "fall_consistency_threshold": 0.7,  # 下跌一致性70%
            "leader_fluctuation_threshold": 9.5  # 龙头异动9.5%
        }
    )

    # 2. 执行事件检测
    industry_events = industry_detector.detect()
    events.extend(industry_events)

    # 初始化公司事件检测器
    comp_detector = CompanyEventDetector()

    # 检测单只股票（例如：贵州茅台 600519）

    comp_events = comp_detector.detect(symbol)

    for idx, event in enumerate(events, 1):
        print(f"【事件{idx}】")
        print(f"事件ID：{event.event_id}")
        print(f"板块名称（symbol）：{event.symbol}")
        print(f"事件类型：{event.event_type.value} -> {event.event_subtype}")
        print(f"事件时间：{event.event_time}")
        print(f"数据来源：{event.data_source}")
        print(f"情绪倾向：{event.sentiment}")
        print(f"影响等级：{event.impact_level.value}")
        print(f"事件描述：{event.event_description}")
        print(f"触发规则：{event.trigger_rule.to_dict() if event.trigger_rule else '无'}")
        print("-" * 80)
