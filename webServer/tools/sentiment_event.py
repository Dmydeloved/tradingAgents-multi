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

    def _calculate_impact_level(self, deviation: float, metric_type: str = "rank") -> ImpactLevel:
        """
        根据偏离度计算影响等级
        :param deviation: 偏离阈值的幅度
        :param metric_type: 指标类型（rank/price）
        :return: 影响等级
        """
        abs_dev = abs(deviation)
        if metric_type == "rank":
            if abs_dev > 1000:
                return ImpactLevel.CRITICAL
            elif abs_dev > 500:
                return ImpactLevel.HIGH
            elif abs_dev > 100:
                return ImpactLevel.MEDIUM
            else:
                return ImpactLevel.LOW
        else:  # price
            if abs_dev > 10:
                return ImpactLevel.CRITICAL
            elif abs_dev > 7:
                return ImpactLevel.HIGH
            elif abs_dev > 3:
                return ImpactLevel.MEDIUM
            else:
                return ImpactLevel.LOW

    def _get_current_time_second(self) -> str:
        """获取当前年月日 + 固定时分秒（8:56:30），格式：YYYY-MM-DD HH:MM:SS"""
        # 1. 获取当前时间对象
        current_datetime = datetime.now()
        # 2. 替换时分秒为固定值：时=8，分=56，秒=30
        fixed_time = current_datetime.replace(hour=8, minute=56, second=30, microsecond=0)
        # 3. 格式化为指定字符串
        return fixed_time.strftime("%Y-%m-%d %H:%M:%S")

    def _find_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """查找数据列（支持多种可能的列名）"""
        for col in candidates:
            if col in df.columns:
                return col
        return None

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

    def _safe_int_convert(self, value) -> int:
        """安全转换为整数"""
        if pd.isna(value):
            return 0
        try:
            return int(float(value))  # 先转浮点数再转整数，兼容小数形式的整数
        except (ValueError, TypeError):
            return 0


# ==================== 情绪事件检测器（核心实现） ====================
class SentimentEventDetector(EventDetector):
    """情绪事件检测器 - 基于东方财富热门榜（stock_hot_up_em）"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            # 排名变动阈值
            'rank_rise_threshold': 1000,    # 排名大幅上升阈值（上升≥100位）
            'rank_drop_threshold': -1000,   # 排名大幅下降阈值（下降≥100位）
            # 热门榜排名阈值
            'top1_threshold': 1,           # 榜首阈值
            'top10_threshold': 10,         # 前10阈值
            'top50_threshold': 50,         # 前50阈值
            'top100_threshold': 100,       # 前100阈值
            # 价格异动阈值（%）
            'price_rise_threshold': 9.0,   # 涨幅异动阈值
            'price_fall_threshold': -9.0,  # 跌幅异动阈值
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, symbol: str = None, **kwargs) -> List[FinancialEvent]:
        """
        检测情绪事件（基于东方财富热门榜）
        Args:
            symbol: 股票代码（如SH688226）。如果为None，则检测所有上榜股票
        Returns:
            情绪事件列表
        """
        events = []

        try:
            # 获取东方财富热门榜数据
            df = ak.stock_hot_up_em()
            if df is None or df.empty:
                print("未获取到东方财富热门榜数据")
                return events

            # 如果指定了股票代码，只检测该股票
            if symbol:
                code_col = self._find_column(df, ['代码', '股票代码'])
                if code_col:
                    df = df[df[code_col] == symbol]
                if df.empty:
                    print(f"股票{symbol}未进入热门榜")
                    return events

            # 统一事件时间（精确到秒）
            event_time = self._get_current_time_second()

            # 检测各类情绪事件
            events.extend(self._detect_rank_change_events(df, event_time))  # 排名变动事件
            events.extend(self._detect_top_rank_events(df, event_time))     # 进入前N排名事件
            events.extend(self._detect_price_fluct_events(df, event_time))  # 价格异动事件
            # events.extend(self._detect_hot_list_entry_events(df, event_time))  # 上榜基础事件

        except Exception as e:
            print(f"检测情绪事件失败: {e}")

        return events

    def _detect_rank_change_events(self, df: pd.DataFrame, event_time: str) -> List[FinancialEvent]:
        """检测排名变动事件（大幅上升/下降）"""
        events = []

        # 查找关键列
        rank_change_col = self._find_column(df, ['排名较昨日变动', '排名变动'])
        current_rank_col = self._find_column(df, ['当前排名', '排名'])
        code_col = self._find_column(df, ['代码', '股票代码'])
        name_col = self._find_column(df, ['股票名称', '名称'])

        if not all([rank_change_col, current_rank_col, code_col]):
            print("缺少排名变动相关字段，跳过排名变动事件检测")
            return events

        # 遍历数据
        for idx, row in df.iterrows():
            try:
                # 提取并转换数据
                rank_change = self._safe_int_convert(row[rank_change_col])
                current_rank = self._safe_int_convert(row[current_rank_col])
                stock_code = str(row[code_col])
                stock_name = str(row[name_col]) if name_col else "未知股票"

                # 1. 排名大幅上升事件
                rank_rise_thresh = self.config['rank_rise_threshold']
                if rank_change >= rank_rise_thresh:
                    deviation = rank_change - rank_rise_thresh
                    trigger_rule = TriggerRule(
                        metric="排名较昨日变动",
                        value=rank_change,
                        threshold=rank_rise_thresh,
                        operator=">="
                    )
                    impact_level = self._calculate_impact_level(deviation, "rank")
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "rank_rise_abnormal"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="rank_rise_abnormal",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="positive",
                        impact_level=impact_level,
                        event_description=f"{stock_name}({stock_code})热门榜排名较昨日上升{rank_change}位（当前排名{current_rank}），触发排名大幅上升事件（阈值：{rank_rise_thresh}位）",
                        raw_data={
                            '股票名称': stock_name,
                            '当前排名': current_rank,
                            '排名较昨日变动': rank_change,
                            '触发阈值': rank_rise_thresh
                        }
                    )
                    events.append(event)

                # 2. 排名大幅下降事件
                rank_drop_thresh = self.config['rank_drop_threshold']
                if rank_change <= rank_drop_thresh:
                    deviation = rank_change - rank_drop_thresh  # 负数，偏离幅度为绝对值
                    trigger_rule = TriggerRule(
                        metric="排名较昨日变动",
                        value=rank_change,
                        threshold=rank_drop_thresh,
                        operator="<="
                    )
                    impact_level = self._calculate_impact_level(abs(deviation), "rank")
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "rank_drop_abnormal"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="rank_drop_abnormal",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="negative",
                        impact_level=impact_level,
                        event_description=f"{stock_name}({stock_code})热门榜排名较昨日下降{abs(rank_change)}位（当前排名{current_rank}），触发排名大幅下降事件（阈值：{abs(rank_drop_thresh)}位）",
                        raw_data={
                            '股票名称': stock_name,
                            '当前排名': current_rank,
                            '排名较昨日变动': rank_change,
                            '触发阈值': rank_drop_thresh
                        }
                    )
                    events.append(event)

            except Exception as e:
                print(f"处理排名变动事件失败（行{idx}）: {e}")
                continue

        return events

    def _detect_top_rank_events(self, df: pd.DataFrame, event_time: str) -> List[FinancialEvent]:
        """检测进入热门榜前N排名事件（榜首/前10/前50/前100）"""
        events = []

        # 查找关键列
        current_rank_col = self._find_column(df, ['当前排名', '排名'])
        code_col = self._find_column(df, ['代码', '股票代码'])
        name_col = self._find_column(df, ['股票名称', '名称'])

        if not all([current_rank_col, code_col]):
            print("缺少当前排名相关字段，跳过前N排名事件检测")
            return events

        # 遍历数据
        for idx, row in df.iterrows():
            try:
                # 提取并转换数据
                current_rank = self._safe_int_convert(row[current_rank_col])
                stock_code = str(row[code_col])
                stock_name = str(row[name_col]) if name_col else "未知股票"

                # 1. 榜首事件（第1名）
                top1_thresh = self.config['top1_threshold']
                if current_rank == top1_thresh:
                    trigger_rule = TriggerRule(
                        metric="当前排名",
                        value=current_rank,
                        threshold=top1_thresh,
                        operator="=="
                    )
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "top1_rank"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="top1_rank",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="positive",
                        impact_level=ImpactLevel.CRITICAL,
                        event_description=f"{stock_name}({stock_code})登顶东方财富热门榜第1名，触发榜首事件",
                        raw_data={
                            '股票名称': stock_name,
                            '当前排名': current_rank,
                            '触发阈值': top1_thresh
                        }
                    )
                    events.append(event)

                # 2. 前10事件
                top10_thresh = self.config['top10_threshold']
                if 1 < current_rank <= top10_thresh:
                    trigger_rule = TriggerRule(
                        metric="当前排名",
                        value=current_rank,
                        threshold=top10_thresh,
                        operator="<="
                    )
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "top10_rank"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="top10_rank",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="positive",
                        impact_level=ImpactLevel.HIGH,
                        event_description=f"{stock_name}({stock_code})进入东方财富热门榜前10（当前排名{current_rank}），触发前10排名事件",
                        raw_data={
                            '股票名称': stock_name,
                            '当前排名': current_rank,
                            '触发阈值': top10_thresh
                        }
                    )
                    events.append(event)

                # 3. 前50事件
                top50_thresh = self.config['top50_threshold']
                if 10 < current_rank <= top50_thresh:
                    trigger_rule = TriggerRule(
                        metric="当前排名",
                        value=current_rank,
                        threshold=top50_thresh,
                        operator="<="
                    )
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "top50_rank"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="top50_rank",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="positive",
                        impact_level=ImpactLevel.MEDIUM,
                        event_description=f"{stock_name}({stock_code})进入东方财富热门榜前50（当前排名{current_rank}），触发前50排名事件",
                        raw_data={
                            '股票名称': stock_name,
                            '当前排名': current_rank,
                            '触发阈值': top50_thresh
                        }
                    )
                    events.append(event)

                # 4. 前100事件
                top100_thresh = self.config['top100_threshold']
                if 50 < current_rank <= top100_thresh:
                    trigger_rule = TriggerRule(
                        metric="当前排名",
                        value=current_rank,
                        threshold=top100_thresh,
                        operator="<="
                    )
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "top100_rank"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="top100_rank",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="positive",
                        impact_level=ImpactLevel.LOW,
                        event_description=f"{stock_name}({stock_code})进入东方财富热门榜前100（当前排名{current_rank}），触发前100排名事件",
                        raw_data={
                            '股票名称': stock_name,
                            '当前排名': current_rank,
                            '触发阈值': top100_thresh
                        }
                    )
                    events.append(event)

            except Exception as e:
                print(f"处理前N排名事件失败（行{idx}）: {e}")
                continue

        return events

    def _detect_price_fluct_events(self, df: pd.DataFrame, event_time: str) -> List[FinancialEvent]:
        """检测热门榜股票价格异动事件（大幅上涨/下跌）"""
        events = []

        # 查找关键列
        price_change_col = self._find_column(df, ['涨跌幅', '涨跌幅%'])
        price_col = self._find_column(df, ['最新价', '价格'])
        change_amt_col = self._find_column(df, ['涨跌额', '涨跌'])
        code_col = self._find_column(df, ['代码', '股票代码'])
        name_col = self._find_column(df, ['股票名称', '名称'])

        if not all([price_change_col, code_col]):
            print("缺少价格相关字段，跳过价格异动事件检测")
            return events

        # 遍历数据
        for idx, row in df.iterrows():
            try:
                # 提取并转换数据
                price_change = self._safe_float_convert(row[price_change_col])
                latest_price = self._safe_float_convert(row[price_col]) if price_col else 0.0
                change_amt = self._safe_float_convert(row[change_amt_col]) if change_amt_col else 0.0
                stock_code = str(row[code_col])
                stock_name = str(row[name_col]) if name_col else "未知股票"

                # 1. 涨幅异动事件（≥9%）
                price_rise_thresh = self.config['price_rise_threshold']
                if price_change >= price_rise_thresh:
                    deviation = price_change - price_rise_thresh
                    trigger_rule = TriggerRule(
                        metric="涨跌幅",
                        value=price_change,
                        threshold=price_rise_thresh,
                        operator=">="
                    )
                    impact_level = self._calculate_impact_level(deviation, "price")
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "price_rise_abnormal"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="price_rise_abnormal",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="positive",
                        impact_level=impact_level,
                        event_description=f"{stock_name}({stock_code})涨跌幅{price_change:.2f}%（最新价{latest_price:.2f}），触发热门股涨幅异动事件（阈值：{price_rise_thresh}%）",
                        raw_data={
                            '股票名称': stock_name,
                            '最新价': latest_price,
                            '涨跌幅': price_change,
                            '涨跌额': change_amt,
                            '触发阈值': price_rise_thresh
                        }
                    )
                    events.append(event)

                # 2. 跌幅异动事件（≤-9%）
                price_fall_thresh = self.config['price_fall_threshold']
                if price_change <= price_fall_thresh:
                    deviation = price_change - price_fall_thresh  # 负数，偏离幅度为绝对值
                    trigger_rule = TriggerRule(
                        metric="涨跌幅",
                        value=price_change,
                        threshold=price_fall_thresh,
                        operator="<="
                    )
                    impact_level = self._calculate_impact_level(abs(deviation), "price")
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(stock_code, event_time, "price_fall_abnormal"),
                        symbol=stock_code,
                        event_type=EventType.SENTIMENT,
                        event_subtype="price_fall_abnormal",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="negative",
                        impact_level=impact_level,
                        event_description=f"{stock_name}({stock_code})涨跌幅{price_change:.2f}%（最新价{latest_price:.2f}），触发热门股跌幅异动事件（阈值：{price_fall_thresh}%）",
                        raw_data={
                            '股票名称': stock_name,
                            '最新价': latest_price,
                            '涨跌幅': price_change,
                            '涨跌额': change_amt,
                            '触发阈值': price_fall_thresh
                        }
                    )
                    events.append(event)

            except Exception as e:
                print(f"处理价格异动事件失败（行{idx}）: {e}")
                continue

        return events

    # def _detect_hot_list_entry_events(self, df: pd.DataFrame, event_time: str) -> List[FinancialEvent]:
    #     """检测热门榜上榜基础事件（所有上榜股票）"""
    #     events = []
    #
    #     # 查找关键列
    #     current_rank_col = self._find_column(df, ['当前排名', '排名'])
    #     code_col = self._find_column(df, ['代码', '股票代码'])
    #     name_col = self._find_column(df, ['股票名称', '名称'])
    #
    #     if not all([current_rank_col, code_col]):
    #         print("缺少基础字段，跳过上榜事件检测")
    #         return events
    #
    #     # 遍历数据
    #     for idx, row in df.iterrows():
    #         try:
    #             # 提取并转换数据
    #             current_rank = self._safe_int_convert(row[current_rank_col])
    #             stock_code = str(row[code_col])
    #             stock_name = str(row[name_col]) if name_col else "未知股票"
    #
    #             # 上榜基础事件
    #             trigger_rule = TriggerRule(
    #                 metric="是否上榜",
    #                 value=1.0,
    #                 threshold=1.0,
    #                 operator="=="
    #             )
    #             event = FinancialEvent(
    #                 event_id=FinancialEvent.generate_event_id(stock_code, event_time, "hot_list_entry"),
    #                 symbol=stock_code,
    #                 event_type=EventType.SENTIMENT,
    #                 event_subtype="hot_list_entry",
    #                 event_time=event_time,
    #                 trigger_rule=trigger_rule,
    #                 sentiment="neutral",
    #                 impact_level=ImpactLevel.LOW,
    #                 event_description=f"{stock_name}({stock_code})进入东方财富热门榜（当前排名{current_rank}）",
    #                 raw_data={
    #                     '股票名称': stock_name,
    #                     '当前排名': current_rank,
    #                     '上榜时间': event_time
    #                 }
    #             )
    #             events.append(event)
    #
    #         except Exception as e:
    #             print(f"处理上榜事件失败（行{idx}）: {e}")
    #             continue
    #
    #     return events


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 1. 初始化检测器（可自定义阈值）
    detector = SentimentEventDetector(
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
    events = detector.detect(symbol=None)

    # 3. 输出检测结果
    print(f"\n=== 情绪事件检测结果 ===")
    print(f"检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"共检测到 {len(events)} 个情绪事件\n")

    # 4. 逐个输出事件详情
    for idx, event in enumerate(events, 1):
        print(f"【事件{idx}】")
        print(f"事件ID：{event.event_id}")
        print(f"股票代码：{event.symbol}")
        print(f"事件类型：{event.event_type.value} -> {event.event_subtype}")
        print(f"事件时间：{event.event_time}（精确到秒）")
        print(f"情绪倾向：{event.sentiment}")
        print(f"影响等级：{event.impact_level.value}")
        print(f"事件描述：{event.event_description}")
        print(f"触发规则：{event.trigger_rule.to_dict() if event.trigger_rule else '无'}")
        print("-" * 80)

