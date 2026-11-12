"""Gateway Simulator Bai 4 - Phan 18C.2.

Ke thua Phan 16; them nhan lenh MANUAL rieng coi va den NODE-03.
Khong ket noi, khong bat/tat bat ky phan cung nao.
"""

import json
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = "http://127.0.0.1:8000"
GATEWAY_ID = "GW-SIM-01"
SEND_INTERVAL = 10

# False: gia lap ADC thap (300-450); True: gia lap ADC cao (1700-2000).
# Chi dung thu phan mem; khong phai nguong bao chay thuc te.
SIMULATE_HIGH_ADC = False

# Doi True de thu nhan nut NODE-01, False la nha nut.
# NHA NUT KHONG XOA CANH BAO! Reset trong Swagger khi da nha.
SIMULATE_BUTTON_PRESSED = False


def call_api(endpoint, data=None):
    is_post = data is not None
    request = Request(
        API_BASE + endpoint,
        data=json.dumps(data).encode("utf-8") if is_post else None,
        headers={"Content-Type": "application/json"} if is_post else {},
        method="POST" if is_post else "GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"{endpoint} -> HTTP {response.status}")
            return result
    except HTTPError as error:
        print(f"{endpoint} -> HTTP {error.code}: {error.read().decode('utf-8')}")
    except (URLError, TimeoutError, ValueError) as error:
        print(f"{endpoint} -> Loi: {error}")
    return None


def create_nodes():
    return [
        {
            "id": "NODE-01", "status": "online",
            "rssi": random.randint(-66, -57),
            "snr": round(random.uniform(6.0, 10.0), 1),
            "packetSuccessRate": round(random.uniform(97.0, 100.0), 1),
            "latency": round(random.uniform(30.0, 65.0), 1),
        },
        {
            "id": "NODE-02", "status": "online",
            "rssi": random.randint(-75, -63),
            "snr": round(random.uniform(2.0, 7.0), 1),
            "packetSuccessRate": round(random.uniform(93.0, 99.0), 1),
            "latency": round(random.uniform(50.0, 110.0), 1),
        },
        {
            "id": "NODE-03", "status": "online",
            "rssi": random.randint(-76, -66),
            "snr": round(random.uniform(2.0, 7.0), 1),
            "packetSuccessRate": round(random.uniform(93.0, 99.0), 1),
            "latency": round(random.uniform(60.0, 130.0), 1),
        },
    ]


def apply_desired_command(command, old_siren, old_light):
    """Chuyen lenh Backend thanh trang thai GIA LAP.

    Tra ve (siren_on, light_on, should_report).
    Chua co lenh hop le / HOLD khi chua biet trang thai -> khong bao cao.
    """
    decision = command.get("decision")
    if decision == "ON":
        return True, True, True
    if decision == "OFF":
        return False, False, True
    if decision == "MANUAL":
        siren = command.get("siren_on")
        light = command.get("light_on")
        if type(siren) is bool and type(light) is bool:
            return siren, light, True
        return old_siren, old_light, False
    if decision == "HOLD":
        return (old_siren, old_light,
                old_siren is not None and old_light is not None)
    return old_siren, old_light, False


def main():
    # Day chi la bien Python, khong dieu khien thiet bi that.
    siren_on = None  # Chua co lenh ON/OFF tu Backend thi KHONG bao cao.
    light_on = None
    print("GATEWAY SIMULATOR - PHAN 18C.2 (MANUAL NODE-03 DEMO)")
    print("Nhan Ctrl+C de dung.")

    try:
        while True:
            nodes = create_nodes()
            count_online = sum(node["status"] == "online" for node in nodes)
            adc_value = (
                random.randint(1700, 2000)
                if SIMULATE_HIGH_ADC else random.randint(300, 450)
            )

            print("\n--- CHU KY MOI ---")
            temperature_c = round(random.uniform(31.0, 35.0), 1)
            print(f"Node online: {count_online}/{len(nodes)} | ADC: {adc_value} | Nhiet do DEMO: {temperature_c} C")

            call_api("/api/gateway/heartbeat", {
                "gateway_id": GATEWAY_ID,
                "wifi_rssi_dbm": -65,
                "connected_nodes": count_online,
            })
            call_api("/api/gateway/nodes/report", {
                "gateway_id": GATEWAY_ID,
                "nodes": nodes,
            })
            if any(node["id"] == "NODE-01" and node["status"] == "online" for node in nodes):
                result = call_api("/api/button/report", {
                    "gateway_id": GATEWAY_ID,
                    "node_id": "NODE-01",
                    "pressed": SIMULATE_BUTTON_PRESSED,
                })
                if result is not None:
                    print(f"Nut NODE-01: {'NHAN' if SIMULATE_BUTTON_PRESSED else 'NHA'}"
                          f" | Canh bao duoc giu: {result.get('alarm_active')}")

            if any(node["id"] == "NODE-02" and node["status"] == "online" for node in nodes):
                call_api("/api/smoke/readings", {
                    "gateway_id": GATEWAY_ID,
                    "node_id": "NODE-02",
                    "adc_value": adc_value,
                })
                # Moi: nhiet do GIA LAP de thu bieu do (NODE-02 chua chac co cam bien nhiet that).
                call_api("/api/temperature/readings", {
                    "gateway_id": GATEWAY_ID,
                    "node_id": "NODE-02",
                    "temperature_c": temperature_c,
                })

            actuator_node_online = any(
                node["id"] == "NODE-03" and node["status"] == "online"
                for node in nodes
            )
            command = (
                call_api(f"/api/actuator/desired/{GATEWAY_ID}")
                if actuator_node_online else None
            )
            if not actuator_node_online:
                print("NODE-03 Offline: khong mo phong lenh hay bao cao coi/den")
            if command is not None:
                decision = command.get("decision")
                print(f"Lenh Backend: {decision} | Nguon: {command.get('source')} | Mode: {command.get('mode')}")
                siren_on, light_on, should_report = apply_desired_command(
                    command, siren_on, light_on
                )
                if decision == "HOLD":
                    print("HOLD: thieu du lieu moi, khong tu dong tat coi/den")
                if decision == "MANUAL" and not should_report:
                    print("Lenh MANUAL khong hop le, khong gui bao cao")
                if should_report:
                    call_api("/api/actuator/report", {
                        "gateway_id": GATEWAY_ID,
                        "node_id": "NODE-03",
                        "siren_on": siren_on,
                        "light_on": light_on,
                    })
                print(f"Coi gia lap: {'CHUA XAC DINH' if siren_on is None else 'BAT' if siren_on else 'TAT'}")
                print(f"Den gia lap: {'CHUA XAC DINH' if light_on is None else 'BAT' if light_on else 'TAT'}")

            print(f"Cho {SEND_INTERVAL} giay...")
            time.sleep(SEND_INTERVAL)
    except KeyboardInterrupt:
        print("\nDa dung Gateway Simulator Phan 18C.2")


if __name__ == "__main__":
    main()
