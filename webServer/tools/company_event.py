from datetime import datetime, timedelta
import akshare as ak
from typing import Optional, List, Dict
import pandas as pd
import abc
import numpy as np

from webServer.tools.event import FinancialEvent, TriggerRule, EventType, ImpactLevel


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


# ==================== 公司事件指标计算器（历史基准） ====================
class CompanyIndicatorCalculator:
    """公司事件指标计算器 - 基于历史数据计算基准阈值"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'profit_change_percentile': 90,  # 净利润变化分位数阈值
            'profit_change_lookback': 24,     # 业绩预告回溯月数
            'unlock_ratio_percentile': 90,    # 解禁比例分位数阈值
            'unlock_ratio_lookback': 36,      # 解禁数据回溯月数
            'default_profit_threshold': 20.0, # 默认净利润变化阈值
            'default_unlock_threshold': 5.0,  # 默认解禁比例阈值
        }
        self.config = {**default_config, **(config or {})}

    def _get_current_time_second(self) -> str:
        """获取当前年月日 + 固定时分秒（8:56:30），格式：YYYY-MM-DD HH:MM:SS"""
        # 1. 获取当前时间对象
        current_datetime = datetime.now()
        # 2. 替换时分秒为固定值：时=8，分=56，秒=30
        fixed_time = current_datetime.replace(hour=8, minute=56, second=30, microsecond=0)
        # 3. 格式化为指定字符串
        return fixed_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_company_indicators(self, symbol: str) -> Optional[Dict]:
        """获取公司事件的历史基准指标"""
        indicators = {
            "profit_change_threshold": self._calc_profit_change_threshold(symbol),
            "unlock_ratio_threshold": self._calc_unlock_ratio_threshold(symbol),
            "calc_time": self._get_current_time_second()
        }
        return indicators

    def _calc_profit_change_threshold(self, symbol: str) -> float:
        """计算业绩预告净利润变化的分位数阈值（历史基准）"""
        try:
            # 获取历史业绩预告数据
            df = ak.stock_yjyg_em()
            if df is None or df.empty:
                return self.config['default_profit_threshold']

            # 过滤目标股票
            if '股票代码' in df.columns:
                df = df[df['股票代码'] == symbol]
            elif '代码' in df.columns:
                df = df[df['代码'] == symbol]
            else:
                return self.config['default_profit_threshold']

            if df.empty:
                return self.config['default_profit_threshold']

            # 提取净利润变化幅度
            profit_changes = []
            for idx, row in df.iterrows():
                forecast_content = str(row.get('预测内容', '')).lower()
                # 提取百分比数值（简单正则匹配）
                import re
                change_matches = re.findall(r'([+-]?\d+\.?\d*)%', forecast_content)
                if change_matches:
                    try:
                        change = float(change_matches[0])
                        profit_changes.append(abs(change))
                    except ValueError:
                        continue

            if not profit_changes:
                return self.config['default_profit_threshold']

            # 计算分位数阈值
            percentile = self.config['profit_change_percentile'] / 100
            threshold = np.percentile(profit_changes, percentile)
            return float(max(threshold, self.config['default_profit_threshold']))

        except Exception as e:
            print(f"计算业绩变化阈值失败 {symbol}: {e}")
            return self.config['default_profit_threshold']

    def _calc_unlock_ratio_threshold(self, symbol: str) -> float:
        """计算限售解禁比例的分位数阈值（历史基准）"""
        try:
            # 获取历史限售解禁数据
            df = ak.stock_restricted_release_queue_em(symbol=symbol)
            if df is None or df.empty:
                return self.config['default_unlock_threshold']

            # 提取解禁比例
            unlock_ratios = []
            for idx, row in df.iterrows():
                for col in ['解禁占总股本比例', '占总股本比例', '解禁市值占总市值比例']:
                    if col in row and pd.notna(row[col]):
                        try:
                            ratio = float(str(row[col]).replace('%', ''))
                            unlock_ratios.append(ratio)
                            break
                        except (ValueError, TypeError):
                            continue

            if not unlock_ratios:
                return self.config['default_unlock_threshold']

            # 计算分位数阈值
            percentile = self.config['unlock_ratio_percentile'] / 100
            threshold = np.percentile(unlock_ratios, percentile)
            return float(max(threshold, self.config['default_unlock_threshold']))

        except Exception as e:
            print(f"计算解禁比例阈值失败 {symbol}: {e}")
            return self.config['default_unlock_threshold']


# ==================== 公司事件检测器（实时对比） ====================
class CompanyEventDetector(EventDetector):
    """公司事件检测器（历史指标+实时数据对比）"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'profit_change_percentile': 90,  # 净利润变化分位数阈值
            'profit_change_lookback': 24,     # 业绩预告回溯月数
            'unlock_ratio_percentile': 90,    # 解禁比例分位数阈值
            'unlock_ratio_lookback': 36,      # 解禁数据回溯月数
        }
        super().__init__({**default_config, **(config or {})})
        # 初始化公司事件指标计算器
        self.indicator_calculator = CompanyIndicatorCalculator(self.config)

    def detect(self, symbol: str, **kwargs) -> List[FinancialEvent]:
        """检测所有公司事件（核心入口）"""
        events = []

        # 获取历史基准指标
        company_indicators = self.indicator_calculator.get_company_indicators(symbol)
        if not company_indicators:
            print(f"无法获取{symbol}公司事件基准指标，跳过检测")
            return events

        try:
            # 检测业绩预告事件（实时 vs 历史分位数阈值）
            events.extend(self._detect_performance_forecast(symbol, company_indicators))
        except Exception as e:
            print(f"检测业绩预告失败 {symbol}: {e}")

        try:
            # 检测限售解禁事件（实时 vs 历史分位数阈值）
            events.extend(self._detect_unlock_shares(symbol, company_indicators))
        except Exception as e:
            print(f"检测限售解禁失败 {symbol}: {e}")

        return events

    def _detect_performance_forecast(self, symbol: str, indicators: Dict) -> List[FinancialEvent]:
        """检测业绩预告事件：实时净利润变化 >= 历史分位数阈值"""
        events = []
        profit_threshold = indicators['profit_change_threshold']

        try:
            # 获取实时业绩预告数据
            df = ak.stock_yjyg_em()
            if df is None or df.empty:
                return events

            # 过滤目标股票
            if '股票代码' in df.columns:
                df = df[df['股票代码'] == symbol]
            elif '代码' in df.columns:
                df = df[df['代码'] == symbol]
            else:
                return events

            if df.empty:
                return events

            # 解析最新业绩预告
            import re
            for idx, row in df.tail(5).iterrows():
                forecast_type = row.get('预测类型', '').strip()
                forecast_content = str(row.get('预测内容', '')).lower()
                event_time = str(row.get('公告日期', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

                # 提取净利润变化幅度
                change_matches = re.findall(r'([+-]?\d+\.?\d*)%', forecast_content)
                if not change_matches:
                    continue
                profit_change = float(change_matches[0])
                abs_change = abs(profit_change)

                # 实时变化幅度超过历史阈值触发事件
                if abs_change >= profit_threshold:
                    # 映射预告类型和情绪
                    type_mapping = {
                        '预增': ('positive', '业绩预增'),
                        '预减': ('negative', '业绩预减'),
                        '扭亏': ('positive', '扭亏为盈'),
                        '续亏': ('negative', '继续亏损'),
                        '略增': ('positive', '业绩略增'),
                        '略减': ('negative', '业绩略减'),
                        '不确定': ('neutral', '业绩不确定'),
                    }
                    sentiment, desc = type_mapping.get(forecast_type, ('neutral', '业绩预告'))

                    # 构建触发规则
                    trigger_rule = TriggerRule(
                        metric="profit_change_percent",
                        value=round(profit_change, 2),
                        threshold=round(profit_threshold, 2),
                        operator=">" if profit_change > 0 else "<"
                    )

                    # 生成事件
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(symbol, event_time, "performance_forecast"),
                        symbol=symbol,
                        event_type=EventType.COMPANY,
                        event_subtype="performance_forecast",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment=sentiment,
                        impact_level=self._calculate_impact_level(abs_change),
                        event_description=f"{desc}：净利润变动{profit_change:.2f}%（超历史90%分位数阈值{profit_threshold:.2f}%），{forecast_content[:50]}",
                        raw_data={
                            'forecast_type': forecast_type,
                            'profit_change': profit_change,
                            'historical_threshold': profit_threshold,
                            'forecast_content': forecast_content,
                            'report_period': str(row.get('报告期', '')),
                        }
                    )
                    events.append(event)

        except Exception as e:
            print(f"业绩预告实时检测失败 {symbol}: {e}")

        return events

    def _detect_unlock_shares(self, symbol: str, indicators: Dict) -> List[FinancialEvent]:
        """检测限售解禁事件：实时解禁比例 >= 历史分位数阈值"""
        events = []
        unlock_threshold = indicators['unlock_ratio_threshold']

        try:
            # 获取实时限售解禁数据
            df = ak.stock_restricted_release_queue_em(symbol=symbol)
            if df is None or df.empty:
                return events

            # 检测最新解禁数据
            for idx, row in df.tail(5).iterrows():
                # 提取解禁比例
                unlock_ratio = None
                for col in ['解禁占总股本比例', '占总股本比例', '解禁市值占总市值比例']:
                    if col in row and pd.notna(row[col]):
                        try:
                            unlock_ratio = float(str(row[col]).replace('%', ''))
                            break
                        except (ValueError, TypeError):
                            continue

                if unlock_ratio is None:
                    continue

                # 实时解禁比例超过历史阈值触发事件
                if unlock_ratio >= unlock_threshold:
                    # 确定事件时间
                    event_time = None
                    for date_col in ['解禁日期', '日期', '上市日期']:
                        if date_col in row and pd.notna(row[date_col]):
                            event_time = str(row[date_col])
                            break
                    if not event_time:
                        event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 提取解禁数量
                    unlock_shares = 0
                    for shares_col in ['解禁数量', '解禁股数', '实际解禁数量']:
                        if shares_col in row and pd.notna(row[shares_col]):
                            try:
                                unlock_shares = float(row[shares_col])
                                break
                            except (ValueError, TypeError):
                                continue

                    # 构建触发规则
                    trigger_rule = TriggerRule(
                        metric="unlock_ratio_percent",
                        value=round(unlock_ratio, 2),
                        threshold=round(unlock_threshold, 2),
                        operator=">="
                    )

                    # 生成事件
                    event = FinancialEvent(
                        event_id=FinancialEvent.generate_event_id(symbol, event_time, "share_unlock"),
                        symbol=symbol,
                        event_type=EventType.COMPANY,
                        event_subtype="share_unlock",
                        event_time=event_time,
                        trigger_rule=trigger_rule,
                        sentiment="negative",
                        impact_level=self._calculate_impact_level(unlock_ratio),
                        event_description=f"限售股解禁：占总股本{unlock_ratio:.2f}%（超历史90%分位数阈值{unlock_threshold:.2f}%），解禁数量{unlock_shares:.2f}股",
                        raw_data={
                            'unlock_ratio': unlock_ratio,
                            'historical_threshold': unlock_threshold,
                            'unlock_shares': unlock_shares,
                            'unlock_date': event_time,
                            'unlock_type': str(row.get('解禁类型', '')),
                        }
                    )
                    events.append(event)

        except Exception as e:
            print(f"限售解禁实时检测失败 {symbol}: {e}")

        return events


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 初始化公司事件检测器
    detector = CompanyEventDetector()

    # 检测单只股票（例如：贵州茅台 600519）
    symbol = "000001"
    events = detector.detect(symbol)

    # 输出检测结果
    print(f"\n=== {symbol} 公司事件检测结果 ===")
    print(f"共检测到 {len(events)} 个事件")
    for idx, event in enumerate(events, 1):
        print(f"\n【事件{idx}】")
        print(f"事件类型：{event.event_subtype}")
        print(f"影响等级：{event.impact_level.value}")
        print(f"情绪倾向：{event.sentiment}")
        print(f"描述：{event.event_description}")
        print(f"触发规则：{event.trigger_rule.to_dict() if event.trigger_rule else '无'}")