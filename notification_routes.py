"""Bài 14 – Demo: đăng ký Expo Push Token; không cần đăng nhập.

Chỉ dùng trên localhost/LAN tin cậy. Không công khai API ra Internet.
Gửi thử không kích hoạt NODE-03 và không tạo cảnh báo cháy giả trong database.
"""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mongo_db import db
from notification_sender import send_test_push

router = APIRouter(prefix="/api/notifications", tags=["Notifications Demo"])
tokens = db["push_devices"]


class RegisterDevice(BaseModel):
    token: str = Field(min_length=20, max_length=255)
    enabled: bool = True
    sound: bool = True
    vibration: bool = True


@router.post("/register")
def register_device(data: RegisterDevice):
    if not (data.token.startswith("ExpoPushToken[") or data.token.startswith("ExponentPushToken[")):
        raise HTTPException(status_code=422, detail="Token khong phai Expo Push Token")
    tokens.update_one(
        {"_id": data.token},
        {"$set": {
            "enabled": data.enabled,
            "sound": data.sound,
            "vibration": data.vibration,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"saved": True, "enabled": data.enabled, "message": "Da luu cai dat push cho dien thoai"}


@router.get("/status")
def status():
    # Không tiết lộ token của người dùng.
    return {"registered_devices": tokens.count_documents({}), "enabled_devices": tokens.count_documents({"enabled": True})}


@router.post("/test")
def test_push(request: Request):
    # Endpoint phát thử chỉ cho chính máy chạy Backend dùng Swagger.
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail="Test chi duoc thuc hien tu localhost")
    result = send_test_push(str(uuid4()))
    return {"mode": "TEST_ONLY_NO_ALARM", **result}
