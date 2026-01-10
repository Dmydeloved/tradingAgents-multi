import datetime

import requests

from webServer.tools.mongodb_tools import convert_objectId
from webServer.utils import mongo_db

event_collection = mongo_db['events']
stock_collection = mongo_db['stock_news']
def gpt(rule,event):
    prompt = f'''
你是一名智能投研与风控助手，负责根据【规则 rule】与【事件 event】判断是否需要生成“及时提醒通知”。

【核心任务】
1. 结合 rule 与 event 的信息，**先判断该事件是否满足生成及时提醒的条件**：
   - event.event_type 与 rule.event_type 一致；
   - event.event_subtype 与 rule.event_subtype 一致；
   - event.trigger_rule.value 与 rule.trigger_condition 语义匹配，且数值逻辑成立；
   - event.impact_level 为 high / critical 时优先生成提醒；
2. 若**不满足生成条件**，请直接返回：
   - 「暂无提醒」
3. 若**满足生成条件**，请生成一条“及时提醒通知”，用于实时推送。

---

【提醒文案输出要求】
当生成提醒时，必须满足以下全部要求：

1. **标题**
   - 开头必须有明确标题；
   - 标题基于 event.event_subtype 自动生成，例如：
     - 【宏观事件提醒｜央行政策】
     - 【系统性风险提醒｜央行政策】

2. **事件要素说明（必须完整）**
   - 事件类型：event.event_type  
   - 事件子类型：event.event_subtype  
   - 关联标的：rule.related_stock 或 event.symbol  
   - 触发指标：来自 event.trigger_rule.metric  
   - 指标数值：event.trigger_rule.value  
   - 触发阈值：event.trigger_rule.threshold  
   - 事件时间：event.event_time  

3. **风险等级（必须出现，单独成行）**
   - 文本格式固定为：
     - “风险等级：高”
     - “风险等级：中等”
     - “风险等级：低”
   - 风险等级直接映射自 event.impact_level：
     - critical → 高
     - high → 高
     - medium → 中等
     - low → 低

4. **情绪判断（必须出现）**
   - 基于 event.sentiment（positive / negative / neutral）进行简要判断；
   - 示例：
     - “当前事件整体情绪偏中性”
     - “事件情绪偏负面，需警惕不确定性扩散”

5. **投资建议（必须包含，但严格限制）**
   - ❌ 禁止出现：买入、卖出、加仓、减仓、抄底、逃顶等任何交易指令；
   - ✅ 仅允许风险提示型 / 观察型建议，例如：
     - “建议关注后续政策落地情况及市场反馈”
     - “建议结合自身风险承受能力审慎评估影响”
     - “建议跟踪宏观环境变化对相关资产的潜在传导”
     - “建议警惕短期波动带来的系统性风险”

6. **整体要求**
   - 内容专业、克制、客观；
   - 可直接作为 App / 系统的实时提醒推送；
   - 字数不少于 100 字；
   - 不输出任何 JSON、解释或多余说明，仅输出提醒文本本身。

---

【输入数据】
rule:
{rule}

event:
{event}

---

【请输出】
- 若满足条件：输出一条【包含风险等级与情绪判断的及时提醒文案】
- 若不满足条件：仅输出「暂无提醒」

    '''
    FUND_URL = f"https://api.v3.cm/v1/messages"
    API = 'sk-MQHPgxtvAKdBQxiE90A4C6A68fAc4eBe9d4b899f107fB9Fb'  ##这里就填你申请的API
    headers = {
        "Authorization": f"Bearer {API}",
        "Content-Type": "application/json",
    }
    request_body = {
        "model": "cc-3-5-haiku-20241022",  ##这里换成你要的模型
        "temperature": 0.7,
        "stream": False,
        "messages": [
            {"role": "user", "content": prompt}]  ##这里写对话内容就行
    }
    response = requests.Session().post(FUND_URL, json=request_body, headers=headers)
    res = response.json()
    print(res['content'][0])
    return res['content'][0]['text']

if __name__ == "__main__":
    event = event_collection.find_one({"event_id":"000063_20251201_limit_up"})
    convert_objectId(event)
    print(event)
    result = gpt(event)
    print(result)
    state = {
        "trade_date": event['event_time'],
        "company_of_interest": event['symbol'],
        "report": str(result),
        "label": "事件提醒",
        "user_id": "691ea11916441e5b365f450f",
        "is_read": "NO",
        'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    result = stock_collection.insert_one(state)
