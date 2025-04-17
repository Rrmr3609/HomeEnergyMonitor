# HomeEnergyMonitor

## Overview
A Flask + static‑HTML/CSS/JS app that visualizes household power consumption and flags anomalies.

## Features
- Real‑time charts at minute/30‑min/hour/day resolutions  
- ML‑powered anomaly detection via IsolationForest  
- Temperature animation, presets, historical data, tutorial buttons (stubbed)

## Quickstart

```bash
# 1. Clone & enter
git clone https://github.com/Rrmr3609/HomeEnergyMonitor.git
cd HomeEnergyMonitor

# 2. Python venv & dependencies
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 3. Run
python backend/app.py



### API

`GET /current_status?resolution=<minute|30min|hour|day>`

**Response**:
```json
{
  "status": "No Anomalies Detected!",
  "latestPower": 1.234,
  "time": "12:34",
  "date": "27/07/2025",
  "resolution": "minute"
}
