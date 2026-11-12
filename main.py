
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from smoke_routes import router as smoke_router
from nodes_routes import router as nodes_router
from gateway_routes import router as gateway_router
from actuator_routes import router as actuator_router
from button_routes import router as button_router
from system_routes import router as system_router
from event_routes import router as event_router
from smoke_history_routes import router as smoke_history_router
from temperature_routes import router as temperature_router
from control_mode_routes import router as control_mode_router
from operator_alarm_routes import router as operator_alarm_router
from manual_control_routes import router as manual_control_router
from fastapi.middleware.cors import CORSMiddleware

# Tao ung dung FastAPI
app = FastAPI(
    title="Fire Alarm Backend",
    description="Backend he thong bao chay IoT"
)


# Cho phep Web Dashboard goi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dang ky nhom API Nodes
app.include_router(nodes_router)

# Dang ky nhom API Gateway
app.include_router(gateway_router)

# Dang ky nhom API cam bien khoi
app.include_router(smoke_router)

app.include_router(actuator_router)

app.include_router(button_router)

app.include_router(system_router)

app.include_router(event_router)

app.include_router(smoke_history_router)

app.include_router(temperature_router)

app.include_router(control_mode_router)

app.include_router(operator_alarm_router)

app.include_router(manual_control_router)


# API trang chu
@app.get("/")
def home():
    return {
        "message": "Backend he thong bao chay dang hoat dong"
    }


# API kiem tra Server
@app.get("/api/health")
def check_health():
    return {
        "status": "ok",
        "message": "Server dang hoat dong"
    }
