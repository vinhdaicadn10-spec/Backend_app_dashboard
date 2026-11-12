"""Bai 4 - Phan 16: API nhiet do GIA LAP, khong dung dieu khien canh bao.

POST /api/temperature/readings          - Gateway Simulator gui mau moi
GET  /api/temperature/latest/{node_id} - Doc mau moi nhat
GET  /api/temperature/history/{node_id} - Lich su nhiet do theo thoi gian

De demo, nhiet do duoc gan cho NODE-02 (SMOKE) nhung KHONG ham y
NODE-02 that su co phan cung do nhiet do. Khi co phan cung can doi schema.
"""
from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mongo_db import db, nodes_collection

router = APIRouter(prefix="/api/temperature", tags=["Temperature Demo"])
collection = db["temperature_readings"]
SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")


class TemperatureReading(BaseModel):
    gateway_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    temperature_c: float = Field(ge=-40, le=125)


def normalize_utc(value):
    """PyMongo co the tra datetime 'naive': trong du an quy uoc UTC."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_saigon(value):
    dt = normalize_utc(value)
    return dt.astimezone(SAIGON_TZ).isoformat() if dt else None


def check_node(node_id):
    # Phan 16 gia lap nhiet do tren NODE-02, KHONG phai do tu cam bien that.
    if node_id != "NODE-02" or nodes_collection.find_one(
        {"id": node_id, "type": "SMOKE"}, {"_id": 1}
    ) is None:
        raise HTTPException(status_code=404, detail="NODE-02 (SMOKE) chua duoc dang ky")


@router.post("/readings")
def add_temperature_reading(data: TemperatureReading):
    check_node(data.node_id)
    now = datetime.now(timezone.utc)
    reading = {
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "temperature_c": data.temperature_c,
        "received_at": now,
        "source": "simulator",
    }
    collection.insert_one(reading)
    return {
        "message": "Da luu nhiet do gia lap",
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "temperature_c": data.temperature_c,
        "received_at": to_saigon(now),
        "source": "simulator",
    }


@router.get("/latest/{node_id}")
def get_latest_temperature(
    node_id: str,
    gateway_id: str = Query(default="GW-SIM-01", min_length=1),
):
    check_node(node_id)
    doc = collection.find_one(
        {"gateway_id": gateway_id, "node_id": node_id},
        {"_id": 0}, sort=[("received_at", -1)],
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Chua co du lieu nhiet do gia lap")
    return {
        "gateway_id": gateway_id,
        "node_id": node_id,
        "temperature_c": doc.get("temperature_c"),
        "received_at": to_saigon(doc.get("received_at")),
        "source": doc.get("source", "simulator"),
    }


@router.get("/history/{node_id}")
def get_temperature_history(
    node_id: str,
    gateway_id: str = Query(default="GW-SIM-01", min_length=1),
    minutes: int = Query(default=15, ge=1, le=180),
    limit: int = Query(default=1200, ge=1, le=2000),
):
    check_node(node_id)
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)

    docs = list(
        collection.find(
            {"gateway_id": gateway_id, "node_id": node_id,
             "received_at": {"$gte": start, "$lte": now}},
            {"_id": 0, "received_at": 1, "temperature_c": 1},
        ).sort("received_at", -1).limit(limit + 1)
    )
    truncated = len(docs) > limit
    points = []
    for doc in reversed(docs[:limit]):
        dt = normalize_utc(doc.get("received_at"))
        value = doc.get("temperature_c")
        if dt is None or isinstance(value, bool) or not isinstance(value, (float, int)):
            continue
        points.append({
            "received_at": to_saigon(dt),
            "temperature_c": value,
        })
    values = [p["temperature_c"] for p in points]
    return {
        "gateway_id": gateway_id,
        "node_id": node_id,
        "window_minutes": minutes,
        "window_start": to_saigon(start),
        "window_end": to_saigon(now),
        "count_returned": len(points),
        "truncated": truncated,
        "points": points,
        "stats": {
            "min_temperature_c": min(values) if values else None,
            "max_temperature_c": max(values) if values else None,
            "avg_temperature_c": round(mean(values), 1) if values else None,
        },
        "source": "simulator",
        "note": "Nhiet do sinh ngau nhien de test; chua do tu phan cung.",
    }
