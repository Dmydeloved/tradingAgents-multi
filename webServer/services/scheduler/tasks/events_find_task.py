import datetime
from dataclasses import asdict
from pymongo import UpdateOne

from webServer.services.scheduler.tasks.base_task import BaseTask
from webServer.tools.events_tools import EventManager
from webServer.tools.llm_request_tools import gpt
from webServer.utils import mongo_db

event_collection = mongo_db['events']
stock_collection = mongo_db['stock_news']

class EventReminderTask(BaseTask):
    def run(self):
        manager = EventManager()
        stocks = ['000001', '000063', '600519', '601318', '002415']
        events = []

        # 1. 统一收集所有事件
        for stock in stocks:
            stock_events = manager.detect_all_events(stock)

            # 确保 detect_all_events 返回的是 list
            if not stock_events:
                continue

            # 展开加入 events 列表
            events.extend(stock_events)

        # 2. 打印事件
        for event in events:
            print(f"事件ID: {event.event_id}")
            print(f"类型: {event.event_type.value} - {event.event_subtype}")
            print(f"时间: {event.event_time}")
            print(f"描述: {event.event_description}")
            print(f"影响等级: {event.impact_level.value}")
            print(f"情绪: {event.sentiment}")
            print("-" * 80)

        # 3. 存入 MongoDB（注意要转成 dict）
        doc_list = [e.to_dict() for e in events]

        if not doc_list:
            print("没有检测到事件")
            return

        operations = []

        for doc in doc_list:
            operations.append(
                UpdateOne(
                    {
                        "event_id": doc["event_id"],
                        "event_time": doc["event_time"]
                    },
                    {"$setOnInsert": doc},
                    upsert=True
                )
            )

        result = event_collection.bulk_write(operations, ordered=False)

        print(f"成功插入 {result.upserted_count} 条事件（已自动去重）")
        # doc_list = [asdict(e) for e in events]
        #
        # if doc_list:
        #     result = event_collection.insert_many(doc_list)
        #     print(f"成功插入 {len(result.inserted_ids)} 条事件")
        # else:
        #     print("没有检测到事件")

        ## 生成提醒
        # for event in events:
        #     reminder_news = gpt(event)
        #     ## 落库
        #     state = {
        #         "trade_date": event['event_time'],
        #         "company_of_interest": event['symbol'],
        #         "report": str(result),
        #         "label": "事件提醒",
        #         "user_id": "691ea11916441e5b365f450f",
        #         "is_read": "NO",
        #         'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        #     }
        #
        #     result = stock_collection.insert_one(state)




if __name__ == "__main__":
    event_reminder_task = EventReminderTask()
    event_reminder_task.run()
    # event = event_collection.find_one({"event_id":"SZ920436_20251219_085630_rank_rise_abnormal"})
    # print(event)
