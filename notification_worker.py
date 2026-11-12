"""Bài 14 – Worker demo phát push từ sự kiện MỚI trong MongoDB.

Chạy riêng: python notification_worker.py. Chỉ chạy MỘT worker.
KHÔNG quét sự kiện lịch sử trước lúc worker khởi động.
KHÔNG gửi lại 10 giây/lần khi trạng thái khói vẫn cảnh báo.
"""
import time
from datetime import datetime, timezone

from mongo_db import db
from notification_sender import send_to_registered

seen_collection = db["push_events_seen"]

# Chỉ các sự kiện phát sinh MỚI; không gửi sự kiện kết thúc/Reset như báo cháy mới.
WATCH = {
    "smoke_alerts": ("ALARM_TRIGGERED",),
    "button_events": ("BUTTON_PRESSED",),
    "operator_alarm_events": ("OPERATOR_ALARM_TRIGGERED",),
}


def notification_text(collection_name, document):
    if collection_name == "smoke_alerts":
        adc = document.get("adc_value")
        return ("CẢNH BÁO KHÓI – NODE-02", f"NODE-02 phát hiện khói vượt ngưỡng. ADC: {adc if adc is not None else 'chưa rõ'}")
    if collection_name == "button_events":
        return ("NÚT KHẨN CẤP – NODE-01", "Nút nhấn khẩn cấp đã được kích hoạt.")
    return ("BÁO ĐỘNG KHẨN CẤP", "Người vận hành kích hoạt báo động từ Dashboard hoặc App.")


def main():
    started_at = datetime.now(timezone.utc)
    print("Notification worker DEMO: dang theo doi su kien moi tu", started_at.isoformat(), flush=True)
    print("Chi chay 1 worker. Su kien truoc luc khoi dong KHONG duoc gui lai.", flush=True)
    while True:
        try:
            for collection_name, types in WATCH.items():
                cursor = db[collection_name].find({
                    "occurred_at": {"$gte": started_at},
                    "event_type": {"$in": list(types)},
                }).sort("occurred_at", 1).limit(100)
                for event in cursor:
                    title, body = notification_text(collection_name, event)
                    unique_key = f"{collection_name}:{event['_id']}"
                    claim = seen_collection.update_one(
                        {"_id": unique_key},
                        {"$setOnInsert": {"seen_at": datetime.now(timezone.utc)}},
                        upsert=True,
                    )
                    # Sự kiện đã quan sát không gửi lại nếu vừa đăng ký thêm điện thoại.
                    if claim.upserted_id is None:
                        continue
                    result = send_to_registered(unique_key, title, body)
                    if result["expo_accepted"] or result["failed"]:
                        print(event.get("event_type"), result, flush=True)
        except Exception as exc:
            print("Worker error:", exc, flush=True)
        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Worker stopped.")
