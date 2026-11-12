"""Bai 4 - Phan 13: API TONG QUAN HE THONG (chi doc - demo).

Doc thong tin Gateway, cac Node, khoi, nut nhan, coi/den tu MongoDB.
Khong phat lenh va khong thay the mach canh bao tai cho.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from mongo_db import gateways_collection, nodes_collection, smoke_readings_collection

router = APIRouter(prefix="/api/system", tags=["System Overview Demo"])

FRESH_SECONDS = 30
SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")
SMOKE_NODE_ID = "NODE-02"
BUTTON_NODE_ID = "NODE-01"
ACTUATOR_NODE_ID = "NODE-03"


def as_utc(value):
    """MongoDB co the tra ve datetime naive; quy uoc gia tri do la UTC."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def fresh(value, now):
    timestamp = as_utc(value)
    return timestamp is not None and 0 <= (now - timestamp).total_seconds() <= FRESH_SECONDS


def saigon_time(value):
    timestamp = as_utc(value)
    return timestamp.astimezone(SAIGON_TZ).isoformat() if timestamp else None


@router.get("/overview/{gateway_id}")
def get_system_overview(gateway_id: str):
    """Tong hop mot ban chup du lieu. Khong cap nhat database."""
    gateway = gateways_collection.find_one({"gateway_id": gateway_id}, {"_id": 0})
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway chua co heartbeat trong MongoDB")

    now = datetime.now(timezone.utc)
    gateway_fresh = fresh(gateway.get("last_seen"), now)

    # Danh sach Node da duoc Gateway nay bao cao (khong lay Node cua Gateway khac).
    node_docs = list(nodes_collection.find({"gateway_id": gateway_id}, {"_id": 0}))
    by_id = {node["id"]: node for node in node_docs if node.get("id")}
    counts = {"total": len(node_docs), "online": 0, "offline": 0,
              "stale": 0, "unknown": 0}

    for node in node_docs:
        if not fresh(node.get("last_reported_at"), now):
            counts["stale"] += 1
        elif node.get("status") == "online":
            counts["online"] += 1
        elif node.get("status") == "offline":
            counts["offline"] += 1
        else:
            counts["unknown"] += 1

    smoke_node = by_id.get(SMOKE_NODE_ID, {})
    button_node = by_id.get(BUTTON_NODE_ID, {})
    actuator_node = by_id.get(ACTUATOR_NODE_ID, {})

    latest_smoke = smoke_readings_collection.find_one(
        {"gateway_id": gateway_id, "node_id": SMOKE_NODE_ID},
        {"_id": 0},
        sort=[("received_at", -1)],
    ) or {}

    smoke_fresh = (
        fresh(latest_smoke.get("received_at"), now)
        and smoke_node.get("status") == "online"
        and fresh(smoke_node.get("last_reported_at"), now)
    )
    button_fresh = (
        button_node.get("status") == "online"
        and fresh(button_node.get("last_reported_at"), now)
        and fresh(button_node.get("last_button_report_at"), now)
    )
    actuator_known = (
        actuator_node.get("status") == "online"
        and fresh(actuator_node.get("last_reported_at"), now)
        and fresh(actuator_node.get("last_actuator_report_at"), now)
        and isinstance(actuator_node.get("siren_on"), bool)
        and isinstance(actuator_node.get("light_on"), bool)
    )

    # Trang thai canh bao da chot: khong tu xoa vi du lieu qua cu.
    smoke_alarm = smoke_node.get("smoke_alert_active") is True
    button_alarm = button_node.get("button_alarm_active") is True

    reasons = []
    if not gateway_fresh:
        reasons.append("Gateway mat heartbeat")
    if counts["offline"]:
        reasons.append(f"Co {counts['offline']} Node offline")
    if counts["stale"] or counts["unknown"]:
        reasons.append("Co Node mat cap nhat/chua ro trang thai")
    if not smoke_fresh:
        reasons.append("Du lieu cam bien khoi khong moi")
    if not button_fresh:
        reasons.append("Du lieu nut nhan khong moi")
    if not actuator_known:
        reasons.append("Chua xac nhan duoc trang thai coi/den")

    # Uu tien hien canh bao da chot; neu khong, khong duoc bao "an toan"
    # khi thieu bao cao cua nhung nguon quan trong.
    if smoke_alarm or button_alarm:
        overall_status = "ALARM"
    elif (not gateway_fresh or not smoke_fresh or not button_fresh
          or not actuator_known or counts["stale"] or counts["unknown"]
          or any(node_id not in by_id for node_id in (
              SMOKE_NODE_ID, BUTTON_NODE_ID, ACTUATOR_NODE_ID))):
        overall_status = "UNKNOWN"
    elif counts["offline"]:
        overall_status = "DEGRADED"
    else:
        overall_status = "NORMAL"

    return {
        "gateway_id": gateway_id,
        "checked_at": now.astimezone(SAIGON_TZ).isoformat(),
        "overall_status": overall_status,
        "gateway": {
            "status": "ONLINE" if gateway_fresh else "OFFLINE",
            "wifi_rssi_dbm": gateway.get("wifi_rssi_dbm"),
            "connected_nodes_reported": gateway.get("connected_nodes"),
            "last_seen": saigon_time(gateway.get("last_seen")),
        },
        "nodes": counts,
        "smoke": {
            "node_id": SMOKE_NODE_ID,
            "adc_value": latest_smoke.get("adc_value"),
            "alarm_active": smoke_alarm,
            "data_fresh": smoke_fresh,
            "last_received_at": saigon_time(latest_smoke.get("received_at")),
        },
        "button": {
            "node_id": BUTTON_NODE_ID,
            "pressed": button_node.get("button_pressed") if button_fresh else None,
            "alarm_active": button_alarm,
            "data_fresh": button_fresh,
            "last_reported_at": saigon_time(button_node.get("last_button_report_at")),
        },
        "actuator": {
            "node_id": ACTUATOR_NODE_ID,
            "siren_on": actuator_node.get("siren_on") if actuator_known else None,
            "light_on": actuator_node.get("light_on") if actuator_known else None,
            "state_known": actuator_known,
            "last_reported_at": saigon_time(actuator_node.get("last_actuator_report_at")),
        },
        "reasons": reasons,
        "note": "Chi la trang thai demo tu MongoDB; khong thay the he thong canh bao tai cho",
    }
