"""Bai 4 - Phan 18A: bao dong tu Dashboard (DEMO, chi may cuc bo).

Chi ghi nhan trang thai canh bao cho bo mo phong Gateway; KHONG dieu khien
bat ky coi/den that nao. Khong trien khai ra Internet khi chua co xac thuc.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mongo_db import (
    db,
    gateways_collection,
    nodes_collection,
    smoke_readings_collection,
)

router = APIRouter(prefix="/api/operator-alarm", tags=["Operator Alarm Demo"])
state_collection = db["operator_alarm_states"]
events_collection = db["operator_alarm_events"]

SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")
FRESH_SECONDS = 30


class OperatorAlarmAction(BaseModel):
    gateway_id: str = Field(min_length=1)


def _local_only(request: Request):
    """Tranh cho API demo khong xac thuc bi goi tu may khac."""
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="API demo chi cho localhost")


def _utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _recent(value, now):
    moment = _utc(value)
    return moment is not None and 0 <= (now - moment).total_seconds() <= FRESH_SECONDS


def _saigon(value):
    moment = _utc(value)
    return moment.astimezone(SAIGON_TZ).isoformat() if moment else None


def _get_gateway(gateway_id):
    gateway = gateways_collection.find_one({"gateway_id": gateway_id}, {"_id": 0})
    if gateway is None:
        raise HTTPException(status_code=404, detail="Chua tim thay Gateway")
    return gateway


def _get_state(gateway_id):
    return state_collection.find_one({"_id": gateway_id})


@router.get("/status/{gateway_id}")
def get_operator_alarm_status(gateway_id: str):
    _get_gateway(gateway_id)
    record = _get_state(gateway_id)
    return {
        "gateway_id": gateway_id,
        "alarm_active": bool(record and record.get("alarm_active") is True),
        "last_changed_at": _saigon(record.get("changed_at")) if record else None,
        "source": "DASHBOARD_DEMO",
    }


@router.post("/activate")
def activate_operator_alarm(data: OperatorAlarmAction, request: Request):
    """Chot canh bao tu thao tac Dashboard; nhan lap lai khong them event."""
    _local_only(request)
    _get_gateway(data.gateway_id)
    now = datetime.now(timezone.utc)

    # Dung _id = gateway_id: moi Gateway chi co mot trang thai operator.
    state_collection.update_one(
        {"_id": data.gateway_id},
        {"$setOnInsert": {
            "gateway_id": data.gateway_id,
            "alarm_active": False,
        }},
        upsert=True,
    )
    changed = state_collection.update_one(
        {"_id": data.gateway_id, "alarm_active": {"$ne": True}},
        {"$set": {"alarm_active": True, "changed_at": now}},
    )
    newly_activated = changed.modified_count == 1
    if newly_activated:
        events_collection.insert_one({
            "gateway_id": data.gateway_id,
            "source": "DASHBOARD_DEMO",
            "event_type": "OPERATOR_ALARM_TRIGGERED",
            "occurred_at": now,
        })
    return {
        "gateway_id": data.gateway_id,
        "alarm_active": True,
        "new_event": "OPERATOR_ALARM_TRIGGERED" if newly_activated else None,
        "message": "Da ghi nhan bao dong demo; cho Gateway Simulator hoi lenh",
        "changed_at": _saigon(now),
    }


@router.post("/reset")
def reset_operator_alarm(data: OperatorAlarmAction, request: Request):
    """Chi reset nguon DASHBOARD khi du bao cao moi va nguon khac an toan."""
    _local_only(request)
    gateway = _get_gateway(data.gateway_id)
    now = datetime.now(timezone.utc)

    if not _recent(gateway.get("last_seen"), now):
        raise HTTPException(status_code=409, detail="Gateway mat cap nhat, khong reset")

    smoke = nodes_collection.find_one({
        "id": "NODE-02", "type": "SMOKE", "gateway_id": data.gateway_id,
    })
    button = nodes_collection.find_one({
        "id": "NODE-01", "type": "BUTTON", "gateway_id": data.gateway_id,
    })
    reading = smoke_readings_collection.find_one(
        {"gateway_id": data.gateway_id, "node_id": "NODE-02"},
        sort=[("received_at", -1)],
    )
    if not smoke or not button or not reading:
        raise HTTPException(status_code=409, detail="Thieu du lieu cam bien/nut nhan")

    if smoke.get("smoke_alert_active") is True or button.get("button_alarm_active") is True:
        raise HTTPException(status_code=409, detail="Van con canh bao khoi hoac nut vat ly")
    if button.get("button_pressed") is not False:
        raise HTTPException(status_code=409, detail="Nut vat ly chua bao da nha")
    if not all([
        smoke.get("status") == "online",
        button.get("status") == "online",
        _recent(smoke.get("last_reported_at"), now),
        _recent(button.get("last_reported_at"), now),
        _recent(button.get("last_button_report_at"), now),
        _recent(reading.get("received_at"), now),
    ]):
        raise HTTPException(status_code=409, detail="Du lieu node/ADC khong moi, khong reset")

    changed = state_collection.update_one(
        {"_id": data.gateway_id, "alarm_active": True},
        {"$set": {"alarm_active": False, "changed_at": now}},
    )
    did_reset = changed.modified_count == 1
    if did_reset:
        events_collection.insert_one({
            "gateway_id": data.gateway_id,
            "source": "DASHBOARD_DEMO",
            "event_type": "OPERATOR_ALARM_RESET",
            "occurred_at": now,
        })
    return {
        "gateway_id": data.gateway_id,
        "alarm_active": False,
        "reset_performed": did_reset,
        "message": "Da reset canh bao Dashboard demo" if did_reset else "Khong co canh bao Dashboard dang giu",
        "changed_at": _saigon(now),
    }
