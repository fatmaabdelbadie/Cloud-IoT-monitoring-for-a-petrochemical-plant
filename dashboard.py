"""
dashboard.py — Real-time Dash/Plotly Monitoring Dashboard
==========================================================
Connects to Azure Event Hub, deserializes telemetry, applies
predictive maintenance rules, and visualizes plant health.

Usage:
    python dashboard.py

Open http://localhost:8050 in your browser.
"""

import os
import json
import time
import random
import threading
from collections import defaultdict, deque
from datetime import datetime
from dotenv import load_dotenv

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# Azure Event Hub SDK (optional – falls back to simulated data)
try:
    from azure.eventhub import EventHubConsumerClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("[DEMO MODE] azure-eventhub not installed — using simulated data.")

load_dotenv()

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
EH_CONN_STR    = os.getenv("EVENT_HUB_CONNECTION_STRING", "")
EH_NAME        = os.getenv("EVENT_HUB_NAME", "")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "$Default")
MAX_POINTS     = 60   # data points to display per machine

THRESHOLDS = {
    "temperature": {"warn": 85.0, "crit": 92.0},
    "vibration":   {"warn": 0.50, "crit": 0.70},
    "power":       {"warn": 60.0, "crit": 68.0},
}

MACHINES = ["pump_01", "compressor_01", "reactor_01"]

# ──────────────────────────────────────────────
# In-memory telemetry store
# ──────────────────────────────────────────────
telemetry: dict[str, dict[str, deque]] = {
    m: {
        "temperature": deque(maxlen=MAX_POINTS),
        "vibration":   deque(maxlen=MAX_POINTS),
        "power":       deque(maxlen=MAX_POINTS),
        "timestamps":  deque(maxlen=MAX_POINTS),
    }
    for m in MACHINES
}
alerts: deque = deque(maxlen=20)
store_lock = threading.Lock()


# ──────────────────────────────────────────────
# Predictive maintenance logic
# ──────────────────────────────────────────────
def evaluate_rules(machine_id: str, payload: dict) -> str | None:
    """Return an alert string if any predictive rule fires, else None."""
    temp = payload.get("temperature", 0)
    vib  = payload.get("vibration", 0)
    pwr  = payload.get("power", 0)
    ts   = payload.get("timestamp", "")[:19]

    if temp > THRESHOLDS["temperature"]["crit"]:
        return f"🔴 CRITICAL [{ts}] {machine_id}: Temperature {temp:.1f}°C (>{THRESHOLDS['temperature']['crit']}°C)"
    if vib > THRESHOLDS["vibration"]["crit"]:
        return f"🔴 CRITICAL [{ts}] {machine_id}: Vibration {vib:.3f}g (>{THRESHOLDS['vibration']['crit']}g)"
    if pwr > THRESHOLDS["power"]["crit"]:
        return f"🔴 CRITICAL [{ts}] {machine_id}: Power {pwr:.1f}kW (>{THRESHOLDS['power']['crit']}kW)"

    # Trend rule: rising vibration over last 5 samples
    with store_lock:
        vib_hist = list(telemetry[machine_id]["vibration"])
    if len(vib_hist) >= 5 and all(
        vib_hist[i] < vib_hist[i + 1] for i in range(len(vib_hist) - 5, len(vib_hist) - 1)
    ):
        return f"🟡 MAINTENANCE [{ts}] {machine_id}: Sustained vibration increase detected"

    if temp > THRESHOLDS["temperature"]["warn"]:
        return f"🟡 WARNING [{ts}] {machine_id}: Temperature {temp:.1f}°C (>{THRESHOLDS['temperature']['warn']}°C)"

    return None


def ingest(payload: dict):
    """Store incoming telemetry and evaluate predictive rules."""
    machine_id = payload.get("machine_id")
    if machine_id not in MACHINES:
        return
    with store_lock:
        for key in ("temperature", "vibration", "power"):
            telemetry[machine_id][key].append(payload.get(key, 0))
        telemetry[machine_id]["timestamps"].append(
            datetime.now().strftime("%H:%M:%S")
        )
    alert = evaluate_rules(machine_id, payload)
    if alert:
        with store_lock:
            alerts.appendleft(alert)


# ──────────────────────────────────────────────
# Event Hub consumer thread
# ──────────────────────────────────────────────
def on_event(partition_context, event):
    try:
        payload = json.loads(event.body_as_str())
        ingest(payload)
        partition_context.update_checkpoint(event)
    except Exception as exc:
        print(f"[Event Hub] Parse error: {exc}")


def start_event_hub_consumer():
    if not (AZURE_AVAILABLE and EH_CONN_STR and EH_NAME):
        return
    client = EventHubConsumerClient.from_connection_string(
        EH_CONN_STR, consumer_group=CONSUMER_GROUP, eventhub_name=EH_NAME
    )
    with client:
        client.receive(on_event=on_event, starting_position="-1")


# ──────────────────────────────────────────────
# Demo data generator (when no Azure connection)
# ──────────────────────────────────────────────
_fault_start = time.time() + 60


def _demo_loop():
    configs = {
        "pump_01":       {"temp_base": 65, "vib_base": 0.35, "pwr_base": 45},
        "compressor_01": {"temp_base": 80, "vib_base": 0.55, "pwr_base": 60},
        "reactor_01":    {"temp_base": 90, "vib_base": 0.20, "pwr_base": 30},
    }
    while True:
        for mid, cfg in configs.items():
            factor = 1.0
            if mid == "compressor_01" and time.time() > _fault_start:
                factor = 1.0 + 0.003 * (time.time() - _fault_start)
            ingest({
                "machine_id":  mid,
                "temperature": round(cfg["temp_base"] * factor + random.gauss(0, 1.5), 2),
                "vibration":   round(cfg["vib_base"]  * factor + random.gauss(0, 0.02), 3),
                "power":       round(cfg["pwr_base"]          + random.gauss(0, 1.5), 2),
                "timestamp":   datetime.utcnow().isoformat(),
            })
        time.sleep(1)


# ──────────────────────────────────────────────
# Dash application
# ──────────────────────────────────────────────
COLORS = {"pump_01": "#1f77b4", "compressor_01": "#ff7f0e", "reactor_01": "#2ca02c"}

app = dash.Dash(__name__, title="Petrochemical Digital Twin")
app.layout = html.Div(
    style={"fontFamily": "Arial, sans-serif", "backgroundColor": "#0d1117", "color": "#e6edf3", "padding": "20px"},
    children=[
        html.H1("🏭 Petrochemical Plant Digital Twin",
                style={"textAlign": "center", "color": "#58a6ff"}),
        html.P("Real-time telemetry monitoring & predictive maintenance — Azure IoT Hub + Event Hub",
               style={"textAlign": "center", "color": "#8b949e"}),

        # Live graphs
        html.Div([
            dcc.Graph(id="temp-graph"),
            dcc.Graph(id="vib-graph"),
            dcc.Graph(id="power-graph"),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "12px"}),

        # Alert feed
        html.H3("⚠️ Active Alerts", style={"color": "#f0883e", "marginTop": "20px"}),
        html.Div(id="alert-feed",
                 style={"backgroundColor": "#161b22", "padding": "10px",
                        "borderRadius": "6px", "minHeight": "80px",
                        "fontFamily": "monospace", "fontSize": "13px"}),

        dcc.Interval(id="interval", interval=1500, n_intervals=0),
    ],
)


def _make_graph(metric: str, unit: str, warn_val: float, crit_val: float):
    fig = go.Figure()
    with store_lock:
        for mid in MACHINES:
            xs = list(telemetry[mid]["timestamps"])
            ys = list(telemetry[mid][metric])
            if xs:
                fig.add_trace(go.Scatter(
                    x=xs, y=ys, mode="lines", name=mid,
                    line={"color": COLORS[mid], "width": 2}
                ))
    fig.add_hline(y=warn_val, line_dash="dash", line_color="orange",
                  annotation_text="WARN", annotation_position="top right")
    fig.add_hline(y=crit_val, line_dash="dot",  line_color="red",
                  annotation_text="CRIT", annotation_position="bottom right")
    fig.update_layout(
        title=f"{metric.capitalize()} ({unit})",
        paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
        font={"color": "#e6edf3"}, legend={"bgcolor": "#0d1117"},
        margin={"t": 40, "b": 30, "l": 40, "r": 20},
        xaxis={"showgrid": False}, yaxis={"gridcolor": "#21262d"},
    )
    return fig


@app.callback(
    [Output("temp-graph",  "figure"),
     Output("vib-graph",   "figure"),
     Output("power-graph", "figure"),
     Output("alert-feed",  "children")],
    Input("interval", "n_intervals"),
)
def update_dashboard(_):
    temp_fig  = _make_graph("temperature", "°C",  THRESHOLDS["temperature"]["warn"], THRESHOLDS["temperature"]["crit"])
    vib_fig   = _make_graph("vibration",   "g",   THRESHOLDS["vibration"]["warn"],   THRESHOLDS["vibration"]["crit"])
    power_fig = _make_graph("power",       "kW",  THRESHOLDS["power"]["warn"],       THRESHOLDS["power"]["crit"])

    with store_lock:
        alert_lines = list(alerts)

    alert_content = (
        [html.P(a, style={"margin": "2px 0"}) for a in alert_lines]
        if alert_lines
        else [html.P("✅ All systems nominal", style={"color": "#3fb950"})]
    )
    return temp_fig, vib_fig, power_fig, alert_content


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if AZURE_AVAILABLE and EH_CONN_STR:
        t = threading.Thread(target=start_event_hub_consumer, daemon=True)
        t.start()
        print("[IoT Hub] Event Hub consumer started.")
    else:
        t = threading.Thread(target=_demo_loop, daemon=True)
        t.start()
        print("[DEMO] Simulated telemetry generator started.")

    app.run(debug=False, host="0.0.0.0", port=8050)
