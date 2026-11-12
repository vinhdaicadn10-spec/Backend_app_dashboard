"""Bai 4 - Phan 18C.2: API lenh thu cong (DEMO, luu vao MongoDB).

API POST chi LUU LENH, Gateway Simulator doc qua /api/actuator/desired.
Khong cong khai API nay ra mang; chua co authentication/authorization.
Canh bao khoi, nut vat ly va bao dong Dashboard luon duoc uu tien.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from mongo_db import db, gateways_collection, nodes_collection, smoke_readings_collection

router = APIRouter(prefix="/api/manual-control", tags=["Manual Control Demo"])

control_modes_collection = db["control_modes"]
manual_states_collection = db["manual_control_states"]
manual_events_collection = db["manual_control_events"]
operator_states_collection = db["operator_alarm_states"]

FRESH_SECONDS = 30
SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")


class ManualCommand(BaseModel):
    gateway_id: str = Field(min_length=1)
    device: Literal["siren", "light"]
    enabled: bool


def to_utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def is_fresh(value, now):
    timestamp = to_utc(value)
    return timestamp is not None and 0 <= (now - timestamp).total_seconds() <= FRESH_SECONDS


def saigon_time(value):
    timestamp = to_utc(value)
    return timestamp.astimezone(SAIGON_TZ).isoformat() if timestamp else None


def localhost_only(request: Request):
    # Gioi han lenh POST demo o may localhost; KHONG thay the xac thuc that.
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="API dieu khien DEMO chi dung tren localhost")


def get_mode_record(gateway_id):
    mode = control_modes_collection.find_one({"gateway_id": gateway_id})
    if mode is None or mode.get("mode") != "MANUAL":
        raise HTTPException(status_code=409, detail="Hay chuyen sang MANUAL truoc khi gui lenh")
    return mode


def check_safe_to_request(gateway_id, now):
    # Day la kiem tra phuc vu demo, khong phai mach interlock bao chay that.
    gw = gateways_collection.find_one({"gateway_id": gateway_id})
    if gw is None:
        raise HTTPException(status_code=404, detail="Chua tim thay Gateway")
    if not is_fresh(gw.get("last_seen"), now):
        raise HTTPException(status_code=409, detail="Gateway khong co heartbeat moi")

    smoke = nodes_collection.find_one({"id": "NODE-02", "gateway_id": gateway_id, "type": "SMOKE"})
    button = nodes_collection.find_one({"id": "NODE-01", "gateway_id": gateway_id, "type": "BUTTON"})
    siren_node = nodes_collection.find_one({"id": "NODE-03", "gateway_id": gateway_id, "type": "SIREN"})
    if not smoke or not button or not siren_node:
        raise HTTPException(status_code=409, detail="Thieu thong tin NODE-01/02/03")

    operator = operator_states_collection.find_one({"_id": gateway_id}) or {}
    if (smoke.get("smoke_alert_active") is True
        or button.get("button_alarm_active") is True
        or button.get("button_pressed") is True
        or operator.get("alarm_active") is True):
        raise HTTPException(status_code=409, detail="Dang co canh bao, khong nhan lenh thu cong")

    reading = smoke_readings_collection.find_one(
        {"gateway_id": gateway_id, "node_id": "NODE-02"},
        sort=[("received_at", -1)],
    )
    if not reading:
        raise HTTPException(status_code=409, detail="Chua co bao cao ADC khoi")

    nodes_fresh = all(
        node.get("status") == "online" and is_fresh(node.get("last_reported_at"), now)
        for node in (smoke, button, siren_node)
    )
    if not (nodes_fresh
            and is_fresh(button.get("last_button_report_at"), now)
            and button.get("button_pressed") is False
            and is_fresh(reading.get("received_at"), now)):
        raise HTTPException(status_code=409, detail="Du lieu Node/ADC cu hoac chua xac nhan nha nut")


def current_state(gateway_id, mode_record=None):
    """Lenh tu lan chon MANUAL truoc khong duoc tu tai su dung o lan moi."""
    stored = manual_states_collection.find_one({"_id": gateway_id}) or {}
    session = to_utc(mode_record.get("updated_at")) if mode_record else None
    active = (session is not None and
              to_utc(stored.get("mode_session_at")) == session)
    return {
        "gateway_id": gateway_id,
        "mode": "MANUAL" if mode_record else "AUTO",
        "requested_siren_on": bool(stored.get("siren_requested")) if active else False,
        "requested_light_on": bool(stored.get("light_requested")) if active else False,
        "commands_current_session": active,
        "last_changed_at": saigon_time(stored.get("updated_at")) if active else None,
        "applied_to_simulator": None,
        "note": "API nay chi luu yeu cau; xem /api/actuator/status/NODE-03 de biet trang thai Simulator da bao cao",
    }


@router.get("/status/{gateway_id}")
def get_manual_control_status(gateway_id: str):
    if gateways_collection.find_one({"gateway_id": gateway_id}) is None:
        raise HTTPException(status_code=404, detail="Gateway chua ton tai")
    mode = control_modes_collection.find_one({"gateway_id": gateway_id})
    mode = mode if mode and mode.get("mode") == "MANUAL" else None
    return current_state(gateway_id, mode)


@router.post("/command")
def save_manual_command(data: ManualCommand, request: Request):
    localhost_only(request)
    mode = get_mode_record(data.gateway_id)
    now = datetime.now(timezone.utc)
    check_safe_to_request(data.gateway_id, now)

    session = mode.get("updated_at")
    if to_utc(session) is None:
        raise HTTPException(status_code=409, detail="Che do MANUAL chua co moc thoi gian hop le")

    # Khoi tao lenh moi khi vua chuyen tu AUTO sang MANUAL.
    old = manual_states_collection.find_one({"_id": data.gateway_id})
    if not old or to_utc(old.get("mode_session_at")) != to_utc(session):
        manual_states_collection.update_one(
            {"_id": data.gateway_id},
            {"$set": {
                "gateway_id": data.gateway_id,
                "mode_session_at": session,
                "siren_requested": False,
                "light_requested": False,
                "updated_at": now,
            }},
            upsert=True,
        )

    field = "siren_requested" if data.device == "siren" else "light_requested"
    changed = manual_states_collection.update_one(
        {"_id": data.gateway_id, field: {"$ne": data.enabled}},
        {"$set": {field: data.enabled, "updated_at": now}},
    )
    is_new_command = changed.modified_count == 1
    event_type = f"MANUAL_{data.device.upper()}_{'ON' if data.enabled else 'OFF'}"
    if is_new_command:
        manual_events_collection.insert_one({
            "gateway_id": data.gateway_id,
            "event_type": event_type,
            "device": data.device,
            "enabled": data.enabled,
            "occurred_at": now,
        })

    return {
        **current_state(data.gateway_id, mode),
        "command_saved": True,
        "new_event": event_type if is_new_command else None,
    }


@router.get("/events/{gateway_id}")
def get_manual_control_events(gateway_id: str, limit: int = Query(20, ge=1, le=100)):
    if gateways_collection.find_one({"gateway_id": gateway_id}) is None:
        raise HTTPException(status_code=404, detail="Gateway chua ton tai")
    items = list(manual_events_collection.find(
        {"gateway_id": gateway_id}, {"_id": 0}
    ).sort("occurred_at", -1).limit(limit))
    for item in items:
        item["occurred_at"] = saigon_time(item.get("occurred_at"))
    return {"gateway_id": gateway_id, "events": items}
