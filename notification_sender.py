"""Gửi Expo Push từ Backend; chỉ chấp nhận ticket = đã nhận yêu cầu, KHÔNG cam kết đã tới điện thoại."""
import hashlib
import json
from datetime import datetime, timezone
from urllib import error, request

from mongo_db import db

PUSH_URL = "https://exp.host/--/api/v2/push/send"
devices_collection = db["push_devices"]
delivery_collection = db["push_deliveries"]


def channel_id(sound: bool, vibration: bool) -> str:
    return f"fire-{'sound' if sound else 'silent'}-{'vibrate' if vibration else 'still'}-v1"


def _send_one(token: str, title: str, body: str, sound: bool, vibration: bool):
    payload = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default" if sound else None,
        "channelId": channel_id(sound, vibration),
        "priority": "high",
        "data": {"type": "fire_alarm_demo"},
    }
    req = request.Request(
        PUSH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
    ticket = data.get("data", {})
    if ticket.get("status") != "ok":
        raise RuntimeError(str(ticket.get("message") or ticket.get("details") or data))
    return ticket.get("id")


def send_to_registered(event_key: str, title: str, body: str):
    selected = list(devices_collection.find({"enabled": True}))
    summary = {"enabled_devices": len(selected), "expo_accepted": 0, "failed": 0, "already_processed": 0}
    for device in selected:
        token = device["_id"]
        safe_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
        unique_id = f"{event_key}:{safe_hash}"
        # Claim duy nhất để không gửi lặp khi 2 worker cùng nhìn thấy một event.
        claimed = delivery_collection.update_one(
            {"_id": unique_id},
            {"$setOnInsert": {"created_at": datetime.now(timezone.utc), "status": "PROCESSING", "event_key": event_key}},
            upsert=True,
        )
        if claimed.upserted_id is None:
            summary["already_processed"] += 1
            continue
        try:
            ticket_id = _send_one(token, title, body, bool(device.get("sound", True)), bool(device.get("vibration", True)))
            delivery_collection.update_one({"_id": unique_id}, {"$set": {"status": "EXPO_ACCEPTED", "expo_ticket_id": ticket_id}})
            summary["expo_accepted"] += 1
        except (Exception) as exc:
            # Demo: ghi thất bại để người học xem MongoDB, chưa triển khai retry/receipts.
            delivery_collection.update_one({"_id": unique_id}, {"$set": {"status": "FAILED", "error": str(exc)[:250]}})
            summary["failed"] += 1
    return summary


def send_test_push(run_id: str):
    return send_to_registered(f"test:{run_id}", "THỬ THÔNG BÁO", "Đây là thông báo thử từ FastAPI. NODE-03 không bị kích hoạt.")
