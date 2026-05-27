# 🏭 Petrochemical Plant Digital Twin — Azure Cloud

A cloud-native IoT monitoring and predictive maintenance platform for a petrochemical plant, built on Microsoft Azure.

> **Course:** CSE5634 – Cloud Computing | October University (MSA)  
> **Team:** Haneen Sherif · Mahmoud Farid · Fatma Amr · Hana Ebrahiem · Nada Mahmoud

---

## 📌 Project Overview

Petrochemical plants face unplanned downtime in critical assets — compressors, reactors, pumps, and heat exchangers. Failures cause production losses, safety hazards, and environmental risk.

This project implements a **secure, cloud-native digital twin** that:

- Streams telemetry from **virtual PLCs** (Python data generators simulating real sensors)
- Ingests data through **Azure IoT Hub** with SAS-token authentication
- Fans it out via **Azure Event Hub** to multiple consumers
- Displays live plant health and predictive maintenance alerts on a **Dash/Plotly dashboard**
- Deploys the dashboard to **Azure App Service** with GitHub Actions CI/CD

The architecture shifts maintenance teams from **reactive** to **predictive** strategies, reducing downtime and cost while providing a scalable reference that can later accept real sensors without redesigning the pipeline.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Edge / Data Generation                   │
│                                                                 │
│   publisher.py  (Virtual PLC)                                   │
│   └─ Generates: temperature · vibration · power (JSON)         │
│   └─ Authenticates via SAS token → TLS → Azure IoT Hub         │
└──────────────────────────────┬──────────────────────────────────┘
                               │ AMQP / MQTT / HTTPS
┌──────────────────────────────▼──────────────────────────────────┐
│                        Azure IoT Hub                            │
│   • Device registry & identity management                       │
│   • TLS termination                                             │
│   • Routes to built-in Event Hub-compatible endpoint            │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Event Hub-compatible endpoint
┌──────────────────────────────▼──────────────────────────────────┐
│                        Azure Event Hub                          │
│   • Partitioned, high-throughput streaming                      │
│   • 365-day telemetry retention (petrochemical standard)        │
│   • Multiple consumer groups (dashboard · analytics · ML)       │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Consumer group checkpoint
┌──────────────────────────────▼──────────────────────────────────┐
│                   Dash / Plotly Dashboard                       │
│   • Deserializes JSON telemetry                                 │
│   • Applies threshold + trend rules                             │
│   • Raises predictive maintenance alerts                        │
│   • Hosted on Azure App Service (Linux B1)                      │
│   • CI/CD via GitHub Actions                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## ☁️ Why Microsoft Azure?

| Feature | Azure | AWS |
|---|---|---|
| Digital Twins | Azure Digital Twins (semantic models) | AWS IoT TwinMaker |
| IoT Ingestion | **Azure IoT Hub** — bi-directional, device registry | AWS IoT Core |
| Streaming | **Azure Event Hub** — partitioned, high-throughput | Amazon Kinesis |
| OT / SCADA fit | **Excellent** — widely used in oil & gas | Strong but cloud-centric |
| Security | Managed identities, Key Vault | Fine-grained IAM |
| CI/CD | Azure DevOps, GitHub Actions | CodePipeline |

Azure's strong **OT/industrial alignment** and mature **Digital Twins service** make it the optimal choice for a petrochemical context.

---

## 💰 Cost Breakdown (~$32.71 / month)

| Resource | Tier | Est. Monthly |
|---|---|---|
| Azure App Service (Linux) | B1 | $12.41 |
| Azure IoT Hub | Basic B1 (400K msg/day) | $25.00 |
| Azure Storage Account | ZRS | $2.50 |
| Immutable Storage Policies | — | $0.50 |
| Azure Private Link | — | $7.30 |

> Economical for critical infrastructure at prototype / PoC scale.

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/petrochemical-digital-twin.git
cd petrochemical-digital-twin
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file (never commit this):

```env
IOTHUB_DEVICE_CONNECTION_STRING=HostName=<hub>.azure-devices.net;DeviceId=<id>;SharedAccessKey=<key>
EVENT_HUB_CONNECTION_STRING=Endpoint=sb://<namespace>.servicebus.windows.net/;...
EVENT_HUB_NAME=<hub-name>
CONSUMER_GROUP=$Default
```

### 4. Start the virtual PLC publisher

```bash
python publisher.py
```

### 5. Launch the dashboard locally

```bash
python dashboard.py
```

Open `http://localhost:8050` in your browser.

---

## 📁 Project Structure

```
petrochemical-digital-twin/
│
├── publisher.py            # Virtual PLC – generates & sends telemetry
├── dashboard.py            # Dash/Plotly app – consumes Event Hub & visualizes
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .github/
│   └── workflows/
│       └── deploy.yml      # GitHub Actions CI/CD → Azure App Service
└── README.md
```

---

## 🔧 Key Components

### `publisher.py` — Virtual PLC / Data Generator

Generates synthetic telemetry using Gaussian noise to mimic real sensor jitter:

```python
import random, json, time
from azure.iot.device import IoTHubDeviceClient, Message

MACHINES = ["pump_01", "compressor_01", "reactor_01"]

def generate_telemetry(machine_id):
    return {
        "machine_id":  machine_id,
        "temperature": round(random.gauss(75, 5), 2),   # °C
        "vibration":   round(random.gauss(0.4, 0.05), 3), # g
        "power":       round(random.gauss(50, 3), 2),   # kW
        "timestamp":   time.time()
    }
```

### `dashboard.py` — Dash/Plotly Real-time Dashboard

- Polls Event Hub via AMQP consumer group
- Deserializes JSON messages into Python objects
- Applies predictive rules (e.g., sustained vibration increase → maintenance alert)
- Renders live line charts per machine and metric

---

## 🔬 Predictive Maintenance Rules

| Rule | Condition | Action |
|---|---|---|
| High Temperature | `temp > 90°C` | 🔴 CRITICAL alert |
| Rising Vibration | Upward trend over 5 samples | 🟡 MAINTENANCE alert |
| Power Anomaly | `power > 65 kW` | 🟡 WARNING |
| Normal | All metrics in range | 🟢 HEALTHY |

---

## 🔒 Security

- Device authentication via **SAS tokens** (rotatable, per-device)
- Telemetry over **TLS 1.2**
- Secrets injected via **environment variables** — never hardcoded
- **Azure Private Link** isolates traffic from the public internet
- Future: migrate secrets to **Azure Key Vault**

---

## 🔄 Business Continuity

- **Decoupled streaming**: Event Hub buffers 365 days of data — dashboard restarts resume from checkpoint without data loss
- **Fault isolation**: IoT Hub and Event Hub continue ingesting even if the dashboard is down
- **Platform redundancy**: Azure Blob Storage backup + SLAs protect against single-point failures

---

## 📈 Digital Twin vs. Traditional SCADA

| Aspect | This Digital Twin | Traditional SCADA |
|---|---|---|
| Analytics | Predictive trend analysis | Reactive fixed thresholds |
| Scalability | Cloud-native, partitioned streams | Bound to on-prem hardware |
| Access | HTTPS from any browser | Local HMI / VPN required |
| Prototype cost | Virtual sensors + free-tier hosting | Hardware panels + licenses |
| Extensibility | Plug in ML, data lake, extra dashboards | Custom middleware required |

---

## 🚢 CI/CD Deployment

```yaml
# .github/workflows/deploy.yml (excerpt)
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - uses: azure/webapps-deploy@v2
        with:
          app-name: ${{ secrets.AZURE_WEBAPP_NAME }}
          publish-profile: ${{ secrets.AZURE_PUBLISH_PROFILE }}
```

---

## 🔮 Future Improvements

- Integrate **Azure Machine Learning** for advanced anomaly detection
- Add **Azure Data Explorer** for time-series querying
- Connect real PLC hardware (OPC-UA → IoT Edge → IoT Hub)
- Implement **Azure Digital Twins** semantic model for full asset graph
- Add **multi-site support** across refinery locations

---

## 📚 References

- Microsoft Azure IoT Hub Documentation — [docs.microsoft.com](https://docs.microsoft.com/azure/iot-hub/)
- Microsoft Azure Event Hub Documentation — [docs.microsoft.com](https://docs.microsoft.com/azure/event-hubs/)
- Plotly Dash Documentation — [dash.plotly.com](https://dash.plotly.com/)
- Azure App Service — [docs.microsoft.com](https://docs.microsoft.com/azure/app-service/)

---

## 📄 License

Academic project — October University / MSA, Fall 2025.
