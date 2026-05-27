"""
publisher.py — Virtual PLC / Data Generator
=============================================
Generates synthetic telemetry for petrochemical plant assets
and securely publishes it to Azure IoT Hub via SAS-token auth.

Usage:
    python publisher.py

Environment variables required (.env or Azure App Settings):
    IOTHUB_DEVICE_CONNECTION_STRING  — IoT Hub device connection string
"""

import os
import json
import time
import random
import math
from datetime import datetime, timezone
from dotenv import load_dotenv

# Attempt to import Azure IoT SDK; fall back to demo mode if not installed
try:
    from azure.iot.device import IoTHubDeviceClient, Message
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("[DEMO MODE] azure-iot-device not installed — printing to console only.")

load_dotenv()

# ──────────────────────────────────────────────
# Plant asset definitions
# ──────────────────────────────────────────────
MACHINES = {
    "pump_01": {
        "temp_base":      65.0,   # °C
        "vibration_base":  0.35,  # g
        "power_base":     45.0,   # kW
    },
    "compressor_01": {
        "temp_base":      80.0,
        "vibration_base":  0.55,
        "power_base":     60.0,
    },
    "reactor_01": {
        "temp_base":      90.0,
        "vibration_base":  0.20,
        "power_base":     30.0,
    },
}

# Degradation simulation (fault injection after 2 minutes)
FAULT_START_TIME: float = time.time() + 120   # seconds
FAULT_MACHINE    = "compressor_01"


def gaussian_noise(value: float, std_pct: float = 0.05) -> float:
    """Add Gaussian noise proportional to the base value."""
    return round(value + random.gauss(0, value * std_pct), 3)


def degradation_factor(machine_id: str) -> float:
    """
    Return a multiplier > 1.0 if the machine is past its fault-start
    time, simulating gradual degradation (rising vibration, temperature).
    """
    if machine_id != FAULT_MACHINE:
        return 1.0
    elapsed = max(0.0, time.time() - FAULT_START_TIME)
    return 1.0 + 0.002 * elapsed   # +0.2 % per second after fault start


def generate_telemetry(machine_id: str) -> dict:
    """Build a structured telemetry payload for the given machine."""
    cfg    = MACHINES[machine_id]
    factor = degradation_factor(machine_id)

    return {
        "machine_id":  machine_id,
        "temperature": gaussian_noise(cfg["temp_base"]      * factor),
        "vibration":   gaussian_noise(cfg["vibration_base"] * factor),
        "power":       gaussian_noise(cfg["power_base"]     * math.sqrt(factor)),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }


def run_publisher(interval_seconds: float = 1.0):
    """Main publish loop — sends telemetry for every machine each interval."""
    conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")

    client = None
    if AZURE_AVAILABLE and conn_str:
        client = IoTHubDeviceClient.create_from_connection_string(conn_str)
        client.connect()
        print("[IoT Hub] Connected — publishing live telemetry.")
    else:
        print("[DEMO] Running in console-output mode (no Azure connection).")

    print(f"Publishing telemetry for: {list(MACHINES.keys())}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            for machine_id in MACHINES:
                payload  = generate_telemetry(machine_id)
                json_str = json.dumps(payload)

                if client:
                    msg = Message(json_str)
                    msg.content_encoding = "utf-8"
                    msg.content_type     = "application/json"
                    client.send_message(msg)

                # Always print locally for visibility
                status = "⚠️ FAULT" if (
                    machine_id == FAULT_MACHINE
                    and time.time() > FAULT_START_TIME
                ) else "✅ OK"
                print(
                    f"[{payload['timestamp'][11:19]}] {machine_id:20s} "
                    f"T={payload['temperature']:6.1f}°C  "
                    f"V={payload['vibration']:.3f}g  "
                    f"P={payload['power']:5.1f}kW  {status}"
                )

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\nPublisher stopped.")
    finally:
        if client:
            client.disconnect()


if __name__ == "__main__":
    run_publisher(interval_seconds=1.0)
