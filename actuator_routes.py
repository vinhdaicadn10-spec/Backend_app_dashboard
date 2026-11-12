"""Bai 4 - Phan 18C.2: Xu ly canh bao + lenh MANUAL cho NODE-03 DEMO.

Ke thua Phan 18A; them yeu cau coi/den rieng tu Phan 18C.1.
Giu nguyen smoke_routes.py Phan 10.
Day KHONG phai giai phap dieu khien thiet bi bao chay that.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mongo_db import (
    db,
    gateways_collection,
    nodes_collection,
    smoke_readings_collection,
)

router = APIRouter(prefix="/api/actuator", tags=["Actuator Demo"])
actuator_events_collection = db["actuator_events"]
operator_alarm_states_collection = db["operator_alarm_states"]
control_modes_collection = db["control_modes"]
manual_states_collection = db["manual_control_states"]

SMOKE_NODE_ID = "NODE-02"
BUTTON_NODE_ID = "NODE-01"
ACTUATOR_NODE_ID = "NODE-03"
FRESH_SECONDS = 30


class ActuatorReport(BaseModel):
    gateway_id: str = Field(min_length=1)
    node_id: Literal["NODE-03"]
    siren_on: bool
    light_on: bool


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fresh(value, now):
    timestamp = _as_utc(value)
    if timestamp is None:
        return False
    delta = (now - timestamp).total_seconds()
    return 0 <= delta <= FRESH_SECONDS


def _get_actuator(node_id, gateway_id=None):
    query = {"id": node_id, "type": "SIREN"}
    if gateway_id is not None:
        query["gateway_id"] = gateway_id
    node = nodes_collection.find_one(query, {"_id": 0})
    if node is None:
        raise HTTPException(
            status_code=404,
            detail="Khong tim thay Node coi/den thuoc Gateway nay",
        )
    return node


def choose_actuator_command(*, smoke_alarm, button_alarm, operator_alarm,
                            data_ready, mode, manual_session_active,
                            siren_requested, light_requested):
    """Quyet dinh lenh. Thuan tuy logic de de kiem thu.

    - ALARM: bat ca hai bat ke AUTO/MANUAL.
    - HOLD: chua du du lieu de chu dong ra lenh TAT.
    - MANUAL: moi kenh duoc quyet dinh rieng khi du lieu moi.
    - AUTO: khong canh bao thi tat ca hai.
    """
    if smoke_alarm or button_alarm or operator_alarm:
        return {"decision": "ON", "siren_on": True, "light_on": True,
                "source": "ALARM"}
    if not data_ready:
        return {"decision": "HOLD", "siren_on": None, "light_on": None,
                "source": "STALE_DATA"}
    if mode == "MANUAL":
        return {
            "decision": "MANUAL",
            "siren_on": (siren_requested is True) if manual_session_active else False,
            "light_on": (light_requested is True) if manual_session_active else False,
            "source": "MANUAL_CONTROL",
        }
    return {"decision": "OFF", "siren_on": False, "light_on": False,
            "source": "AUTO"}


@router.get("/desired/{gateway_id}")
def get_desired_actuator_state(gateway_id: str):
    """Gateway Simulator lay lenh; demo, KHONG phai interlock bao chay that.

    Chi mot API nay quyet dinh ON/OFF/HOLD/MANUAL de tranh 2 noi tranh lenh.
    """
    gateway = gateways_collection.find_one({"gateway_id": gateway_id})
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway chua dang ky/heartbeat")

    actuator = _get_actuator(ACTUATOR_NODE_ID, gateway_id)
    smoke_node = nodes_collection.find_one(
        {"id": SMOKE_NODE_ID, "type": "SMOKE", "gateway_id": gateway_id}
    )
    if smoke_node is None:
        raise HTTPException(status_code=404, detail="Khong tim thay NODE-02")
    button_node = nodes_collection.find_one(
        {"id": BUTTON_NODE_ID, "type": "BUTTON", "gateway_id": gateway_id}
    )
    if button_node is None:
        raise HTTPException(status_code=404, detail="Khong tim thay NODE-01")

    now = datetime.now(timezone.utc)
    latest = smoke_readings_collection.find_one(
        {"node_id": SMOKE_NODE_ID, "gateway_id": gateway_id},
        sort=[("received_at", -1)],
    )

    # Khong tu xoa canh bao da chot khi du lieu tro nen cu.
    smoke_alarm = smoke_node.get("smoke_alert_active") is True
    button_alarm = (button_node.get("button_alarm_active") is True
                    or button_node.get("button_pressed") is True)
    operator_record = operator_alarm_states_collection.find_one({"_id": gateway_id}) or {}
    operator_alarm = operator_record.get("alarm_active") is True

    gateway_fresh = _fresh(gateway.get("last_seen"), now)
    smoke_fresh = (
        smoke_node.get("status") == "online"
        and _fresh(smoke_node.get("last_reported_at"), now)
        and _fresh(latest.get("received_at") if latest else None, now)
    )
    button_fresh = (
        button_node.get("status") == "online"
        and button_node.get("button_pressed") is False
        and _fresh(button_node.get("last_reported_at"), now)
        and _fresh(button_node.get("last_button_report_at"), now)
    )
    actuator_fresh = (
        actuator.get("status") == "online"
        and _fresh(actuator.get("last_reported_at"), now)
    )
    data_ready = gateway_fresh and smoke_fresh and button_fresh and actuator_fresh

    mode_record = control_modes_collection.find_one({"gateway_id": gateway_id}) or {}
    mode = "MANUAL" if mode_record.get("mode") == "MANUAL" else "AUTO"
    manual_record = manual_states_collection.find_one({"_id": gateway_id}) or {}
    # Lenh cua phien MANUAL cu khong duoc tai su dung sau AUTO -> MANUAL.
    session_at = _as_utc(mode_record.get("updated_at"))
    manual_session_at = _as_utc(manual_record.get("mode_session_at"))
    manual_session_active = (
        mode == "MANUAL" and session_at is not None
        and session_at == manual_session_at
    )

    result = choose_actuator_command(
        smoke_alarm=smoke_alarm,
        button_alarm=button_alarm,
        operator_alarm=operator_alarm,
        data_ready=data_ready,
        mode=mode,
        manual_session_active=manual_session_active,
        siren_requested=manual_record.get("siren_requested"),
        light_requested=manual_record.get("light_requested"),
    )
    return {
        "gateway_id": gateway_id,
        "node_id": ACTUATOR_NODE_ID,
        **result,
        "mode": mode,
        "alarm_active": smoke_alarm or button_alarm or operator_alarm,
        "smoke_alarm_active": smoke_alarm,
        "button_alarm_active": button_alarm,
        "operator_alarm_active": operator_alarm,
        "gateway_data_fresh": gateway_fresh,
        "smoke_data_fresh": smoke_fresh,
        "button_data_fresh": button_fresh,
        "actuator_node_fresh": actuator_fresh,
        "manual_command_session_active": manual_session_active,
        "checked_at": now.isoformat(),
    }


@router.post("/report")
def report_actuator_state(data: ActuatorReport):
    """Gateway gia lap xac nhan trang thai coi/den da mo phong."""
    _get_actuator(data.node_id, data.gateway_id)
    now = datetime.now(timezone.utc)

    values = {
        "siren_on": data.siren_on,
        "light_on": data.light_on,
        "last_actuator_report_at": now,
    }

    # Chi ghi event khi ON/OFF thuc su thay doi; bao cao lap lai chi cap nhat timestamp.
    changed = nodes_collection.update_one(
        {
            "id": data.node_id,
            "type": "SIREN",
            "gateway_id": data.gateway_id,
            "$or": [
                {"siren_on": {"$ne": data.siren_on}},
                {"light_on": {"$ne": data.light_on}},
            ],
        },
        {"$set": values},
    )

    if changed.modified_count == 1:
        event_type = (
            "ACTUATOR_ON" if data.siren_on or data.light_on else "ACTUATOR_OFF"
        )
        actuator_events_collection.insert_one(
            {
                "gateway_id": data.gateway_id,
                "node_id": data.node_id,
                "event_type": event_type,
                "siren_on": data.siren_on,
                "light_on": data.light_on,
                "occurred_at": now,
            }
        )
    else:
        nodes_collection.update_one(
            {"id": data.node_id, "type": "SIREN", "gateway_id": data.gateway_id},
            {"$set": {"last_actuator_report_at": now}},
        )
        event_type = None

    return {
        "message": "Da nhan trang thai coi/den MO PHONG",
        "node_id": data.node_id,
        "siren_on": data.siren_on,
        "light_on": data.light_on,
        "new_event": event_type,
        "reported_at": now.isoformat(),
    }


@router.get("/status/{node_id}")
def get_actuator_status(node_id: str):
    node = _get_actuator(node_id)
    now = datetime.now(timezone.utc)
    report_fresh = _fresh(node.get("last_actuator_report_at"), now)
    node_connected = (
        node.get("status") == "online"
        and _fresh(node.get("last_reported_at"), now)
    )
    return {
        "node_id": node_id,
        "gateway_id": node.get("gateway_id"),
        # Gia tri lan cuoi, KHONG khang dinh trang thai khi mat ket noi
        "siren_on": node.get("siren_on"),
        "light_on": node.get("light_on"),
        "last_reported_at": (
            _as_utc(node.get("last_actuator_report_at")).isoformat()
            if _as_utc(node.get("last_actuator_report_at")) else None
        ),
        "report_fresh": report_fresh,
        "node_connected": node_connected,
        "current_state_known": report_fresh and node_connected,
    }


@router.get("/events/{node_id}")
def get_actuator_events(node_id: str, limit: int = Query(10, ge=1, le=100)):
    _get_actuator(node_id)
    events = list(
        actuator_events_collection.find(
            {"node_id": node_id}, {"_id": 0}
        ).sort("occurred_at", -1).limit(limit)
    )
    return {"node_id": node_id, "events": events}
