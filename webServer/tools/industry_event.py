from datetime import datetime, timedelta
import akshare as ak
from typing import Optional, List, Dict
import pandas as pd
import abc
from webServer.tools.event import FinancialEvent, TriggerRule, EventType,ImpactLevel
# ==================== 抽象检测器基类 ====================
class BaseEventDetector(abc.ABC):
    """事件检测器抽象基类"""

    def __init__(self, config: Optional[Dict] = None):
        # 默认配置（可通过外部参数覆盖）
        default_config = {
            # 价格类阈值
            "price_rise_threshold": 3.0,  # 涨幅异常阈值
            "price_fall_threshold": -0.7,  # 跌幅异常阈值
            # 资金类阈值
            "capital_inflow_threshold": 30.0,  # 资金流入阈值（亿元）
            "capital_outflow_threshold": -10.0,  # 资金流出阈值（亿元）
            # 结构一致性阈值
            "rise_consistency_threshold": 0.8,  # 上涨一致性阈值（80%）
            "fall_consistency_threshold": 0.7,  # 下跌一致性阈值（70%）
            # 龙头异动阈值
            "leader_fluctuation_threshold": 9.5  # 龙头涨跌幅阈值
        }
        self.config = {**default_config, **(config or {})}

    @abc.abstractmethod
    def detect(self) -> List[FinancialEvent]:
        """核心检测方法，返回事件列表"""
        pass

    def _get_current_time(self) -> str:
        """获取当前年月日 + 固定时分秒（8:56:30），格式：YYYY-MM-DD HH:MM:SS"""
        # 1. 获取当前时间对象
        current_datetime = datetime.now()
        # 2. 替换时分秒为固定值：时=8，分=56，秒=30
        fixed_time = current_datetime.replace(hour=8, minute=56, second=30, microsecond=0)
        # 3. 格式化为指定字符串
        return fixed_time.strftime("%Y-%m-%d %H:%M:%S")

    def _safe_float(self, value) -> float:
        """安全转换为浮点数，异常返回0"""
        try:
            if isinstance(value, str):
                # 移除百分号、逗号等干扰字符
                value = value.replace("%", "").replace(",", "").strip()
            return float(value)
        except (ValueError, TypeError, AttributeError):
            return 0.0

    def _calculate_impact_level(self, value: float, threshold: float, event_type: str) -> ImpactLevel:
        """
        根据实际值与阈值的偏离度计算影响等级
        :param value: 实际值
        :param threshold: 阈值
        :param event_type: 事件类型（price/capital/breadth/leader）
        :return: 影响等级
        """
        deviation = abs(value - threshold)

        if event_type == "price":
            if deviation > 5:
                return ImpactLevel.CRITICAL
            elif deviation > 3:
                return ImpactLevel.HIGH
            else:
                return ImpactLevel.MEDIUM
        elif event_type == "capital":
            if deviation > 50:
                return ImpactLevel.CRITICAL
            elif deviation > 20:
                return ImpactLevel.HIGH
            else:
                return ImpactLevel.MEDIUM
        elif event_type == "breadth":
            if deviation > 0.2:
                return ImpactLevel.HIGH
            else:
                return ImpactLevel.MEDIUM
        elif event_type == "leader":
            if abs(value) > 10:
                return ImpactLevel.CRITICAL
            else:
                return ImpactLevel.HIGH
        return ImpactLevel.MEDIUM


# ==================== 行业板块综合事件检测器 ====================
class IndustryBoardEventDetector(BaseEventDetector):
    """
    行业板块综合事件检测器
    支持7类事件：
    1. 行业涨幅异常事件（≥3%）
    2. 行业跌幅异常事件（≤-0.7%）
    3. 行业资金显著流入事件（净流入>30亿）
    4. 行业资金显著流出事件（净流入<-10亿）
    5. 行业内部上涨一致性事件（上涨家数占比≥80%）
    6. 行业内部下跌一致性事件（下跌家数占比≥70%）
    7. 行业龙头异动事件（领涨股涨跌幅≥9.5% 或 ≤-9.5%）
    """

    def detect(self) -> List[FinancialEvent]:
        """执行事件检测，返回所有触发的事件"""
        events = []

        # 1. 获取行业板块数据
        board_df = self._get_board_data()
        if board_df is None or board_df.empty:
            print("未获取到行业板块数据")
            return events

        # 2. 统一事件时间（所有事件使用同一检测时间）
        event_time = self._get_current_time()

        # 3. 遍历每个板块，检测事件
        for _, row in board_df.iterrows():
            # 提取基础字段并做类型转换
            board_info = self._extract_board_info(row)
            if not board_info:
                continue  # 跳过无效数据

            # 检测7类事件
            events.extend(self._detect_price_events(board_info, event_time))
            events.extend(self._detect_capital_events(board_info, event_time))
            events.extend(self._detect_breadth_events(board_info, event_time))
            events.extend(self._detect_leader_events(board_info, event_time))

        return events

    def _get_board_data(self) -> Optional[pd.DataFrame]:
        """获取同花顺行业板块汇总数据"""
        try:
            df = ak.stock_board_industry_summary_ths()
            # 确保列名匹配用户提供的格式（兼容不同akshare版本）
            col_mapping = {
                "板块": "板块",
                "涨跌幅": "涨跌幅",
                "总成交量": "总成交量",
                "总成交额": "总成交额",
                "净流入": "净流入",
                "上涨家数": "上涨家数",
                "下跌家数": "下跌家数",
                "均价": "均价",
                "领涨股": "领涨股",
                "领涨股-最新价": "领涨股-最新价",
                "领涨股-涨跌幅": "领涨股-涨跌幅"
            }
            # 只保留需要的列
            df = df[[col for col in col_mapping.keys() if col in df.columns]]
            return df
        except Exception as e:
            print(f"获取板块数据失败：{e}")
            return None

    def _extract_board_info(self, row: pd.Series) -> Optional[Dict]:
        """提取并清洗板块基础信息"""
        try:
            board_name = row.get("板块", "未知板块")
            total_stocks = self._safe_float(row["上涨家数"]) + self._safe_float(row["下跌家数"])

            return {
                "board_name": board_name,
                "price_change": self._safe_float(row["涨跌幅"]),  # 板块涨跌幅（%）
                "total_volume": self._safe_float(row["总成交量"]),  # 总成交量
                "total_amount": self._safe_float(row["总成交额"]),  # 总成交额
                "net_inflow": self._safe_float(row["净流入"]),  # 净流入（亿元）
                "rise_stocks": self._safe_float(row["上涨家数"]),  # 上涨家数
                "fall_stocks": self._safe_float(row["下跌家数"]),  # 下跌家数
                "total_stocks": total_stocks,  # 总家数（上涨+下跌）
                "avg_price": self._safe_float(row["均价"]),  # 均价
                "leader_stock": row.get("领涨股", ""),  # 领涨股名称
                "leader_price": self._safe_float(row["领涨股-最新价"]),  # 领涨股最新价
                "leader_change": self._safe_float(row["领涨股-涨跌幅"])  # 领涨股涨跌幅（%）
            }
        except Exception as e:
            print(f"解析板块数据失败：{e}")
            return None

    def _detect_price_events(self, board_info: Dict, event_time: str) -> List[FinancialEvent]:
        """检测价格类事件（规则1、规则2）"""
        events = []
        price_change = board_info["price_change"]
        board_name = board_info["board_name"]

        # 规则1：行业涨幅异常事件
        rise_thresh = self.config["price_rise_threshold"]
        if price_change >= rise_thresh:
            trigger_rule = TriggerRule(
                metric="板块涨跌幅",
                value=price_change,
                threshold=rise_thresh,
                operator=">=",
                calc_formula="板块涨跌幅 ≥ 3%"
            )
            impact_level = self._calculate_impact_level(price_change, rise_thresh, "price")
            # 构建统一的FinancialEvent
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "price_rise_abnormal"),
                symbol=board_name,  # 板块名称作为symbol
                event_type=EventType.INDUSTRY,
                event_subtype="price_rise_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="positive",
                impact_level=impact_level,
                event_description=f"{board_name}板块涨跌幅{price_change:.2f}%，高于阈值{rise_thresh}%，触发行业涨幅异常事件",
                raw_data=board_info
            )
            events.append(event)

        # 规则2：行业跌幅异常事件
        fall_thresh = self.config["price_fall_threshold"]
        if price_change <= fall_thresh:
            trigger_rule = TriggerRule(
                metric="板块涨跌幅",
                value=price_change,
                threshold=fall_thresh,
                operator="<=",
                calc_formula="板块涨跌幅 ≤ -0.7%"
            )
            impact_level = self._calculate_impact_level(price_change, fall_thresh, "price")
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "price_fall_abnormal"),
                symbol=board_name,
                event_type=EventType.INDUSTRY,
                event_subtype="price_fall_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="negative",
                impact_level=impact_level,
                event_description=f"{board_name}板块涨跌幅{price_change:.2f}%，低于阈值{fall_thresh}%，触发行业跌幅异常事件",
                raw_data=board_info
            )
            events.append(event)

        return events

    def _detect_capital_events(self, board_info: Dict, event_time: str) -> List[FinancialEvent]:
        """检测资金流动类事件（规则3、规则4）"""
        events = []
        net_inflow = board_info["net_inflow"]
        board_name = board_info["board_name"]

        # 规则3：行业资金显著流入事件
        inflow_thresh = self.config["capital_inflow_threshold"]
        if net_inflow > inflow_thresh:
            trigger_rule = TriggerRule(
                metric="板块净流入",
                value=net_inflow,
                threshold=inflow_thresh,
                operator=">",
                calc_formula="板块净流入 > 30亿元"
            )
            impact_level = self._calculate_impact_level(net_inflow, inflow_thresh, "capital")
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "capital_inflow_abnormal"),
                symbol=board_name,
                event_type=EventType.CAPITAL_FLOW,
                event_subtype="capital_inflow_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="positive",
                impact_level=impact_level,
                event_description=f"{board_name}板块净流入{net_inflow:.2f}亿元，超过阈值{inflow_thresh}亿元，触发资金显著流入事件",
                raw_data=board_info
            )
            events.append(event)

        # 规则4：行业资金显著流出事件
        outflow_thresh = self.config["capital_outflow_threshold"]
        if net_inflow < outflow_thresh:
            trigger_rule = TriggerRule(
                metric="板块净流入",
                value=net_inflow,
                threshold=outflow_thresh,
                operator="<",
                calc_formula="板块净流入 < -10亿元"
            )
            impact_level = self._calculate_impact_level(net_inflow, outflow_thresh, "capital")
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "capital_outflow_abnormal"),
                symbol=board_name,
                event_type=EventType.CAPITAL_FLOW,
                event_subtype="capital_outflow_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="negative",
                impact_level=impact_level,
                event_description=f"{board_name}板块净流入{net_inflow:.2f}亿元，低于阈值{outflow_thresh}亿元，触发资金显著流出事件",
                raw_data=board_info
            )
            events.append(event)

        return events

    def _detect_breadth_events(self, board_info: Dict, event_time: str) -> List[FinancialEvent]:
        """检测结构一致性类事件（规则5、规则6）"""
        events = []
        board_name = board_info["board_name"]
        total_stocks = board_info["total_stocks"]
        rise_stocks = board_info["rise_stocks"]
        fall_stocks = board_info["fall_stocks"]

        # 避免除零错误
        if total_stocks == 0:
            return events

        # 规则5：行业内部上涨一致性事件
        rise_consist_thresh = self.config["rise_consistency_threshold"]
        rise_ratio = rise_stocks / total_stocks
        if rise_ratio >= rise_consist_thresh:
            trigger_rule = TriggerRule(
                metric="上涨家数占比",
                value=rise_ratio,
                threshold=rise_consist_thresh,
                operator=">=",
                calc_formula="上涨家数 / (上涨家数 + 下跌家数) ≥ 80%"
            )
            impact_level = self._calculate_impact_level(rise_ratio, rise_consist_thresh, "breadth")
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "rise_consistency_abnormal"),
                symbol=board_name,
                event_type=EventType.INDUSTRY,
                event_subtype="rise_consistency_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="positive",
                impact_level=impact_level,
                event_description=f"{board_name}板块上涨家数占比{rise_ratio:.1%}（{rise_stocks}/{int(total_stocks)}），高于阈值{rise_consist_thresh:.1%}，触发上涨一致性事件",
                raw_data={**board_info, "上涨家数占比": rise_ratio}
            )
            events.append(event)

        # 规则6：行业内部下跌一致性事件
        fall_consist_thresh = self.config["fall_consistency_threshold"]
        fall_ratio = fall_stocks / total_stocks
        if fall_ratio >= fall_consist_thresh:
            trigger_rule = TriggerRule(
                metric="下跌家数占比",
                value=fall_ratio,
                threshold=fall_consist_thresh,
                operator=">=",
                calc_formula="下跌家数 / (上涨家数 + 下跌家数) ≥ 70%"
            )
            impact_level = self._calculate_impact_level(fall_ratio, fall_consist_thresh, "breadth")
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "fall_consistency_abnormal"),
                symbol=board_name,
                event_type=EventType.INDUSTRY,
                event_subtype="fall_consistency_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="negative",
                impact_level=impact_level,
                event_description=f"{board_name}板块下跌家数占比{fall_ratio:.1%}（{fall_stocks}/{int(total_stocks)}），高于阈值{fall_consist_thresh:.1%}，触发下跌一致性事件",
                raw_data={**board_info, "下跌家数占比": fall_ratio}
            )
            events.append(event)

        return events

    def _detect_leader_events(self, board_info: Dict, event_time: str) -> List[FinancialEvent]:
        """检测龙头驱动类事件（规则7）"""
        events = []
        board_name = board_info["board_name"]
        leader_change = board_info["leader_change"]
        leader_stock = board_info["leader_stock"]
        leader_thresh = self.config["leader_fluctuation_threshold"]

        # 规则7：行业龙头异动事件（涨≥9.5% 或 跌≤-9.5%）
        if abs(leader_change) >= leader_thresh:
            if leader_change >= leader_thresh:
                operator = ">="
                sentiment = "positive"
                desc_prefix = "上涨"
                threshold = leader_thresh
            else:
                operator = "<="
                sentiment = "negative"
                desc_prefix = "下跌"
                threshold = -leader_thresh

            trigger_rule = TriggerRule(
                metric="领涨股涨跌幅",
                value=leader_change,
                threshold=threshold,
                operator=operator,
                calc_formula="领涨股涨跌幅 ≥ 9.5% 或 ≤ -9.5%"
            )
            impact_level = self._calculate_impact_level(leader_change, leader_thresh, "leader")
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(board_name, event_time, "leader_fluctuation_abnormal"),
                symbol=board_name,
                event_type=EventType.INDUSTRY,
                event_subtype="leader_fluctuation_abnormal",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment=sentiment,
                impact_level=impact_level,
                event_description=f"{board_name}板块领涨股{leader_stock}涨跌幅{leader_change:.2f}%，{desc_prefix}超过阈值{leader_thresh}%，触发龙头异动事件",
                raw_data=board_info
            )
            events.append(event)

        return events


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 1. 初始化检测器（可自定义阈值）
    detector = IndustryBoardEventDetector(
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
    events = detector.detect()

    # 3. 输出检测结果
    print(f"\n=== 行业板块事件检测结果 ===")
    print(f"检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"共检测到 {len(events)} 个异常事件\n")

    # 4. 逐个输出事件详情
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
