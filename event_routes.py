"""Bai 4 - Phan 14: Lich su su kien tong hop (chi doc, demo).

Hop nhat lich su khoi, nut nhan, coi/den, bao dong Dashboard va MANUAL.
Khong them su kien moi, khong phat lenh dieu khien thiet bi.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Query

from mongo_db import db

router = APIRouter(prefix="/api/events", tags=["System Event History Demo"])

SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")

COLLECTIONS = {
    "smoke": db["smoke_alerts"],
    "button": db["button_events"],
    "actuator": db["actuator_events"],
    "operator": db["operator_alarm_events"],
    "manual": db["manual_control_events"],
}

# Tieu de cho 6 loai su kien da duoc tao trong Phan 10-12.
EVENT_LABELS = {
    "ALARM_TRIGGERED": "Bat dau canh bao khoi (demo)",
    "ALARM_CLEARED": "Ket thuc canh bao khoi (demo)",
    "BUTTON_PRESSED": "Nhan nut khan cap (demo)",
    "BUTTON_RESET": "Reset canh bao nut nhan (demo)",
    "ACTUATOR_ON": "Bat coi/den (demo)",
    "ACTUATOR_OFF": "Tat coi/den (demo)",
    "OPERATOR_ALARM_TRIGGERED": "Bao dong thu cong tu Dashboard (demo)",
    "OPERATOR_ALARM_RESET": "Reset bao dong tu Dashboard (demo)",
    "MANUAL_SIREN_ON": "Bat coi thu cong (demo)",
    "MANUAL_SIREN_OFF": "Tat coi thu cong (demo)",
    "MANUAL_LIGHT_ON": "Bat den thu cong (demo)",
    "MANUAL_LIGHT_OFF": "Tat den thu cong (demo)",
}

SOURCE_LABELS = {
    "smoke": "Cam bien khoi",
    "button": "Nut nhan khan cap",
    "actuator": "Coi va den canh bao",
    "operator": "Dieu khien tu Dashboard",
    "manual": "Thao tac MANUAL",
}


def to_utc(value):
    """MongoDB co the tra datetime khong timezone; mac dinh la UTC."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_event(document, source):
    """Chuyen ba kieu su kien ve chung mot cau truc JSON."""
    occurred = to_utc(document.get("occurred_at"))
    if occurred is None:
        return None

    event_type = document.get("event_type", "UNKNOWN")

    return {
        "gateway_id": document.get("gateway_id"),
        "node_id": document.get("node_id"),
        "source": source,
        "source_label": SOURCE_LABELS[source],
        "event_type": event_type,
        "description": EVENT_LABELS.get(event_type, str(event_type)),
        "adc_value": document.get("adc_value") if source == "smoke" else None,
        "siren_on": document.get("siren_on") if source == "actuator" else None,
        "light_on": document.get("light_on") if source == "actuator" else None,
        "device": document.get("device") if source == "manual" else None,
        "enabled": document.get("enabled") if source == "manual" else None,
        "occurred_at": occurred.astimezone(SAIGON_TZ).isoformat(),
        "_sort_ts": occurred.timestamp(),
    }


@router.get("/history/{gateway_id}")
def get_system_event_history(
    gateway_id: str,
    source: Literal["all", "smoke", "button", "actuator", "operator", "manual"] = "all",
    limit: int = Query(default=30, ge=1, le=100),
):
    """Tra toi da `limit` su kien MOI NHAT cua Gateway, tu 1 hoac 3 collection.

    Chi lay toi da `limit` ban ghi / collection: du de tim top `limit`
    tong hop, khong can tai toan bo lich su MongoDB vao RAM.
    """
    selected = COLLECTIONS if source == "all" else {source: COLLECTIONS[source]}
    combined = []

    for source_name, collection in selected.items():
        records = (
            collection.find({"gateway_id": gateway_id}, {"_id": 0})
            .sort("occurred_at", -1)
            .limit(limit)
        )
        for record in records:
            event = normalize_event(record, source_name)
            if event is not None:
                combined.append(event)

    # Su kien tu nhieu collection phai duoc sap xep chung theo thoi gian.
    combined.sort(key=lambda item: item["_sort_ts"], reverse=True)
    events = combined[:limit]
    for event in events:
        event.pop("_sort_ts")

    return {
        "gateway_id": gateway_id,
        "source_filter": source,
        "total_returned": len(events),
        "events": events,
        "note": "Lich su demo doc tu MongoDB, khong phai danh sach su kien canh bao thuc te da duoc xac minh",
    }
