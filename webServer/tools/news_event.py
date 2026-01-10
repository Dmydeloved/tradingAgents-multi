from datetime import datetime, timedelta
import akshare as ak
from typing import Optional, List, Dict
import pandas as pd
import abc
from webServer.tools.event import FinancialEvent, TriggerRule, EventType,ImpactLevel
class EventDetector(abc.ABC):
    """事件检测器抽象基类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    @abc.abstractmethod
    def detect(self, **kwargs) -> List[FinancialEvent]:
        """检测事件"""
        pass

    def _safe_float_convert(self, value) -> float:
        """安全转换为浮点数"""
        if pd.isna(value):
            return 0.0
        try:
            if isinstance(value, str):
                value = value.replace('%', '').replace('+', '').replace(',', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return 0.0


# ==================== 宏观新闻事件检测器（核心实现） ====================
class MacroNewsEventDetector(EventDetector):
    """宏观新闻事件检测器 - 基于新浪全球宏观新闻（stock_info_global_sina）"""

    # 扩展宏观关键词分类（放开匹配规则，覆盖大范围）
    MACRO_KEYWORDS = {
        # 核心宏观类别（匹配规则宽松，含相关关键词即分类）
        "央行政策": ["央行", "欧洲央行", "美联储", "加息", "降息", "利率", "存款机制利率", "货币政策", "再融资利率"],
        "经济增长": ["GDP", "经济增长", "增长预期", "上调增长", "下调增长", "经济数据", "增速"],
        "通胀数据": ["通胀", "通胀率", "通胀预期", "CPI", "物价", "2%目标", "核心通胀"],
        "金融监管": ["监管", "金融监管", "银保监", "证监会", "省联社改革", "农商行", "开业批复"],
        "国际局势": ["外交部", "会议", "黎巴嫩", "巴黎会议", "地缘政治", "国际会议"],
        "产业政策": ["核能", "私人企业开放", "产能", "扩产", "产业政策", "行业开放"],
        "资本市场": ["指数", "斯托克600", "国债收益率", "欧元兑美元", "汇率", "交易员押注"],
        "财政政策": ["财政", "国债", "发行债券", "财政支出", "税收"],
        "能源大宗商品": ["原油", "天然气", "大宗商品", "能源价格", "煤炭"],
        "突发事件": ["火灾", "爆炸", "停产", "事故", "中断", "紧急"],
        "政策放开": ["开放", "批准", "法案", "议会批准", "政策调整"],
    }

    # 情绪判定关键词（放开匹配，弱化严格性）
    SENTIMENT_KEYWORDS = {
        "positive": ["上调", "增长", "开放", "批准", "上涨", "利好", "稳定", "提升"],
        "negative": ["下调", "下跌", "风险", "危机", "暴跌", "亏损", "处罚"],
        "neutral": ["维持不变", "按兵不动", "确认", "表示", "预计", "评估", "决议"]
    }

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'min_match_count': 1,  # 最低匹配1个关键词即触发（放开规则）
            'lookback_limit': 100,  # 单次检测最多处理100条新闻
            'critical_impact_keywords': ["美联储", "欧洲央行", "通胀目标", "大幅加息", "GDP增速"],  # 高影响关键词
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, **kwargs) -> List[FinancialEvent]:
        """
        检测宏观新闻事件（无需传入股票代码，自动分类）
        Returns:
            宏观新闻事件列表
        """
        events = []

        try:
            # 获取新浪全球宏观新闻数据
            df = ak.stock_info_global_sina()
            if df is None or df.empty:
                print("未获取到新浪全球宏观新闻数据")
                return events

            # 限制单次处理数量（避免数据量过大）
            if len(df) > self.config['lookback_limit']:
                df = df.head(self.config['lookback_limit'])

            # 遍历每条新闻生成事件
            for idx, row in df.iterrows():
                try:
                    event = self._analyze_macro_news(row)
                    if event:
                        events.append(event)
                except Exception as e:
                    print(f"处理第{idx}条新闻失败: {e}")
                    continue

        except Exception as e:
            print(f"检测宏观新闻事件失败: {e}")

        return events

    def _analyze_macro_news(self, news_row: pd.Series) -> Optional[FinancialEvent]:
        """分析单条宏观新闻，生成标准化事件"""
        # 1. 提取核心字段
        news_time = str(news_row.get('时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        news_content = str(news_row.get('内容', '')).strip()

        if not news_content:
            return None

        # 2. 新闻分类（按关键词匹配，放开规则）
        category, match_count, match_keywords = self._classify_macro_news(news_content)
        if not category:  # 无匹配分类则标记为"综合宏观新闻"
            category = "综合宏观新闻"
            match_count = 0
            match_keywords = []

        # 3. 生成分类标签（替代原股票代码symbol）
        macro_tag = category  # 如"欧洲央行政策"、"中国金融监管"

        # 4. 情绪判定（放开规则，优先匹配中性，有明确正负才标记）
        sentiment = self._judge_sentiment(news_content)

        # 5. 影响等级判定（结合分类和关键词）
        impact_level = self._determine_impact_level(category, match_keywords)

        # 6. 触发规则（匹配关键词数量≥1）
        trigger_rule = TriggerRule(
            metric="宏观关键词匹配数",
            value=float(match_count),
            threshold=float(self.config['min_match_count']),
            operator=">="
        )

        # 7. 事件子类型（基于分类）
        event_subtype = f"macro_{category.replace(' ', '_').lower()}"

        # 8. 事件描述（截取前80字）
        event_desc = f"【{category}】{news_content[:80]}..." if len(news_content) > 80 else f"【{category}】{news_content}"

        # 9. 原始数据
        raw_data = {
            "新闻时间": news_time,
            "新闻内容": news_content,
            "匹配分类": category,
            "匹配关键词": match_keywords,
            "匹配数量": match_count
        }

        # 10. 生成事件ID
        event_id = FinancialEvent.generate_event_id(macro_tag, news_time, event_subtype)

        # 11. 构建事件对象
        event = FinancialEvent(
            event_id=event_id,
            symbol=macro_tag,  # 分类标签替代股票代码
            event_type=EventType.MACRO,  # 宏观事件为主类型
            event_subtype=event_subtype,
            event_time=news_time,  # 直接使用接口返回的新闻时间
            trigger_rule=trigger_rule,
            sentiment=sentiment,
            impact_level=impact_level,
            event_description=event_desc,
            raw_data=raw_data
        )

        return event

    def _classify_macro_news(self, content: str) -> tuple[str, int, list]:
        """
        分类宏观新闻（放开匹配规则，匹配到1个关键词即分类）
        Returns:
            (分类名称, 匹配关键词数量, 匹配的关键词列表)
        """
        content_lower = content.lower()
        max_match = 0
        best_category = ""
        match_keywords = []

        # 遍历所有宏观分类
        for category, keywords in self.MACRO_KEYWORDS.items():
            current_match = 0
            current_keywords = []
            for kw in keywords:
                if kw.lower() in content_lower:
                    current_match += 1
                    current_keywords.append(kw)

            # 匹配数最多的分类为最佳分类
            if current_match > max_match:
                max_match = current_match
                best_category = category
                match_keywords = current_keywords

        return best_category, max_match, match_keywords

    def _judge_sentiment(self, content: str) -> str:
        """
        判定新闻情绪（放开规则，优先中性）
        Returns:
            positive/negative/neutral
        """
        content_lower = content.lower()

        # 统计正负情绪关键词数量
        pos_count = sum(1 for kw in self.SENTIMENT_KEYWORDS["positive"] if kw.lower() in content_lower)
        neg_count = sum(1 for kw in self.SENTIMENT_KEYWORDS["negative"] if kw.lower() in content_lower)

        # 放开规则：仅当某类情绪关键词数≥2才标记，否则中性
        if pos_count >= 2:
            return "positive"
        elif neg_count >= 2:
            return "negative"
        else:
            return "neutral"

    def _determine_impact_level(self, category: str, match_keywords: list) -> ImpactLevel:
        """
        判定影响等级（放开规则，范围更大）
        """
        # 高影响关键词匹配则直接标为CRITICAL/HIGH
        critical_kw = self.config['critical_impact_keywords']
        if any(kw in match_keywords for kw in critical_kw):
            return ImpactLevel.CRITICAL if "央行" in category or "通胀" in category else ImpactLevel.HIGH

        # 核心宏观分类标为HIGH/MEDIUM
        high_impact_categories = ["央行政策", "经济增长", "通胀数据", "国际局势"]
        if category in high_impact_categories:
            return ImpactLevel.HIGH

        # 其他分类标为MEDIUM/LOW
        medium_impact_categories = ["金融监管", "资本市场", "产业政策"]
        if category in medium_impact_categories:
            return ImpactLevel.MEDIUM

        return ImpactLevel.LOW


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 1. 初始化宏观新闻检测器（可自定义配置）
    detector = MacroNewsEventDetector(
        config={
            'min_match_count': 1,  # 匹配1个关键词即触发
            'lookback_limit': 100,  # 最多处理100条新闻
            'critical_impact_keywords': ["美联储", "欧洲央行", "通胀目标", "GDP增速", "大幅加息"],
        }
    )

    # 2. 检测宏观新闻事件（无需传入股票代码）
    events = detector.detect()

    # 3. 输出检测结果
    print(f"\n=== 宏观新闻事件检测结果 ===")
    print(f"检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"共检测到 {len(events)} 个宏观新闻事件\n")

    # 4. 逐个输出事件详情
    for idx, event in enumerate(events, 1):
        print(f"【事件{idx}】")
        print(f"事件ID：{event.event_id}")
        print(f"新闻分类：{event.symbol}（替代股票代码）")
        print(f"事件类型：{event.event_type.value} -> {event.event_subtype}")
        print(f"新闻时间：{event.event_time}（精确到秒）")
        print(f"情绪倾向：{event.sentiment}")
        print(f"影响等级：{event.impact_level.value}")
        print(f"事件描述：{event.event_description}")
        print(f"触发规则：{event.trigger_rule.to_dict() if event.trigger_rule else '无'}")
        print("-" * 100)

    # # 5. 可选：将事件保存为JSON文件
    # import json
    # events_json = json.dumps([e.to_dict() for e in events], ensure_ascii=False, indent=2)
    # with open("macro_news_events.json", "w", encoding="utf-8") as f:
    #     f.write(events_json)
    # print("\n宏观新闻事件已保存至 macro_news_events.json 文件")