
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from schemas import GatewayHeartbeat, GatewayNodesReport
from mongo_db import gateways_collection, nodes_collection


# ========================================
# CAU HINH MUI GIO VIET NAM
# ========================================

VN_TZ = timezone(timedelta(hours=7))


# ========================================
# TAO ROUTER CHO GATEWAY
# ========================================

router = APIRouter(
    prefix="/api/gateway",
    tags=["Gateway"]
)


# ========================================
# 1. API NHAN HEARTBEAT TU GATEWAY
# ========================================

@router.post("/heartbeat")
def receive_heartbeat(data: GatewayHeartbeat):

    # 1. Lay thoi gian hien tai theo UTC
    now = datetime.now(timezone.utc)

    # 2. Chuyen sang gio Viet Nam
    now_vn = now.astimezone(VN_TZ)

    # 3. Them hoac cap nhat Gateway trong MongoDB
    gateways_collection.update_one(
        {"gateway_id": data.gateway_id},
        {
            "$set": {
                "gateway_id": data.gateway_id,
                "wifi_rssi_dbm": data.wifi_rssi_dbm,
                "connected_nodes": data.connected_nodes,
                "last_seen": now
            }
        },
        upsert=True
    )

    # 4. In thong tin Gateway ra Terminal
    print("============================")
    print("Da nhan heartbeat!")
    print("Gateway ID:", data.gateway_id)
    print("WiFi RSSI:", data.wifi_rssi_dbm)
    print("So node:", data.connected_nodes)
    print(
        "Gio Viet Nam:",
        now_vn.strftime("%d/%m/%Y %H:%M:%S")
    )
    print("============================")

    # 5. Tra ve thoi gian Viet Nam
    return {
        "status": "received",
        "message": "Backend da nhan du lieu Gateway",
        "gateway_id": data.gateway_id,
        "wifi_rssi_dbm": data.wifi_rssi_dbm,
        "connected_nodes": data.connected_nodes,
        "last_seen": now_vn.isoformat()
    }


# ========================================
# 2. API XEM TRANG THAI GATEWAY
# ========================================

@router.get("/status/{gateway_id}")
def get_gateway_status(gateway_id: str):

    # 1. Tim Gateway trong MongoDB
    gateway = gateways_collection.find_one(
        {"gateway_id": gateway_id},
        {"_id": 0}
    )

    # 2. Kiem tra Gateway co ton tai khong
    if gateway is None:
        raise HTTPException(
            status_code=404,
            detail="Khong tim thay Gateway"
        )

    # 3. Lay thoi gian heartbeat gan nhat
    last_seen = gateway["last_seen"]

    # MongoDB co the tra ve datetime khong co timezone
    # Neu thieu timezone thi xem du lieu la UTC
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(
            tzinfo=timezone.utc
        )

    # 4. Chuyen thoi gian sang gio Viet Nam
    last_seen_vn = last_seen.astimezone(VN_TZ)

    # 5. Tinh so giay tu heartbeat gan nhat
    now = datetime.now(timezone.utc)

    elapsed = max(
        0,
        (now - last_seen).total_seconds()
    )

    # 6. Kiem tra online / offline
    if elapsed <= 30:
        gateway_status = "online"
    else:
        gateway_status = "offline"

    # 7. Tra ve du lieu cho Dashboard / App
    return {
        "gateway_id": gateway["gateway_id"],
        "wifi_rssi_dbm": gateway["wifi_rssi_dbm"],
        "connected_nodes": gateway["connected_nodes"],
        "last_seen": last_seen_vn.isoformat(),
        "last_seen_display": last_seen_vn.strftime(
            "%d/%m/%Y %H:%M:%S"
        ),
        "seconds_since_last_seen": round(elapsed, 1),
        "status": gateway_status
    }


# =========================================
# API NHAN TRANG THAI CAC NODE TU GATEWAY
# =========================================


@router.post("/nodes/report")
def receive_nodes_report(data: GatewayNodesReport):

    now = datetime.now(timezone.utc)

    updated_nodes = []
    not_found_nodes = []

    metric_fields = (
        "rssi",
        "snr",
        "packetSuccessRate",
        "latency"
    )

    for node in data.nodes:

        # Du lieu luu trong MongoDB
        set_fields = {
            "status": node.status,
            "gateway_id": data.gateway_id,
            "last_reported_at": now
        }

        unset_fields = {}

        # Luu chi so neu Node Online
        for field in metric_fields:

            value = getattr(node, field)

            if node.status == "online" and value is not None:
                set_fields[field] = value
            else:
                # Xoa so do cu khi Node Offline
                # hoac khong co chi so moi
                unset_fields[field] = ""

        update = {
            "$set": set_fields
        }

        if unset_fields:
            update["$unset"] = unset_fields

        result = nodes_collection.update_one(
            {"id": node.id},
            update
        )

        if result.matched_count > 0:
            updated_nodes.append({
                "id": node.id,
                "status": node.status
            })
        else:
            not_found_nodes.append(node.id)

    return {
        "message": "Da xu ly bao cao Node",
        "gateway_id": data.gateway_id,
        "updated_count": len(updated_nodes),
        "updated_nodes": updated_nodes,
        "not_found_nodes": not_found_nodes,
        "reported_at": now.astimezone(VN_TZ).isoformat()
    }
