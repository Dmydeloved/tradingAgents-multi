from datetime import datetime, timedelta
import akshare as ak
from typing import Optional, List, Dict
import pandas as pd
import abc

from akshare_test.new_event import ImpactLevel
from webServer.tools.event import FinancialEvent, TriggerRule, EventType


class EventDetector(abc.ABC):
    """事件检测器抽象基类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    @abc.abstractmethod
    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测事件"""
        pass

    def _calculate_impact_level(self, deviation: float) -> ImpactLevel:
        """根据偏离度计算影响等级"""
        abs_dev = abs(deviation)
        if abs_dev > 10:
            return ImpactLevel.CRITICAL
        elif abs_dev > 5:
            return ImpactLevel.HIGH
        elif abs_dev > 2:
            return ImpactLevel.MEDIUM
        else:
            return ImpactLevel.LOW



# ==================== 日线基准指标计算类（无缓存） ====================
class DailyIndicatorCalculator:
    """日线基准指标计算器 - 无缓存，每次调用重新计算"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'price_threshold_lookback': 60,  # 价格波动阈值计算回溯天数
            'volume_lookback': 30,  # 成交量基准计算回溯天数
            'volatility_lookback': 100,  # 波动率基准计算回溯天数
            'volatility_percentile': 95,  # 波动率分位数（95%）
            'ma_periods': [5, 10, 20, 60],  # 均线周期
            'limit_move_threshold': 9.9,  # 涨跌停阈值（%）
        }
        self.config = {**default_config, **(config or {})}

    def get_daily_indicators(self, symbol: str) -> Optional[Dict]:
        """获取指定股票的日线基准指标（每次重新计算）"""
        # 获取日线数据
        daily_df = self._get_daily_data(symbol)
        if daily_df is None or daily_df.empty:
            return None

        # 计算各类基准指标
        indicators = {
            "price_jump_threshold": self._calc_price_jump_threshold(daily_df),
            "volume_benchmark": self._calc_volume_benchmark(daily_df),
            "volume_multiplier": self.config.get("volume_multiplier", 2.0),
            "volatility_threshold": self._calc_volatility_threshold(daily_df),
            "ma_values": self._calc_ma_values(daily_df),
            "limit_move_threshold": self.config["limit_move_threshold"],
            "latest_daily_close": daily_df.iloc[-1]["收盘"],  # 最新日线收盘价
            "calc_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 指标计算时间
        }
        print("indicators=================================================")
        print(indicators)
        print("\n")
        return indicators

    def _get_daily_data(self, symbol: str, days: int = 120) -> Optional[pd.DataFrame]:
        """获取标准化的日线数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period='daily',
                start_date=start_date,
                end_date=end_date,
                adjust='qfq'
            )

            if df is None or df.empty:
                return None

            # 标准化列名和计算涨跌幅
            df = df.rename(columns={
                '日期': '日期',
                '开盘': '开盘',
                '收盘': '收盘',
                '最高': '最高',
                '最低': '最低',
                '成交量': '成交量',
                '涨跌幅': '涨跌幅'
            })

            # 确保涨跌幅字段存在
            if '涨跌幅' not in df.columns:
                df['涨跌幅'] = df['收盘'].pct_change() * 100

            # 转换日期格式
            df['日期'] = pd.to_datetime(df['日期'])
            return df

        except Exception as e:
            print(f"获取日线数据失败 {symbol}: {e}")
            return None

    def _calc_price_jump_threshold(self, df: pd.DataFrame) -> float:
        """计算价格波动基准阈值（过去N天涨跌幅的90%分位数）"""
        lookback = self.config["price_threshold_lookback"]
        recent_returns = df['涨跌幅'].iloc[-lookback:].abs()
        return float(recent_returns.quantile(0.9))  # 取90%分位数作为阈值

    def _calc_volume_benchmark(self, df: pd.DataFrame) -> float:
        """计算成交量基准（过去N天平均成交量）"""
        lookback = self.config["volume_lookback"]
        recent_volume = df['成交量'].iloc[-lookback:]
        return float(recent_volume.mean())

    def _calc_volatility_threshold(self, df: pd.DataFrame) -> float:
        """计算波动率基准阈值（过去N天收益率的指定分位数）"""
        lookback = self.config["volatility_lookback"]
        percentile = self.config["volatility_percentile"] / 100

        # 计算日收益率
        df['returns'] = df['收盘'].pct_change()
        recent_returns = df['returns'].iloc[-lookback:].abs().dropna()

        if recent_returns.empty:
            return 0.02  # 默认阈值2%

        return float(recent_returns.quantile(percentile))

    def _calc_ma_values(self, df: pd.DataFrame) -> Dict[int, float]:
        """计算各周期均线的最新值"""
        ma_values = {}
        for period in self.config["ma_periods"]:
            if len(df) >= period:
                ma_values[period] = float(df['收盘'].rolling(window=period).mean().iloc[-1])
        return ma_values

# ==================== 交易类事件检测器（无缓存） ====================
class TradingEventDetector(EventDetector):
    """市场交易类事件检测器
    逻辑：先通过日线计算基准指标 → 实时数据对比基准指标 → 触发事件（无缓存）
    """

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'volume_multiplier': 2.0,  # 成交量异动倍数（叠加到日线基准）
            'real_time_period': '1',  # 实时数据周期（1分钟）
        }
        super().__init__({**default_config, **(config or {})})

        # 初始化日线指标计算器
        self.indicator_calculator = DailyIndicatorCalculator({
            'volume_multiplier': self.config['volume_multiplier']
        })

    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测交易类事件（核心逻辑）"""
        events = []

        # 1. 获取日线基准指标（事件判断的参考标准）
        daily_indicators = self.indicator_calculator.get_daily_indicators(symbol)
        if not daily_indicators:
            print(f"无法获取{symbol}的日线基准指标，跳过事件检测")
            return events

        # 2. 获取实时数据（分钟线/最新报价）
        real_time_df = self._get_real_time_data(symbol)
        if real_time_df is None or real_time_df.empty:
            print(f"无法获取{symbol}的实时数据，跳过事件检测")
            return events

        # 3. 基于「日线指标+实时数据」检测各类事件
        events.extend(self._detect_price_jump(symbol, daily_indicators, real_time_df))
        events.extend(self._detect_volume_anomaly(symbol, daily_indicators, real_time_df))
        events.extend(self._detect_limit_move(symbol, daily_indicators, real_time_df))
        events.extend(self._detect_ma_cross(symbol, daily_indicators, real_time_df))
        events.extend(self._detect_volatility_anomaly(symbol, daily_indicators, real_time_df))

        return events

    def _get_real_time_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取实时分钟线数据（无缓存，每次重新获取）"""
        try:
            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                period=self.config['real_time_period'],
                adjust='qfq'
            )

            if df is None or df.empty:
                return None

            # 标准化处理
            df = df.rename(columns={
                '时间': '时间',
                '开盘': '开盘',
                '收盘': '收盘',
                '最高': '最高',
                '最低': '最低',
                '成交量': '成交量'
            })

            # 只保留当天数据，转换时间格式
            df['时间'] = pd.to_datetime(df['时间'])
            today = datetime.now().date()
            df = df[df['时间'].dt.date == today].copy()

            # 计算实时涨跌幅（相对最新日线收盘价）
            latest_daily_close = self.indicator_calculator.get_daily_indicators(symbol)['latest_daily_close']
            df['real_time_pct_change'] = (df['收盘'] - latest_daily_close) / latest_daily_close * 100

            # 计算分钟级涨跌幅
            df['minute_pct_change'] = df['收盘'].pct_change() * 100

            return df

        except Exception as e:
            print(f"获取{symbol}实时数据失败: {e}")
            return None

    def _detect_price_jump(self, symbol: str, daily_indicators: Dict, real_time_df: pd.DataFrame) -> List[FinancialEvent]:
        """检测价格跳空事件：实时涨跌幅 > 日线计算的波动阈值"""
        events = []
        price_threshold = daily_indicators['price_jump_threshold']

        # 取最新的实时数据
        latest_real_time = real_time_df.iloc[-1]
        real_time_pct = latest_real_time['real_time_pct_change']
        event_time = latest_real_time['时间'].strftime("%Y-%m-%d %H:%M:%S")

        if abs(real_time_pct) >= price_threshold:
            # 构建触发规则（实时值 vs 日线阈值）
            trigger_rule = TriggerRule(
                metric="real_time_price_jump",
                value=round(real_time_pct, 2),
                threshold=round(price_threshold, 2),
                operator=">" if real_time_pct > 0 else "<"
            )

            # 构建事件
            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(symbol, event_time, "price_jump"),
                symbol=symbol,
                event_type=EventType.TRADING,
                event_subtype="price_jump",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="positive" if real_time_pct > 0 else "negative",
                impact_level=self._calculate_impact_level(real_time_pct),
                event_description=f"实时价格波动{real_time_pct:.2f}%，超过日线基准阈值{price_threshold:.2f}%",
                raw_data={
                    "real_time_close": float(latest_real_time['收盘']),
                    "daily_close_benchmark": float(daily_indicators['latest_daily_close']),
                    "price_threshold": float(price_threshold),
                    "real_time_pct_change": float(real_time_pct)
                }
            )
            events.append(event)

        return events

    def _detect_volume_anomaly(self, symbol: str, daily_indicators: Dict, real_time_df: pd.DataFrame) -> List[FinancialEvent]:
        """检测成交量异动：实时成交量 > 日线平均成交量 × 倍数"""
        events = []
        volume_benchmark = daily_indicators['volume_benchmark']
        volume_multiplier = daily_indicators['volume_multiplier']
        volume_threshold = volume_benchmark * volume_multiplier

        # 取最新实时成交量
        latest_real_time = real_time_df.iloc[-1]
        real_time_volume = latest_real_time['成交量']
        event_time = latest_real_time['时间'].strftime("%Y-%m-%d %H:%M:%S")

        if real_time_volume >= volume_threshold:
            volume_ratio = real_time_volume / volume_benchmark

            trigger_rule = TriggerRule(
                metric="real_time_volume_anomaly",
                value=round(volume_ratio, 2),
                threshold=round(volume_multiplier, 2),
                operator=">"
            )

            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(symbol, event_time, "volume_anomaly"),
                symbol=symbol,
                event_type=EventType.TRADING,
                event_subtype="volume_anomaly",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="neutral",
                impact_level=self._calculate_impact_level((volume_ratio - 1) * 100),
                event_description=f"实时成交量{real_time_volume:.0f}，为日线平均成交量({volume_benchmark:.0f})的{volume_ratio:.2f}倍",
                raw_data={
                    "real_time_volume": float(real_time_volume),
                    "daily_volume_benchmark": float(volume_benchmark),
                    "volume_multiplier": float(volume_multiplier),
                    "volume_threshold": float(volume_threshold)
                }
            )
            events.append(event)

        return events

    def _detect_limit_move(self, symbol: str, daily_indicators: Dict, real_time_df: pd.DataFrame) -> List[FinancialEvent]:
        """检测涨跌停事件：实时价格接近涨跌停阈值（日线计算的9.9%）"""
        events = []
        limit_threshold = daily_indicators['limit_move_threshold']

        latest_real_time = real_time_df.iloc[-1]
        real_time_pct = latest_real_time['real_time_pct_change']
        event_time = latest_real_time['时间'].strftime("%Y-%m-%d %H:%M:%S")

        is_limit_up = real_time_pct >= limit_threshold
        is_limit_down = real_time_pct <= -limit_threshold

        if is_limit_up or is_limit_down:
            subtype = "limit_up" if is_limit_up else "limit_down"
            trigger_rule = TriggerRule(
                metric="real_time_limit_move",
                value=round(real_time_pct, 2),
                threshold=limit_threshold if is_limit_up else -limit_threshold,
                operator=">" if is_limit_up else "<"
            )

            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(symbol, event_time, subtype),
                symbol=symbol,
                event_type=EventType.TRADING,
                event_subtype=subtype,
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="positive" if is_limit_up else "negative",
                impact_level=ImpactLevel.CRITICAL,
                event_description=f"实时{('涨停' if is_limit_up else '跌停')}，涨跌幅{real_time_pct:.2f}%（阈值{limit_threshold}%）",
                raw_data={
                    "real_time_close": float(latest_real_time['收盘']),
                    "real_time_pct_change": float(real_time_pct),
                    "limit_threshold": float(limit_threshold)
                }
            )
            events.append(event)

        return events

    def _detect_ma_cross(self, symbol: str, daily_indicators: Dict, real_time_df: pd.DataFrame) -> List[FinancialEvent]:
        """检测均线穿越事件：实时价格穿越日线计算的均线值"""
        events = []
        ma_values = daily_indicators['ma_values']
        latest_real_time = real_time_df.iloc[-1]
        real_time_close = latest_real_time['收盘']
        event_time = latest_real_time['时间'].strftime("%Y-%m-%d %H:%M:%S")

        # 遍历各周期均线
        for ma_period, ma_value in ma_values.items():
            # 上穿均线
            if real_time_close > ma_value:
                deviation = (real_time_close - ma_value) / ma_value * 100
                trigger_rule = TriggerRule(
                    metric=f"real_time_ma{ma_period}_cross",
                    value=round(deviation, 2),
                    threshold=0.0,
                    operator=">"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, f"ma{ma_period}_cross_up"),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype=f"ma{ma_period}_cross_up",
                    event_time=event_time,
                    trigger_rule=trigger_rule,
                    sentiment="positive",
                    impact_level=self._calculate_impact_level(deviation),
                    event_description=f"实时价格{real_time_close:.2f}上穿日线MA{ma_period}均线({ma_value:.2f})，偏离{deviation:.2f}%",
                    raw_data={
                        "real_time_close": float(real_time_close),
                        f"daily_MA{ma_period}": float(ma_value),
                        "deviation_pct": float(deviation)
                    }
                )
                events.append(event)

            # 下穿均线
            elif real_time_close < ma_value:
                deviation = (real_time_close - ma_value) / ma_value * 100
                trigger_rule = TriggerRule(
                    metric=f"real_time_ma{ma_period}_cross",
                    value=round(deviation, 2),
                    threshold=0.0,
                    operator="<"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, f"ma{ma_period}_cross_down"),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype=f"ma{ma_period}_cross_down",
                    event_time=event_time,
                    trigger_rule=trigger_rule,
                    sentiment="negative",
                    impact_level=self._calculate_impact_level(abs(deviation)),
                    event_description=f"实时价格{real_time_close:.2f}下穿日线MA{ma_period}均线({ma_value:.2f})，偏离{deviation:.2f}%",
                    raw_data={
                        "real_time_close": float(real_time_close),
                        f"daily_MA{ma_period}": float(ma_value),
                        "deviation_pct": float(deviation)
                    }
                )
                events.append(event)

        return events

    def _detect_volatility_anomaly(self, symbol: str, daily_indicators: Dict, real_time_df: pd.DataFrame) -> List[FinancialEvent]:
        """检测波动率异常：实时分钟涨跌幅 > 日线计算的波动率阈值"""
        events = []
        volatility_threshold = daily_indicators['volatility_threshold']
        volatility_threshold_pct = volatility_threshold * 100  # 转换为百分比

        latest_real_time = real_time_df.iloc[-1]
        minute_pct_change = latest_real_time['minute_pct_change']
        event_time = latest_real_time['时间'].strftime("%Y-%m-%d %H:%M:%S")

        if pd.isna(minute_pct_change):
            return events

        if abs(minute_pct_change) >= volatility_threshold_pct:
            trigger_rule = TriggerRule(
                metric="real_time_volatility_anomaly",
                value=round(abs(minute_pct_change), 2),
                threshold=round(volatility_threshold_pct, 2),
                operator=">"
            )

            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(symbol, event_time, "volatility_anomaly"),
                symbol=symbol,
                event_type=EventType.TRADING,
                event_subtype="volatility_anomaly",
                event_time=event_time,
                trigger_rule=trigger_rule,
                sentiment="neutral",
                impact_level=ImpactLevel.HIGH,
                event_description=f"实时分钟波动率{minute_pct_change:.2f}%，超过日线95%分位数阈值{volatility_threshold_pct:.2f}%",
                raw_data={
                    "minute_pct_change": float(minute_pct_change),
                    "volatility_threshold_pct": float(volatility_threshold_pct),
                    "real_time_close": float(latest_real_time['收盘'])
                }
            )
            events.append(event)

        return events


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 初始化检测器
    detector = TradingEventDetector()

    # 检测单只股票的事件（例如：贵州茅台 600519）
    symbol = "600519"
    events = detector.detect(symbol)

    # 输出事件结果
    print(f"检测到{symbol}的事件数量：{len(events)}")
    for event in events:
        print("\n=== 事件详情 ===")
        print(event)
        print(f"事件ID：{event.event_id}")
        print(f"事件类型：{event.event_subtype}")
        print(f"影响等级：{event.impact_level.value}")
        print(f"描述：{event.event_description}")
        print(f"触发规则：{event.trigger_rule.to_dict() if event.trigger_rule else '无'}")