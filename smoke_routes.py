"""Bai 4 - Phan 10: Doc ADC va tao su kien canh bao MO PHONG.

Thay the smoke_routes.py Phan 9. Khong thay doi API cu:
    POST /api/smoke/readings
    GET  /api/smoke/latest/{node_id}
Bo sung:
    GET  /api/smoke/alerts/{node_id}

Chu y: Nguong chi phuc vu TEST software, khong phai nguong bao chay thuc te.
Khong dung backend, dashboard hay HTTP de thay the bao chay tai cho.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from mongo_db import db, nodes_collection, smoke_readings_collection
from schemas import SmokeReading

router = APIRouter(prefix="/api/smoke", tags=["Smoke Sensor"])

smoke_alerts_collection = db["smoke_alerts"]

# Nguong gia lap de thu API va Dashboard; KHONG dung lam nguong an toan.
ALARM_ON_ADC = 1500
ALARM_OFF_ADC = 1200


def _get_smoke_node(node_id: str):
    node = nodes_collection.find_one(
        {"id": node_id, "type": "SMOKE"},
        {"_id": 0, "id": 1, "smoke_alert_active": 1},
    )
    if node is None:
        raise HTTPException(
            status_code=404,
            detail="Khong tim thay Node cam bien khoi da dang ky",
        )
    return node


@router.post("/readings")
def create_smoke_reading(data: SmokeReading):
    _get_smoke_node(data.node_id)
    now = datetime.now(timezone.utc)

    # 1. Ghi lich su ADC, nhu Phan 9.
    reading = {
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "adc_value": data.adc_value,
        "received_at": now,
    }
    smoke_readings_collection.insert_one(reading)

    # 2. Chi tao SU KIEN khi trang thai THAY DOI.
    # filter + update atomic tren mot Node tranh nhieu su kien trung
    # khi Gateway gui ADC lon lien tuc 10 giay mot lan.
    new_event = None

    if data.adc_value >= ALARM_ON_ADC:
        changed = nodes_collection.update_one(
            {
                "id": data.node_id,
                "type": "SMOKE",
                "smoke_alert_active": {"$ne": True},
            },
            {
                "$set": {
                    "smoke_alert_active": True,
                    "smoke_alert_changed_at": now,
                }
            },
        )
        if changed.modified_count == 1:
            new_event = "ALARM_TRIGGERED"

    elif data.adc_value <= ALARM_OFF_ADC:
        changed = nodes_collection.update_one(
            {
                "id": data.node_id,
                "type": "SMOKE",
                "smoke_alert_active": True,
            },
            {
                "$set": {
                    "smoke_alert_active": False,
                    "smoke_alert_changed_at": now,
                }
            },
        )
        if changed.modified_count == 1:
            new_event = "ALARM_CLEARED"

    # 1200 < ADC < 1500: giu nguyen trang thai truoc do.
    if new_event is not None:
        smoke_alerts_collection.insert_one(
            {
                "gateway_id": data.gateway_id,
                "node_id": data.node_id,
                "event_type": new_event,
                "adc_value": data.adc_value,
                "occurred_at": now,
            }
        )

    node = _get_smoke_node(data.node_id)
    return {
        "message": "Da luu gia tri ADC cam bien khoi",
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "adc_value": data.adc_value,
        "received_at": now.isoformat(),
        "alarm_active": node.get("smoke_alert_active") is True,
        "new_event": new_event,
        "threshold_high": ALARM_ON_ADC,
        "threshold_clear": ALARM_OFF_ADC,
    }


@router.get("/latest/{node_id}")
def get_latest_smoke_reading(node_id: str):
    _get_smoke_node(node_id)
    reading = smoke_readings_collection.find_one(
        {"node_id": node_id},
        {"_id": 0},
        sort=[("received_at", -1)],
    )
    if reading is None:
        raise HTTPException(
            status_code=404,
            detail="Node chua gui du lieu cam bien khoi",
        )
    node = _get_smoke_node(node_id)
    return {
        **reading,
        "alarm_active": node.get("smoke_alert_active") is True,
        "threshold_high": ALARM_ON_ADC,
        "threshold_clear": ALARM_OFF_ADC,
    }


@router.get("/alerts/{node_id}")
def get_smoke_alerts(node_id: str, limit: int = Query(20, ge=1, le=100)):
    _get_smoke_node(node_id)
    events = list(
        smoke_alerts_collection.find(
            {"node_id": node_id}, {"_id": 0}
        ).sort("occurred_at", -1).limit(limit)
    )
    return {
        "node_id": node_id,
        "total_returned": len(events),
        "events": events,
    }
