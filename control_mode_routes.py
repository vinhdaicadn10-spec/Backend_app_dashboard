"""Bai 4 - Phan 17A: Luu va doc che do AUTO/MANUAL (CHI THU NGHIEM).

Khong dieu khien coi/den; actuator_routes.py se tiep tuc quyet dinh
ON/OFF/HOLD theo canh bao nhu Phan 12. Khong trien khai API thay doi
che do khong xac thuc ra mang cong cong.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mongo_db import db, gateways_collection

router = APIRouter(prefix="/api/control", tags=["Operation Mode Demo"])
control_modes_collection = db["control_modes"]
SAIGON_TZ = timezone(timedelta(hours=7), name="Asia/Saigon")


class ModeChange(BaseModel):
    gateway_id: str = Field(min_length=1)
    mode: Literal["AUTO", "MANUAL"]


def check_gateway(gateway_id: str) -> None:
    gateway = gateways_collection.find_one(
        {"gateway_id": gateway_id}, {"_id": 1}
    )
    if gateway is None:
        raise HTTPException(status_code=404, detail="Gateway chua ton tai")


def to_saigon(value):
    if not isinstance(value, datetime):
        return None
    # Trong du an, ngay khong kem timezone duoc quy uoc la UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SAIGON_TZ).isoformat()


@router.get("/mode/{gateway_id}")
def get_operation_mode(gateway_id: str):
    """Xem che do da luu. Neu chua cai dat, mac dinh AUTO (khong ghi DB)."""
    check_gateway(gateway_id)
    record = control_modes_collection.find_one(
        {"gateway_id": gateway_id}, {"_id": 0}
    )
    return {
        "gateway_id": gateway_id,
        "mode": record.get("mode", "AUTO") if record else "AUTO",
        "saved": record is not None,
        "updated_at": to_saigon(record.get("updated_at")) if record else None,
        "note": "Che do thu nghiem; chua ket noi dieu khien coi/den",
    }


@router.post("/mode")
def set_operation_mode(data: ModeChange):
    """Luu AUTO/MANUAL. Khong tu gui lenh den thiet bi chieu thuong."""
    check_gateway(data.gateway_id)
    now = datetime.now(timezone.utc)
    control_modes_collection.update_one(
        {"gateway_id": data.gateway_id},
        {"$set": {"mode": data.mode, "updated_at": now}},
        upsert=True,
    )
    return {
        "message": "Da luu che do thu nghiem",
        "gateway_id": data.gateway_id,
        "mode": data.mode,
        "updated_at": to_saigon(now),
        "note": "Chua thay doi logic coi/den; actuator_routes.py van xu ly canh bao",
    }
