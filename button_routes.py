"""Part 12 - DEMO emergency button (NODE-01), for local software testing only.

A press latches an alarm; releasing the button does NOT clear it.
A separate manual demo reset is allowed only after a fresh released report.
This is not a certified emergency signaling system.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mongo_db import db, nodes_collection

router = APIRouter(prefix="/api/button", tags=["Emergency Button Demo"])
button_events_collection = db["button_events"]
BUTTON_NODE_ID = "NODE-01"
FRESH_SECONDS = 30


class ButtonReport(BaseModel):
    gateway_id: str = Field(min_length=1)
    node_id: Literal["NODE-01"]
    pressed: bool


class ButtonReset(BaseModel):
    gateway_id: str = Field(min_length=1)
    node_id: Literal["NODE-01"]


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _recent(value, now):
    at = _as_utc(value)
    return at is not None and 0 <= (now - at).total_seconds() <= FRESH_SECONDS


def _get_node(node_id, gateway_id=None):
    query = {"id": node_id, "type": "BUTTON"}
    if gateway_id is not None:
        query["gateway_id"] = gateway_id
    node = nodes_collection.find_one(query, {"_id": 0})
    if node is None:
        raise HTTPException(status_code=404, detail="Khong tim thay NODE-01 thuoc Gateway nay")
    return node


@router.post("/report")
def report_button(data: ButtonReport):
    node = _get_node(data.node_id, data.gateway_id)
    now = datetime.now(timezone.utc)
    if node.get("status") != "online" or not _recent(node.get("last_reported_at"), now):
        raise HTTPException(status_code=409, detail="Node nut nhan chua Online/khong co bao cao moi")

    # A press makes the alarm latch. Repeated 10-second reports do not create extra events.
    new_event = None
    if data.pressed:
        changed = nodes_collection.update_one(
            {"id": data.node_id, "type": "BUTTON", "gateway_id": data.gateway_id,
             "button_alarm_active": {"$ne": True}},
            {"$set": {"button_alarm_active": True,
                      "button_alarm_changed_at": now}},
        )
        if changed.modified_count == 1:
            new_event = "BUTTON_PRESSED"
            button_events_collection.insert_one({
                "gateway_id": data.gateway_id,
                "node_id": data.node_id,
                "event_type": new_event,
                "occurred_at": now,
            })

    # Releasing the physical button changes pressed, but never clears the latch.
    nodes_collection.update_one(
        {"id": data.node_id, "type": "BUTTON", "gateway_id": data.gateway_id},
        {"$set": {"button_pressed": data.pressed,
                  "last_button_report_at": now}},
    )
    latest = _get_node(data.node_id, data.gateway_id)
    return {
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "pressed": data.pressed,
        "alarm_active": latest.get("button_alarm_active") is True,
        "new_event": new_event,
        "reported_at": now.isoformat(),
    }


@router.post("/reset")
def reset_button_demo(data: ButtonReset):
    """Manual demo reset via Swagger, NOT a remote reset of safety equipment."""
    node = _get_node(data.node_id, data.gateway_id)
    now = datetime.now(timezone.utc)
    if not _recent(node.get("last_button_report_at"), now) or node.get("status") != "online":
        raise HTTPException(status_code=409, detail="Bao cao nut nhan khong moi; khong reset")
    if node.get("button_pressed") is not False:
        raise HTTPException(status_code=409, detail="Nut van dang duoc nhan; hay nha nut truoc")

    changed = nodes_collection.update_one(
        {"id": data.node_id, "type": "BUTTON", "gateway_id": data.gateway_id,
         "button_pressed": False, "button_alarm_active": True},
        {"$set": {"button_alarm_active": False,
                  "button_alarm_changed_at": now}},
    )
    did_reset = changed.modified_count == 1
    if did_reset:
        button_events_collection.insert_one({
            "gateway_id": data.gateway_id,
            "node_id": data.node_id,
            "event_type": "BUTTON_RESET",
            "occurred_at": now,
        })
    return {"node_id": data.node_id, "alarm_active": False,
            "reset_performed": did_reset, "reset_at": now.isoformat()}


@router.get("/status/{node_id}")
def get_button_status(node_id: str):
    node = _get_node(node_id)
    now = datetime.now(timezone.utc)
    fresh = _recent(node.get("last_button_report_at"), now) and node.get("status") == "online" and _recent(node.get("last_reported_at"), now)
    reported = _as_utc(node.get("last_button_report_at"))
    return {
        "node_id": node_id,
        "gateway_id": node.get("gateway_id"),
        "pressed": node.get("button_pressed"),
        "alarm_active": node.get("button_alarm_active") is True,
        "report_fresh": fresh,
        "last_reported_at": reported.isoformat() if reported else None,
    }


@router.get("/events/{node_id}")
def get_button_events(node_id: str, limit: int = Query(default=10, ge=1, le=100)):
    _get_node(node_id)
    events = list(button_events_collection.find(
        {"node_id": node_id}, {"_id": 0}
    ).sort("occurred_at", -1).limit(limit))
    return {"node_id": node_id, "events": events}
