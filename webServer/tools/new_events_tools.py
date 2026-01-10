"""
金融事件提取系统
从AkShare数据源中提取和分析各类金融事件
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Literal
import akshare as ak
import pandas as pd
import numpy as np
from enum import Enum


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
    """触发规则"""
    metric: str  # 指标名称
    value: float  # 实际值
    threshold: float  # 阈值
    operator: str = ">"  # 比较操作符

    def to_dict(self) -> Dict:
        return asdict(self)


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
        result = asdict(self)
        if self.trigger_rule:
            result['trigger_rule'] = self.trigger_rule.to_dict()
        return result

    @staticmethod
    def generate_event_id(symbol: str, event_time: str, event_subtype: str) -> str:
        """生成事件ID"""
        time_str = event_time.replace("-", "").replace(":", "").replace(" ", "_")[:15]
        return f"{symbol}_{time_str}_{event_subtype}"


class EventDetector(ABC):
    """事件检测器抽象基类"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    @abstractmethod
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


# ==================== 1. 市场交易类事件检测器 ====================

class TradingEventDetector(EventDetector):
    """市场交易类事件检测器"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'daily_price_threshold': 7.0,  # 日线涨跌幅阈值 (%)
            'minute_price_threshold': 3.0,  # 分钟涨跌幅阈值 (%)
            'volume_multiplier': 2.0,  # 成交量倍数
            'volume_lookback': 30,  # 成交量回溯天数
            'volatility_percentile': 95,  # 波动率分位数
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测所有交易类事件"""
        events = []

        # 获取日线数据
        try:
            daily_df = self._get_daily_data(symbol)
            if daily_df is not None and not daily_df.empty:
                events.extend(self._detect_price_jump(symbol, daily_df, 'daily'))
                events.extend(self._detect_volume_anomaly(symbol, daily_df))
                events.extend(self._detect_limit_move(symbol, daily_df))
                events.extend(self._detect_ma_cross(symbol, daily_df))
        except Exception as e:
            print(f"检测日线事件失败 {symbol}: {e}")

        return events

    def _get_daily_data(self, symbol: str, days: int = 100) -> Optional[pd.DataFrame]:
        """获取实时数据（替代原日线数据）"""
        try:
            # 使用实时行情接口
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return None

            # 筛选指定股票
            df = df[df['代码'] == symbol]
            if df.empty:
                return None

            # 将实时数据格式转换为原来的日线数据格式，保持接口一致
            df_converted = pd.DataFrame({
                '日期': [datetime.now().strftime('%Y-%m-%d')],
                '开盘': df['今开'].values,
                '收盘': df['最新价'].values,
                '最高': df['最高'].values,
                '最低': df['最低'].values,
                '成交量': df['成交量'].values,
                '成交额': df['成交额'].values,
                '涨跌幅': df['涨跌幅'].values,
                '涨跌额': df['涨跌额'].values,
                '昨收': df['昨收'].values,
            })
            df_converted['pct_change'] = df_converted['涨跌幅']

            # 如果需要历史数据用于均线等计算，补充分钟数据
            try:
                # 获取最近的分钟数据作为历史
                minute_df = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='qfq')
                if minute_df is not None and not minute_df.empty:
                    # 按小时分组，取每小时的最后一条作为伪日线
                    minute_df['日期'] = pd.to_datetime(minute_df['时间']).dt.floor('H')
                    hourly_df = minute_df.groupby('日期').agg({
                        '开盘': 'first',
                        '收盘': 'last',
                        '最高': 'max',
                        '最低': 'min',
                        '成交量': 'sum',
                    }).reset_index()
                    hourly_df['日期'] = hourly_df['日期'].dt.strftime('%Y-%m-%d %H:%M:%S')
                    hourly_df['pct_change'] = hourly_df['收盘'].pct_change() * 100

                    # 合并实时数据和历史数据
                    df_converted = pd.concat([hourly_df.tail(days-1), df_converted], ignore_index=True)
            except Exception as hist_error:
                print(f"获取历史分钟数据失败，仅使用实时数据: {hist_error}")

            return df_converted

        except Exception as e:
            print(f"获取实时数据失败 {symbol}: {e}")
        return None

    def _detect_price_jump(self, symbol: str, df: pd.DataFrame, period: str) -> List[FinancialEvent]:
        """检测价格剧烈波动事件"""
        events = []
        threshold = self.config['daily_price_threshold'] if period == 'daily' else self.config['minute_price_threshold']

        for idx, row in df.iterrows():
            if pd.isna(row['pct_change']):
                continue

            abs_change = abs(row['pct_change'])
            if abs_change >= threshold:
                event_time = str(row['日期'])
                trigger = TriggerRule(
                    metric=f"pct_change_{period}",
                    value=round(row['pct_change'], 2),
                    threshold=threshold,
                    operator=">" if row['pct_change'] > 0 else "<"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, "price_jump"),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype="price_jump",
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="positive" if row['pct_change'] > 0 else "negative",
                    impact_level=self._calculate_impact_level(row['pct_change']),
                    event_description=f"{period}涨跌幅{row['pct_change']:.2f}%，超过阈值{threshold}%",
                    raw_data={
                        'open': float(row['开盘']),
                        'high': float(row['最高']),
                        'low': float(row['最低']),
                        'close': float(row['收盘']),
                        'volume': float(row['成交量']),
                    }
                )
                events.append(event)

        return events

    def _detect_volume_anomaly(self, symbol: str, df: pd.DataFrame) -> List[FinancialEvent]:
        """检测成交量异动事件"""
        events = []
        lookback = self.config['volume_lookback']
        multiplier = self.config['volume_multiplier']

        if len(df) < lookback:
            return events

        # 计算移动平均成交量
        df['volume_ma'] = df['成交量'].rolling(window=lookback).mean()

        for idx, row in df.tail(10).iterrows():  # 只检查最近10天
            if pd.isna(row['volume_ma']):
                continue

            if row['成交量'] > row['volume_ma'] * multiplier:
                event_time = str(row['日期'])
                ratio = row['成交量'] / row['volume_ma']

                trigger = TriggerRule(
                    metric="volume_ratio",
                    value=round(ratio, 2),
                    threshold=multiplier,
                    operator=">"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, "volume_anomaly"),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype="volume_anomaly",
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="neutral",
                    impact_level=self._calculate_impact_level((ratio - 1) * 100),
                    event_description=f"成交量为{lookback}日均量的{ratio:.2f}倍",
                    raw_data={
                        'volume': float(row['成交量']),
                        'volume_ma': float(row['volume_ma']),
                        'close': float(row['收盘']),
                    }
                )
                events.append(event)

        return events

    def _detect_limit_move(self, symbol: str, df: pd.DataFrame) -> List[FinancialEvent]:
        """检测涨停/跌停事件"""
        events = []

        for idx, row in df.tail(10).iterrows():
            pct_change = row['pct_change']
            if pd.isna(pct_change):
                continue

            # 判断涨停 (约9.9%以上) 或跌停 (约-9.9%以下)
            is_limit_up = pct_change >= 9.9
            is_limit_down = pct_change <= -9.9

            if is_limit_up or is_limit_down:
                event_time = str(row['日期'])
                subtype = "limit_up" if is_limit_up else "limit_down"

                trigger = TriggerRule(
                    metric="pct_change",
                    value=round(pct_change, 2),
                    threshold=9.9 if is_limit_up else -9.9,
                    operator=">" if is_limit_up else "<"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, subtype),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype=subtype,
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="positive" if is_limit_up else "negative",
                    impact_level=ImpactLevel.HIGH,
                    event_description=f"{'涨停' if is_limit_up else '跌停'}，涨跌幅{pct_change:.2f}%",
                    raw_data={
                        'close': float(row['收盘']),
                        'high': float(row['最高']),
                        'low': float(row['最低']),
                    }
                )
                events.append(event)

        return events

    def _detect_ma_cross(self, symbol: str, df: pd.DataFrame) -> List[FinancialEvent]:
        """检测均线突破事件"""
        events = []
        ma_periods = [5, 10, 20, 60]

        # 计算各周期均线
        for period in ma_periods:
            df[f'MA{period}'] = df['收盘'].rolling(window=period).mean()

        if len(df) < 2:
            return events

        # 检查最近一天的突破
        latest = df.iloc[-1]
        previous = df.iloc[-2]

        for period in ma_periods:
            ma_col = f'MA{period}'
            if pd.isna(latest[ma_col]) or pd.isna(previous[ma_col]):
                continue

            # 上穿
            if previous['收盘'] <= previous[ma_col] and latest['收盘'] > latest[ma_col]:
                event_time = str(latest['日期'])
                deviation = ((latest['收盘'] - latest[ma_col]) / latest[ma_col]) * 100

                trigger = TriggerRule(
                    metric=f"price_vs_MA{period}",
                    value=round(deviation, 2),
                    threshold=0,
                    operator=">"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, f"ma{period}_cross_up"),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype="ma_cross_up",
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="positive",
                    impact_level=self._calculate_impact_level(deviation),
                    event_description=f"价格上穿MA{period}均线，当前价格{latest['收盘']:.2f}，MA{period}={latest[ma_col]:.2f}",
                    raw_data={
                        'close': float(latest['收盘']),
                        f'MA{period}': float(latest[ma_col]),
                    }
                )
                events.append(event)

            # 下穿
            elif previous['收盘'] >= previous[ma_col] and latest['收盘'] < latest[ma_col]:
                event_time = str(latest['日期'])
                deviation = ((latest['收盘'] - latest[ma_col]) / latest[ma_col]) * 100

                trigger = TriggerRule(
                    metric=f"price_vs_MA{period}",
                    value=round(deviation, 2),
                    threshold=0,
                    operator="<"
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, f"ma{period}_cross_down"),
                    symbol=symbol,
                    event_type=EventType.TRADING,
                    event_subtype="ma_cross_down",
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="negative",
                    impact_level=self._calculate_impact_level(abs(deviation)),
                    event_description=f"价格下穿MA{period}均线，当前价格{latest['收盘']:.2f}，MA{period}={latest[ma_col]:.2f}",
                    raw_data={
                        'close': float(latest['收盘']),
                        f'MA{period}': float(latest[ma_col]),
                    }
                )
                events.append(event)

        return events


# ==================== 2. 资金流向类事件检测器 ====================

class CapitalFlowEventDetector(EventDetector):
    """资金流向类事件检测器"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'northbound_percentile': 95,  # 北向资金分位数阈值
            'northbound_lookback': 60,  # 北向资金回溯天数
            'margin_consecutive_days': 3,  # 融资余额连续增加天数
            'block_trade_deviation': 2.0,  # 大宗交易价格偏离百分比
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测所有资金流向事件"""
        events = []

        try:
            # 检测北向资金
            events.extend(self._detect_northbound_flow(symbol))
        except Exception as e:
            print(f"检测北向资金事件失败 {symbol}: {e}")

        try:
            # 检测融资融券
            events.extend(self._detect_margin_trading(symbol))
        except Exception as e:
            print(f"检测融资融券事件失败 {symbol}: {e}")

        try:
            # 检测大宗交易
            events.extend(self._detect_block_trade(symbol))
        except Exception as e:
            print(f"检测大宗交易事件失败 {symbol}: {e}")

        return events

    def _detect_northbound_flow(self, symbol: str) -> List[FinancialEvent]:
        """检测北向资金异常流入/流出"""
        events = []

        try:
            # 获取北向资金个股数据
            df = ak.stock_hsgt_individual_em(symbol=symbol)
            if df is None or df.empty:
                return events

            lookback = self.config['northbound_lookback']
            df = df.tail(lookback)

            # 计算分位数
            if '净买入' in df.columns:
                percentile_value = df['净买入'].quantile(self.config['northbound_percentile'] / 100)

                # 检查最近几天
                for idx, row in df.tail(5).iterrows():
                    net_buy = row['净买入']
                    if abs(net_buy) >= abs(percentile_value):
                        event_time = str(row['日期']) if '日期' in row else datetime.now().strftime('%Y-%m-%d')
                        subtype = "northbound_inflow" if net_buy > 0 else "northbound_outflow"

                        trigger = TriggerRule(
                            metric="net_buy",
                            value=round(float(net_buy), 2),
                            threshold=round(float(percentile_value), 2),
                            operator=">" if net_buy > 0 else "<"
                        )

                        event = FinancialEvent(
                            event_id=FinancialEvent.generate_event_id(symbol, event_time, subtype),
                            symbol=symbol,
                            event_type=EventType.CAPITAL_FLOW,
                            event_subtype=subtype,
                            event_time=event_time,
                            trigger_rule=trigger,
                            sentiment="positive" if net_buy > 0 else "negative",
                            impact_level=ImpactLevel.HIGH,
                            event_description=f"北向资金{'流入' if net_buy > 0 else '流出'}{abs(net_buy):.2f}万元，超过{lookback}日{self.config['northbound_percentile']}分位数",
                            raw_data={
                                'net_buy': float(net_buy),
                                'percentile_value': float(percentile_value),
                            }
                        )
                        events.append(event)
        except Exception as e:
            print(f"北向资金检测异常: {e}")

        return events

    def _detect_margin_trading(self, symbol: str) -> List[FinancialEvent]:
        """检测融资融券异常"""
        events = []

        try:
            # 使用 stock_margin_underlying_info_szse 获取深交所融资融券标的信息
            # 或使用 stock_margin_detail 获取个股融资融券详情
            # 由于API限制，这里简化处理，仅在有数据时分析
            try:
                # 尝试获取融资融券余额数据
                df = ak.stock_margin_detail_fund_em(symbol=symbol)
            except:
                # 如果上述API不可用，返回空结果
                return events

            if df is None or df.empty:
                return events

            # 确保有日期列并排序
            date_col = None
            for col in ['交易日期', '日期', '信用交易日期']:
                if col in df.columns:
                    date_col = col
                    df = df.sort_values(col)
                    break

            if date_col is None:
                return events

            # 检查融资余额连续增加
            consecutive_days = self.config['margin_consecutive_days']

            # 查找融资余额列（可能是不同的列名）
            margin_col = None
            for col in ['融资余额(元)', '融资余额', '本日融资余额(元)', '融资余额(亿元)']:
                if col in df.columns:
                    margin_col = col
                    break

            if margin_col is None or len(df) < consecutive_days:
                return events

            recent = df.tail(consecutive_days)
            margin_balance = recent[margin_col].astype(float).tolist()

            # 检查是否连续增加
            is_consecutive_increase = all(
                margin_balance[i] < margin_balance[i + 1]
                for i in range(len(margin_balance) - 1)
            )

            if is_consecutive_increase:
                latest = recent.iloc[-1]
                event_time = str(latest[date_col])
                increase_pct = ((margin_balance[-1] - margin_balance[0]) / margin_balance[0]) * 100

                trigger = TriggerRule(
                    metric="margin_balance_consecutive_increase",
                    value=consecutive_days,
                    threshold=consecutive_days,
                    operator=">="
                )

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, "margin_increase"),
                    symbol=symbol,
                    event_type=EventType.CAPITAL_FLOW,
                    event_subtype="margin_consecutive_increase",
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="positive",
                    impact_level=self._calculate_impact_level(increase_pct),
                    event_description=f"融资余额连续{consecutive_days}日增加，累计增长{increase_pct:.2f}%",
                    raw_data={
                        'margin_balance_current': float(margin_balance[-1]),
                        'margin_balance_start': float(margin_balance[0]),
                        'increase_pct': round(increase_pct, 2),
                    }
                )
                events.append(event)
        except Exception as e:
            print(f"融资融券检测异常: {e}")

        return events

    def _detect_block_trade(self, symbol: str) -> List[FinancialEvent]:
        """检测大宗交易价格偏离"""
        events = []

        try:
            # 使用 stock_dzjy_mrmx 获取每日大宗交易明细
            # 注意：此API不接受symbol参数，需要指定日期范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

            try:
                df = ak.stock_dzjy_mrmx(start_date=start_date, end_date=end_date)
            except Exception as api_error:
                # API调用失败，静默返回
                return events

            if df is None or df.empty:
                return events

            # 过滤出指定股票的数据
            symbol_col = None
            for col in ['证券代码', '股票代码', '代码']:
                if col in df.columns:
                    symbol_col = col
                    break

            if symbol_col is None:
                return events

            df = df[df[symbol_col] == symbol]

            if df.empty:
                return events

            deviation_threshold = self.config['block_trade_deviation']

            for idx, row in df.tail(10).iterrows():
                # 查找价格列（列名可能不同）
                trade_price_col = None
                close_price_col = None

                for col in ['成交价', '成交价格', '价格']:
                    if col in row and pd.notna(row[col]):
                        trade_price_col = col
                        break

                for col in ['收盘价', '当日收盘价', '前收盘']:
                    if col in row and pd.notna(row[col]):
                        close_price_col = col
                        break

                if trade_price_col and close_price_col:
                    try:
                        trade_price = float(row[trade_price_col])
                        close_price = float(row[close_price_col])

                        if close_price == 0:
                            continue

                        deviation = ((trade_price - close_price) / close_price) * 100

                        if abs(deviation) >= deviation_threshold:
                            # 查找日期列
                            event_time = None
                            for date_col in ['交易日期', '日期', '成交日期']:
                                if date_col in row and pd.notna(row[date_col]):
                                    event_time = str(row[date_col])
                                    break
                            if not event_time:
                                event_time = datetime.now().strftime('%Y-%m-%d')

                            trigger = TriggerRule(
                                metric="price_deviation",
                                value=round(deviation, 2),
                                threshold=deviation_threshold,
                                operator=">" if deviation > 0 else "<"
                            )

                            event = FinancialEvent(
                                event_id=FinancialEvent.generate_event_id(symbol, event_time, "block_trade_deviation"),
                                symbol=symbol,
                                event_type=EventType.CAPITAL_FLOW,
                                event_subtype="block_trade_price_deviation",
                                event_time=event_time,
                                trigger_rule=trigger,
                                sentiment="neutral",
                                impact_level=self._calculate_impact_level(abs(deviation)),
                                event_description=f"大宗交易价格{trade_price:.2f}偏离市价{abs(deviation):.2f}%",
                                raw_data={
                                    'trade_price': trade_price,
                                    'close_price': close_price,
                                    'volume': float(row['成交量']) if '成交量' in row and pd.notna(row['成交量']) else 0,
                                }
                            )
                            events.append(event)
                    except (ValueError, TypeError):
                        continue

        except Exception as e:
            print(f"大宗交易检测异常: {e}")

        return events


# ==================== 3. 公司事件检测器 ====================

class CompanyEventDetector(EventDetector):
    """公司事件检测器"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'profit_change_threshold': 20.0,  # 净利润变化阈值 (%)
            'unlock_ratio_threshold': 5.0,  # 解禁占流通盘比例阈值 (%)
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测所有公司事件"""
        events = []

        try:
            events.extend(self._detect_performance_forecast(symbol))
        except Exception as e:
            print(f"检测业绩预告失败 {symbol}: {e}")

        try:
            events.extend(self._detect_unlock_shares(symbol))
        except Exception as e:
            print(f"检测限售解禁失败 {symbol}: {e}")

        return events

    def _detect_performance_forecast(self, symbol: str) -> List[FinancialEvent]:
        """检测业绩预告事件"""
        events = []

        try:
            # stock_yjyg_em() 不需要 symbol 参数，返回所有股票的业绩预告
            df = ak.stock_yjyg_em()
            if df is None or df.empty:
                return events

            # 过滤出指定股票的数据
            if '股票代码' in df.columns:
                df = df[df['股票代码'] == symbol]
            elif '代码' in df.columns:
                df = df[df['代码'] == symbol]
            else:
                return events

            if df.empty:
                return events

            for idx, row in df.tail(5).iterrows():
                forecast_type = row.get('预测类型', '')
                event_time = str(row.get('公告日期', datetime.now().strftime('%Y-%m-%d')))

                # 定义预告类型和情绪的映射
                type_mapping = {
                    '预增': ('positive', '业绩预增'),
                    '预减': ('negative', '业绩预减'),
                    '扭亏': ('positive', '扭亏为盈'),
                    '续亏': ('negative', '继续亏损'),
                    '略增': ('positive', '业绩略增'),
                    '略减': ('negative', '业绩略减'),
                }

                if forecast_type in type_mapping:
                    sentiment, desc = type_mapping[forecast_type]

                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(symbol, event_time, "performance_forecast"),
                        symbol=symbol,
                        event_type=EventType.COMPANY,
                        event_subtype="performance_forecast",
                        event_time=event_time,
                        sentiment=sentiment,
                        impact_level=ImpactLevel.HIGH if forecast_type in ['预增', '预减', '扭亏', '续亏'] else ImpactLevel.MEDIUM,
                        event_description=f"{desc}：{row.get('预测内容', '')}",
                        raw_data={
                            'forecast_type': forecast_type,
                            'forecast_content': str(row.get('预测内容', '')),
                            'report_period': str(row.get('报告期', '')),
                        }
                    )
                    events.append(event)
        except Exception as e:
            print(f"业绩预告检测异常: {e}")

        return events

    def _detect_unlock_shares(self, symbol: str) -> List[FinancialEvent]:
        """检测限售解禁事件"""
        events = []

        try:
            # 使用正确的 API: stock_restricted_release_queue_em (限售解禁排队)
            df = ak.stock_restricted_release_queue_em(symbol=symbol)
            if df is None or df.empty:
                return events

            threshold = self.config['unlock_ratio_threshold']

            for idx, row in df.tail(5).iterrows():
                # 查找解禁比例列（可能有不同的列名）
                unlock_ratio = None
                for col in ['解禁占总股本比例', '占总股本比例', '解禁市值占总市值比例']:
                    if col in row:
                        unlock_ratio = float(str(row[col]).replace('%', ''))
                        break

                if unlock_ratio is None:
                    continue

                if unlock_ratio >= threshold:
                    # 查找日期列
                    event_time = None
                    for date_col in ['解禁日期', '日期', '上市日期']:
                        if date_col in row:
                            event_time = str(row[date_col])
                            break
                    if not event_time:
                        event_time = datetime.now().strftime('%Y-%m-%d')

                    trigger = TriggerRule(
                        metric="unlock_ratio",
                        value=round(unlock_ratio, 2),
                        threshold=threshold,
                        operator=">="
                    )

                    # 查找解禁数量
                    unlock_shares = 0
                    for shares_col in ['解禁数量', '解禁股数', '实际解禁数量']:
                        if shares_col in row:
                            unlock_shares = float(row[shares_col])
                            break

                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(symbol, event_time, "share_unlock"),
                        symbol=symbol,
                        event_type=EventType.COMPANY,
                        event_subtype="share_unlock",
                        event_time=event_time,
                        trigger_rule=trigger,
                        sentiment="negative",
                        impact_level=self._calculate_impact_level(unlock_ratio),
                        event_description=f"限售股解禁，占总股本{unlock_ratio:.2f}%",
                        raw_data={
                            'unlock_ratio': unlock_ratio,
                            'unlock_shares': unlock_shares,
                        }
                    )
                    events.append(event)
        except Exception as e:
            print(f"限售解禁检测异常: {e}")

        return events


# ==================== 4. 行业周期事件检测器 ====================

class IndustryEventDetector(EventDetector):
    """行业周期事件检测器"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'commodity_threshold': 8.0,  # 大宗商品价格变化阈值 (%)
            'industry_index_threshold': 5.0,  # 行业指数变化阈值 (%)
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, commodity: str = None, **kwargs) -> List[FinancialEvent]:
        """检测行业周期事件"""
        events = []

        try:
            events.extend(self._detect_commodity_price(commodity))
        except Exception as e:
            print(f"检测大宗商品价格失败: {e}")

        return events

    def _detect_commodity_price(self, commodity: str = None) -> List[FinancialEvent]:
        """检测大宗商品价格波动"""
        events = []

        # 这里需要根据实际的大宗商品代码来获取数据
        # 示例使用期货主力合约
        try:
            # 示例：检测原油期货
            # df = ak.futures_main_sina(symbol="CL", market="nymex")
            # 这里简化处理，实际需要根据commodity参数选择不同的数据源
            pass
        except Exception as e:
            print(f"大宗商品检测异常: {e}")

        return events


# ==================== 5. 宏观事件检测器 ====================

class MacroEventDetector(EventDetector):
    """宏观事件检测器"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'cpi_threshold': 0.5,  # CPI超预期阈值
            'pmi_threshold': 50.0,  # PMI荣枯线
            'pmi_consecutive_months': 2,  # PMI连续月数
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, **kwargs) -> List[FinancialEvent]:
        """检测宏观事件"""
        events = []

        try:
            events.extend(self._detect_cpi())
        except Exception as e:
            print(f"检测CPI事件失败: {e}")

        try:
            events.extend(self._detect_pmi())
        except Exception as e:
            print(f"检测PMI事件失败: {e}")

        return events

    def _detect_cpi(self) -> List[FinancialEvent]:
        """检测通胀事件（CPI）"""
        events = []

        try:
            df = ak.macro_china_cpi()
            if df is None or df.empty:
                return events

            # 分析最近几个月的CPI
            for idx, row in df.tail(3).iterrows():
                if '同比' in row:
                    cpi_yoy = float(row['同比'])
                    event_time = str(row.get('月份', datetime.now().strftime('%Y-%m')))

                    # 判断是否异常
                    if abs(cpi_yoy) >= self.config['cpi_threshold']:
                        trigger = TriggerRule(
                            metric="cpi_yoy",
                            value=round(cpi_yoy, 2),
                            threshold=self.config['cpi_threshold'],
                            operator=">" if cpi_yoy > 0 else "<"
                        )

                        event = FinancialEvent(
                            event_id=FinancialEvent.generate_event_id("MACRO", event_time, "cpi"),
                            symbol="MACRO_CPI",
                            event_type=EventType.MACRO,
                            event_subtype="cpi_change",
                            event_time=event_time,
                            trigger_rule=trigger,
                            sentiment="negative" if abs(cpi_yoy) > 3 else "neutral",
                            impact_level=ImpactLevel.HIGH if abs(cpi_yoy) > 3 else ImpactLevel.MEDIUM,
                            event_description=f"CPI同比{cpi_yoy:.2f}%",
                            raw_data={
                                'cpi_yoy': cpi_yoy,
                                'cpi_mom': float(row.get('环比', 0)),
                            }
                        )
                        events.append(event)
        except Exception as e:
            print(f"CPI检测异常: {e}")

        return events

    def _detect_pmi(self) -> List[FinancialEvent]:
        """检测经济扩张/收缩事件（PMI）"""
        events = []

        try:
            df = ak.macro_china_pmi()
            if df is None or df.empty:
                return events

            threshold = self.config['pmi_threshold']
            consecutive_months = self.config['pmi_consecutive_months']

            # 检查最近几个月PMI是否连续低于50
            recent = df.tail(consecutive_months)
            if len(recent) >= consecutive_months and '制造业PMI' in recent.columns:
                pmi_values = recent['制造业PMI'].tolist()

                # 检查是否连续低于50
                all_below_50 = all(float(val) < threshold for val in pmi_values)

                if all_below_50:
                    latest = recent.iloc[-1]
                    event_time = str(latest.get('月份', datetime.now().strftime('%Y-%m')))
                    latest_pmi = float(latest['制造业PMI'])

                    trigger = TriggerRule(
                        metric="pmi_consecutive_below_50",
                        value=consecutive_months,
                        threshold=consecutive_months,
                        operator=">="
                    )

                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id("MACRO", event_time, "pmi_contraction"),
                        symbol="MACRO_PMI",
                        event_type=EventType.MACRO,
                        event_subtype="economic_contraction",
                        event_time=event_time,
                        trigger_rule=trigger,
                        sentiment="negative",
                        impact_level=ImpactLevel.HIGH,
                        event_description=f"PMI连续{consecutive_months}个月低于{threshold}，当前为{latest_pmi:.1f}",
                        raw_data={
                            'pmi_current': latest_pmi,
                            'pmi_values': [float(v) for v in pmi_values],
                        }
                    )
                    events.append(event)
        except Exception as e:
            print(f"PMI检测异常: {e}")

        return events


# ==================== 6. 情绪事件检测器 ====================

class SentimentEventDetector(EventDetector):
    """情绪事件检测器 - 基于雪球关注度"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'hot_surge_threshold': 20.0,  # 关注度激增阈值 (%)
            'hot_explosion_threshold': 50.0,  # 关注度爆炸阈值 (%)
            'hot_drop_threshold': -20.0,  # 关注度下降阈值 (%)
            'hot_collapse_threshold': -40.0,  # 关注度崩塌阈值 (%)
            'rank_change_threshold': 10,  # 排名变化阈值
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, symbol: str = None, **kwargs) -> List[FinancialEvent]:
        """检测情绪事件

        Args:
            symbol: 股票代码。如果为None，则检测热门榜前100
        """
        events = []

        try:
            # 获取雪球关注度数据
            df = ak.stock_hot_follow_xq(symbol="最热门")
            if df is None or df.empty:
                return events

            # 如果指定了股票代码，只检测该股票
            if symbol:
                # 查找股票代码列
                symbol_col = None
                for col in ['代码', '股票代码', 'symbol']:
                    if col in df.columns:
                        symbol_col = col
                        break

                if symbol_col:
                    df = df[df[symbol_col] == symbol]

                if df.empty:
                    return events

            # 检测各类情绪事件
            events.extend(self._detect_hot_surge(df))
            events.extend(self._detect_hot_drop(df))
            events.extend(self._detect_hot_list_events(df))

        except Exception as e:
            print(f"检测情绪事件失败: {e}")

        return events

    def _detect_hot_surge(self, df: pd.DataFrame) -> List[FinancialEvent]:
        """检测热度激增类事件"""
        events = []

        try:
            # 查找关注度变化列
            hot_change_col = None
            for col in ['关注指数变化', '关注度变化', '涨跌幅', '关注指数涨跌']:
                if col in df.columns:
                    hot_change_col = col
                    break

            if hot_change_col is None:
                return events

            # 查找必要的列
            symbol_col = self._find_column(df, ['代码', '股票代码', 'symbol'])
            name_col = self._find_column(df, ['名称', '股票名称', 'name'])
            rank_col = self._find_column(df, ['排名', 'rank', '序号'])
            hot_score_col = self._find_column(df, ['关注指数', '热度', 'hot_score'])

            for idx, row in df.iterrows():
                try:
                    # 解析关注度变化（可能是字符串如"+32.5%"）
                    hot_change_str = str(row[hot_change_col])
                    hot_change = float(hot_change_str.replace('%', '').replace('+', ''))
                except (ValueError, TypeError):
                    continue

                symbol = str(row[symbol_col]) if symbol_col else "UNKNOWN"
                event_time = datetime.now().strftime('%Y-%m-%d')

                # 判断事件类型
                if hot_change >= self.config['hot_explosion_threshold']:
                    # 关注度爆炸
                    subtype = "hot_explosion"
                    impact_level = ImpactLevel.CRITICAL
                    description = f"关注度爆炸式增长 {hot_change:.1f}%，超过阈值 {self.config['hot_explosion_threshold']}%"
                elif hot_change >= self.config['hot_surge_threshold']:
                    # 关注度激增
                    subtype = "hot_surge"
                    impact_level = ImpactLevel.HIGH
                    description = f"关注度激增 {hot_change:.1f}%，超过阈值 {self.config['hot_surge_threshold']}%"
                else:
                    continue

                trigger = TriggerRule(
                    metric="hot_change_pct",
                    value=round(hot_change, 2),
                    threshold=self.config['hot_surge_threshold'] if hot_change < self.config['hot_explosion_threshold'] else self.config['hot_explosion_threshold'],
                    operator=">"
                )

                raw_data = {}
                if rank_col:
                    raw_data['rank'] = int(row[rank_col])
                if hot_score_col:
                    raw_data['hot_score'] = float(row[hot_score_col])
                if name_col:
                    raw_data['name'] = str(row[name_col])

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, subtype),
                    symbol=symbol,
                    event_type=EventType.SENTIMENT,
                    event_subtype=subtype,
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="positive",
                    impact_level=impact_level,
                    event_description=description,
                    raw_data=raw_data
                )
                events.append(event)

        except Exception as e:
            print(f"热度激增检测异常: {e}")

        return events

    def _detect_hot_drop(self, df: pd.DataFrame) -> List[FinancialEvent]:
        """检测热度骤降类事件"""
        events = []

        try:
            # 查找关注度变化列
            hot_change_col = None
            for col in ['关注指数变化', '关注度变化', '涨跌幅', '关注指数涨跌']:
                if col in df.columns:
                    hot_change_col = col
                    break

            if hot_change_col is None:
                return events

            symbol_col = self._find_column(df, ['代码', '股票代码', 'symbol'])
            name_col = self._find_column(df, ['名称', '股票名称', 'name'])
            rank_col = self._find_column(df, ['排名', 'rank', '序号'])
            hot_score_col = self._find_column(df, ['关注指数', '热度', 'hot_score'])

            for idx, row in df.iterrows():
                try:
                    hot_change_str = str(row[hot_change_col])
                    hot_change = float(hot_change_str.replace('%', '').replace('+', ''))
                except (ValueError, TypeError):
                    continue

                symbol = str(row[symbol_col]) if symbol_col else "UNKNOWN"
                event_time = datetime.now().strftime('%Y-%m-%d')

                # 判断事件类型
                if hot_change <= self.config['hot_collapse_threshold']:
                    # 关注度崩塌
                    subtype = "hot_collapse"
                    impact_level = ImpactLevel.CRITICAL
                    description = f"关注度崩塌式下降 {hot_change:.1f}%，超过阈值 {self.config['hot_collapse_threshold']}%"
                elif hot_change <= self.config['hot_drop_threshold']:
                    # 关注度下降
                    subtype = "hot_drop"
                    impact_level = ImpactLevel.HIGH
                    description = f"关注度下降 {hot_change:.1f}%，超过阈值 {self.config['hot_drop_threshold']}%"
                else:
                    continue

                trigger = TriggerRule(
                    metric="hot_change_pct",
                    value=round(hot_change, 2),
                    threshold=self.config['hot_drop_threshold'] if hot_change > self.config['hot_collapse_threshold'] else self.config['hot_collapse_threshold'],
                    operator="<"
                )

                raw_data = {}
                if rank_col:
                    raw_data['rank'] = int(row[rank_col])
                if hot_score_col:
                    raw_data['hot_score'] = float(row[hot_score_col])
                if name_col:
                    raw_data['name'] = str(row[name_col])

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, subtype),
                    symbol=symbol,
                    event_type=EventType.SENTIMENT,
                    event_subtype=subtype,
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="negative",
                    impact_level=impact_level,
                    event_description=description,
                    raw_data=raw_data
                )
                events.append(event)

        except Exception as e:
            print(f"热度下降检测异常: {e}")

        return events

    def _detect_hot_list_events(self, df: pd.DataFrame) -> List[FinancialEvent]:
        """检测热点榜出现事件"""
        events = []

        try:
            symbol_col = self._find_column(df, ['代码', '股票代码', 'symbol'])
            name_col = self._find_column(df, ['名称', '股票名称', 'name'])
            rank_col = self._find_column(df, ['排名', 'rank', '序号'])
            hot_score_col = self._find_column(df, ['关注指数', '热度', 'hot_score'])

            if not rank_col:
                return events

            for idx, row in df.iterrows():
                try:
                    rank = int(row[rank_col])
                except (ValueError, TypeError):
                    continue

                symbol = str(row[symbol_col]) if symbol_col else "UNKNOWN"
                event_time = datetime.now().strftime('%Y-%m-%d')

                # 判断事件类型
                if rank == 1:
                    # 榜单第一
                    subtype = "top1_event"
                    impact_level = ImpactLevel.CRITICAL
                    description = f"登顶最热门榜第一名"
                elif rank <= 10:
                    # 前10事件
                    subtype = "top10_event"
                    impact_level = ImpactLevel.HIGH
                    description = f"进入最热门榜前10，排名第 {rank} 位"
                elif rank <= 100:
                    # 进入榜单（仅首次记录，实际场景需要与历史对比）
                    subtype = "enter_hot_list"
                    impact_level = ImpactLevel.MEDIUM
                    description = f"进入最热门榜前100，排名第 {rank} 位"
                else:
                    continue

                trigger = TriggerRule(
                    metric="rank",
                    value=rank,
                    threshold=100 if rank <= 100 else 10 if rank <= 10 else 1,
                    operator="<="
                )

                raw_data = {'rank': rank}
                if hot_score_col:
                    raw_data['hot_score'] = float(row[hot_score_col])
                if name_col:
                    raw_data['name'] = str(row[name_col])

                event = FinancialEvent(
                    event_id=FinancialEvent.generate_event_id(symbol, event_time, subtype),
                    symbol=symbol,
                    event_type=EventType.SENTIMENT,
                    event_subtype=subtype,
                    event_time=event_time,
                    trigger_rule=trigger,
                    sentiment="positive",
                    impact_level=impact_level,
                    event_description=description,
                    raw_data=raw_data
                )
                events.append(event)

        except Exception as e:
            print(f"热点榜事件检测异常: {e}")

        return events

    def _find_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """查找数据列（支持多种可能的列名）"""
        for col in candidates:
            if col in df.columns:
                return col
        return None


# ==================== 7. 新闻事件检测器 ====================

class NewsEventDetector(EventDetector):
    """新闻事件检测器 - 基于东方财富新闻"""

    # 关键词分类字典
    NEWS_KEYWORDS = {
        "利好": ["增长", "大涨", "超预期", "扩产", "订单", "合作", "增持", "创新", "突破", "盈利提升",
                "签订大单", "产能扩张", "净利润提升", "订单增加", "并购利好"],
        "利空": ["下滑", "暴跌", "亏损", "裁员", "调查", "处罚", "终止", "失败", "预警", "项目终止"],
        "监管": ["证监会", "问询", "监管", "处罚", "警示", "立案", "监管通报"],
        "重大": ["并购", "重组", "收购", "战略合作", "定增", "重大合同", "发行债券"],
        "突发": ["火灾", "爆炸", "停产", "事故", "中断"]
    }

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'lookback_days': 7,  # 检测最近N天的新闻
            'min_confidence': 0.5,  # 最小置信度
        }
        super().__init__({**default_config, **(config or {})})

    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测新闻事件

        Args:
            symbol: 股票代码
        """
        events = []

        try:
            # 获取东方财富新闻
            df = ak.stock_news_em(symbol=symbol)
            if df is None or df.empty:
                return events

            # 只分析最近的新闻
            if len(df) > 30:
                df = df.head(30)

            # 分析每条新闻
            for idx, row in df.iterrows():
                event = self._analyze_news(symbol, row)
                if event:
                    events.append(event)

        except Exception as e:
            print(f"检测新闻事件失败 {symbol}: {e}")

        return events

    def _analyze_news(self, symbol: str, news_row: pd.Series) -> Optional[FinancialEvent]:
        """分析单条新闻"""
        try:
            # 提取新闻标题和内容
            title = str(news_row.get('标题', ''))
            content = str(news_row.get('内容', ''))

            # 如果没有内容，使用标题
            if not content or content == 'nan':
                content = title

            # 提取发布时间
            event_time = None
            for time_col in ['发布时间', '时间', '日期', '发布日期']:
                if time_col in news_row and pd.notna(news_row[time_col]):
                    event_time = str(news_row[time_col])
                    break

            if not event_time:
                event_time = datetime.now().strftime('%Y-%m-%d')

            # 标准化时间格式
            if len(event_time) > 10:
                event_time = event_time[:10]

            # 分类和情绪判断
            category, sentiment, confidence = self._classify_news(title + " " + content)

            if category == "中性" and confidence < self.config['min_confidence']:
                return None

            # 确定影响等级
            impact_level = self._determine_impact_level(category, confidence)

            # 生成事件描述
            event_description = f"【{category}新闻】{title[:50]}"

            # 构建原始数据
            raw_data = {
                'title': title,
                'content': content[:200] if content else "",  # 限制内容长度
                'news_source': '东方财富',
                'category': category,
                'confidence': confidence,
            }

            # 添加新闻链接（如果有）
            if '链接' in news_row:
                raw_data['url'] = str(news_row['链接'])

            event = FinancialEvent(
                event_id=FinancialEvent.generate_event_id(symbol, event_time, f"news_{category}"),
                symbol=symbol,
                event_type=EventType.NEWS,
                event_subtype=f"news_{category}",
                event_time=event_time,
                sentiment=sentiment,
                impact_level=impact_level,
                event_description=event_description,
                raw_data=raw_data
            )

            return event

        except Exception as e:
            print(f"分析新闻异常: {e}")
            return None

    def _classify_news(self, text: str) -> tuple[str, str, float]:
        """分类新闻并判断情绪

        Returns:
            (category, sentiment, confidence)
            category: 利好/利空/监管/重大/突发/中性
            sentiment: positive/negative/neutral
            confidence: 0.0-1.0
        """
        text = text.lower()

        # 统计各类别关键词出现次数
        category_scores = {category: 0 for category in self.NEWS_KEYWORDS.keys()}

        for category, keywords in self.NEWS_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    category_scores[category] += 1

        # 找出最高分的类别
        max_score = max(category_scores.values())

        if max_score == 0:
            return "中性", "neutral", 0.5

        # 获取最高分类别
        top_category = max(category_scores, key=category_scores.get)

        # 计算置信度（基于关键词匹配数量）
        confidence = min(0.5 + (max_score * 0.15), 1.0)

        # 判断情绪
        if top_category == "利好":
            sentiment = "positive"
        elif top_category == "利空":
            sentiment = "negative"
        elif top_category == "监管" or top_category == "突发":
            sentiment = "negative"
        elif top_category == "重大":
            # 重大新闻需要看利好/利空关键词
            if category_scores["利好"] > category_scores["利空"]:
                sentiment = "positive"
            elif category_scores["利空"] > category_scores["利好"]:
                sentiment = "negative"
            else:
                sentiment = "neutral"
        else:
            sentiment = "neutral"

        return top_category, sentiment, confidence

    def _determine_impact_level(self, category: str, confidence: float) -> ImpactLevel:
        """根据新闻类别和置信度确定影响等级"""
        # 重大、监管、突发新闻影响较大
        if category in ["重大", "监管", "突发"]:
            if confidence >= 0.8:
                return ImpactLevel.CRITICAL
            elif confidence >= 0.6:
                return ImpactLevel.HIGH
            else:
                return ImpactLevel.MEDIUM

        # 利好、利空新闻
        elif category in ["利好", "利空"]:
            if confidence >= 0.8:
                return ImpactLevel.HIGH
            elif confidence >= 0.6:
                return ImpactLevel.MEDIUM
            else:
                return ImpactLevel.LOW

        # 中性新闻
        else:
            return ImpactLevel.LOW


# ==================== 事件管理器 ====================

class EventManager:
    """事件管理器 - 统一管理所有事件检测器"""

    def __init__(self):
        self.detectors = {
            EventType.TRADING: TradingEventDetector(),
            EventType.CAPITAL_FLOW: CapitalFlowEventDetector(),
            EventType.COMPANY: CompanyEventDetector(),
            EventType.INDUSTRY: IndustryEventDetector(),
            EventType.MACRO: MacroEventDetector(),
            EventType.SENTIMENT: SentimentEventDetector(),
            EventType.NEWS: NewsEventDetector(),
        }

    def detect_all_events(self, symbol: str) -> List[FinancialEvent]:
        """检测某只股票的所有事件"""
        all_events = []

        # 检测交易类事件
        all_events.extend(self.detectors[EventType.TRADING].detect(symbol))

        # 检测资金流向类事件
        all_events.extend(self.detectors[EventType.CAPITAL_FLOW].detect(symbol))

        # 检测公司事件
        all_events.extend(self.detectors[EventType.COMPANY].detect(symbol))

        # 检测情绪事件
        all_events.extend(self.detectors[EventType.SENTIMENT].detect(symbol))

        # 检测新闻事件
        all_events.extend(self.detectors[EventType.NEWS].detect(symbol))

        return all_events

    def detect_macro_events(self) -> List[FinancialEvent]:
        """检测宏观事件（不针对特定股票）"""
        return self.detectors[EventType.MACRO].detect()

    def detect_sentiment_events(self, symbol: str = None) -> List[FinancialEvent]:
        """检测情绪事件

        Args:
            symbol: 股票代码。如果为None，则检测整个热门榜
        """
        return self.detectors[EventType.SENTIMENT].detect(symbol)

    def detect_news_events(self, symbol: str) -> List[FinancialEvent]:
        """检测新闻事件"""
        return self.detectors[EventType.NEWS].detect(symbol)

    def detect_by_type(self, event_type: EventType, symbol: str = None, **kwargs) -> List[FinancialEvent]:
        """按类型检测事件"""
        detector = self.detectors.get(event_type)
        if detector:
            if event_type == EventType.MACRO:
                return detector.detect(**kwargs)
            elif event_type == EventType.SENTIMENT:
                # 情绪事件支持不指定股票代码
                return detector.detect(symbol, **kwargs)
            else:
                return detector.detect(symbol, **kwargs)
        return []

    def get_events_summary(self, events: List[FinancialEvent]) -> Dict:
        """获取事件摘要统计"""
        summary = {
            'total': len(events),
            'by_type': {},
            'by_sentiment': {'positive': 0, 'negative': 0, 'neutral': 0},
            'by_impact': {level.value: 0 for level in ImpactLevel},
        }

        for event in events:
            # 按类型统计
            event_type = event.event_type.value
            summary['by_type'][event_type] = summary['by_type'].get(event_type, 0) + 1

            # 按情绪统计
            if event.sentiment:
                summary['by_sentiment'][event.sentiment] += 1

            # 按影响等级统计
            summary['by_impact'][event.impact_level.value] += 1

        return summary


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 创建事件管理器
    manager = EventManager()

    # 示例1：检测单只股票的所有事件
    print("=" * 80)
    print("检测平安银行(000001)的所有事件")
    print("=" * 80)

    symbol = "000001"
    events = manager.detect_all_events(symbol)

    print(f"\n共检测到 {len(events)} 个事件\n")

    for event in events[:5]:  # 只显示前5个
        print(f"事件ID: {event.event_id}")
        print(f"类型: {event.event_type.value} - {event.event_subtype}")
        print(f"时间: {event.event_time}")
        print(f"描述: {event.event_description}")
        print(f"影响等级: {event.impact_level.value}")
        print(f"情绪: {event.sentiment}")
        print("-" * 80)

    # 获取事件摘要
    summary = manager.get_events_summary(events)
    print("\n事件摘要统计:")
    print(f"总事件数: {summary['total']}")
    print(f"按类型: {summary['by_type']}")
    print(f"按情绪: {summary['by_sentiment']}")
    print(f"按影响: {summary['by_impact']}")

    # 示例2：只检测特定类型的事件
    print("\n" + "=" * 80)
    print("只检测交易类事件")
    print("=" * 80)

    trading_events = manager.detect_by_type(EventType.TRADING, symbol)
    print(f"检测到 {len(trading_events)} 个交易类事件")

    # 示例3：检测宏观事件
    print("\n" + "=" * 80)
    print("检测宏观经济事件")
    print("=" * 80)

    macro_events = manager.detect_macro_events()
    print(f"检测到 {len(macro_events)} 个宏观事件")

    for event in macro_events:
        print(f"\n{event.event_description}")
        print(f"影响等级: {event.impact_level.value}")

    # 示例4：检测情绪事件（雪球热门榜）
    print("\n" + "=" * 80)
    print("检测情绪事件 - 雪球热门榜分析")
    print("=" * 80)

    # 检测整个热门榜
    sentiment_events = manager.detect_sentiment_events()
    print(f"检测到 {len(sentiment_events)} 个情绪事件")

    # 显示前5个情绪事件
    for event in sentiment_events[:5]:
        print(f"\n股票: {event.symbol} ({event.raw_data.get('name', '')})")
        print(f"事件: {event.event_subtype}")
        print(f"描述: {event.event_description}")
        print(f"排名: {event.raw_data.get('rank', 'N/A')}")
        print(f"热度: {event.raw_data.get('hot_score', 'N/A')}")

    # 示例5：检测新闻事件
    print("\n" + "=" * 80)
    print("检测新闻事件 - 东方财富新闻分析")
    print("=" * 80)

    news_events = manager.detect_news_events(symbol)
    print(f"检测到 {len(news_events)} 个新闻事件")

    # 显示前3个新闻事件
    for event in news_events[:3]:
        print(f"\n新闻类别: {event.raw_data.get('category', '')}")
        print(f"标题: {event.raw_data.get('title', '')[:60]}")
        print(f"时间: {event.event_time}")
        print(f"情绪: {event.sentiment}")
        print(f"影响等级: {event.impact_level.value}")
        print(f"置信度: {event.raw_data.get('confidence', 0):.2f}")

    # 示例6：只检测特定股票的情绪事件
    print("\n" + "=" * 80)
    print(f"检测{symbol}的情绪事件")
    print("=" * 80)

    symbol_sentiment = manager.detect_sentiment_events(symbol)
    if symbol_sentiment:
        for event in symbol_sentiment:
            print(f"\n{event.event_description}")
    else:
        print(f"{symbol}未出现在雪球热门榜中")

    # 示例7：导出为字典格式
    print("\n" + "=" * 80)
    print("事件数据格式示例（JSON格式）")
    print("=" * 80)

    if events:
        import json
        print(json.dumps(events[0].to_dict(), ensure_ascii=False, indent=2))
