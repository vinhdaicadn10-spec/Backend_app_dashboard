# Định nghĩa và kiểm tra cấu trúc dữ liệu
from typing import Literal
from pydantic import BaseModel, Field


# Du lieu khi them node moi
class NodeCreate(BaseModel):
    id: str
    name: str
    type: str


# Du lieu khi cap nhat node
class NodeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    

# Du lieu Gateway gui den Backend
class GatewayHeartbeat(BaseModel):
    gateway_id: str
    wifi_rssi_dbm: int
    connected_nodes: int


# =====================================
# DU LIEU TRANG THAI MOT NODE
# =====================================


class NodeStateReport(BaseModel):
    id: str = Field(min_length=1)
    status: Literal["online", "offline"]

    # Cuong do tin hieu (dBm)
    rssi: int | None = Field(
        default=None, ge=-140, le=0
    )

    # Ti so tin hieu tren nhieu (dB)
    snr: float | None = Field(
        default=None, ge=-30, le=40
    )

    # Ty le goi tin thanh cong (%)
    packetSuccessRate: float | None = Field(
        default=None, ge=0, le=100
    )

    # Do tre (ms)
    latency: float | None = Field(
        default=None, ge=0
    )



# =====================================
# GATEWAY GUI DANH SACH TRANG THAI NODE
# =====================================

class GatewayNodesReport(BaseModel):
    gateway_id: str = Field(min_length=1)
    nodes: list[NodeStateReport] = Field(min_length=1)


# =========================================
# DU LIEU CAM BIEN KHOI
# =========================================

class SmokeReading(BaseModel):
    gateway_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    adc_value: int = Field(ge=0, le=4095)
