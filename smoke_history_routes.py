"""Bai 4 - Phan 15: API doc LICH SU ADC (chi doc).

Khong sua logic canh bao Phan 10/12, khong phat lenh.
Doc collection smoke_readings do POST /api/smoke/readings da luu.
"""

from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import APIRouter, HTTPException, Query
from mongo_db import nodes_collection, smoke_readings_collection
from smoke_routes import ALARM_ON_ADC, ALARM_OFF_ADC

router = APIRouter(prefix="/api/smoke", tags=["Smoke History Demo"])

SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")


def to_utc(value):
    """PyMongo co the tra datetime khong kem timezone (naive): coi la UTC."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/history/{node_id}")
def get_smoke_history(
    node_id: str,
    gateway_id: str = Query(default="GW-SIM-01", min_length=1),
    minutes: int = Query(default=60, ge=1, le=180),
    limit: int = Query(default=1200, ge=1, le=2000),
):
    """Lay cac mau ADC moi nhat trong N phut, sap xep tu cu den moi.

    Neu qua limit, chi lay limit mau gan nhat va tra truncated=True.
    Khong nham lich su gia tri ADC voi lich su su kien smoke_alerts.
    """
    existing = nodes_collection.find_one({"id": node_id, "type": "SMOKE"}, {"_id": 1})
    if existing is None:
        raise HTTPException(status_code=404, detail="Khong tim thay Node cam bien khoi")

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)

    cursor = (
        smoke_readings_collection.find(
            {
                "gateway_id": gateway_id,
                "node_id": node_id,
                "received_at": {"$gte": start, "$lte": now},
            },
            {"_id": 0, "adc_value": 1, "received_at": 1},
        )
        .sort("received_at", -1)
        .limit(limit + 1)
    )
    newest_first = list(cursor)
    truncated = len(newest_first) > limit
    newest_first = newest_first[:limit]

    points = []
    # Dao nguoc de truc X chay tu thoi diem cu sang moi.
    for item in reversed(newest_first):
        timestamp = to_utc(item.get("received_at"))
        adc = item.get("adc_value")
        if timestamp is None or not isinstance(adc, int) or not (0 <= adc <= 4095):
            continue
        points.append({
            "received_at": timestamp.astimezone(SAIGON_TZ).isoformat(),
            "adc_value": adc,
        })

    values = [p["adc_value"] for p in points]
    return {
        "gateway_id": gateway_id,
        "node_id": node_id,
        "window_minutes": minutes,
        "window_start": start.astimezone(SAIGON_TZ).isoformat(),
        "window_end": now.astimezone(SAIGON_TZ).isoformat(),
        "count_returned": len(points),
        "truncated": truncated,
        "points": points,
        "stats": {
            "min_adc": min(values) if values else None,
            "max_adc": max(values) if values else None,
            "avg_adc": round(mean(values), 1) if values else None,
        },
        "demo_thresholds": {
            "alarm_on_adc": ALARM_ON_ADC,
            "alarm_off_adc": ALARM_OFF_ADC,
        },
        "note": "Lich su ADC mo phong; nguong chi de test phan mem, khong phai nguong bao chay thuc te.",
    }
