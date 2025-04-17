# Home Energy Monitor

A **Flask** + plain‑HTML/CSS/JS single‑page app that visualises household power consumption and flags anomalies in real time

---

## Table of Contents

1. [Features](#features)  
2. [Prerequisites](#prerequisites)  
3. [Configuration](#configuration)  
4. [Quickstart](#quickstart)  
5. [API](#api)  
6. [Project Structure](#project-structure)  

---

## Features

- **Real‑time line charts** at minute / 30‑min / hourly / daily resolutions  
- **Anomaly detection** powered by `IsolationForest` (10% contamination)  
- **Temperature animation** and target‑adjust controls  
- Stubbed buttons for presets, history, tutorials  
- Responsive CSS layout  

---

## Prerequisites

- **Python 3.8+**  
- [pip](https://pip.pypa.io/)  
- A copy of the [Household Power Consumption dataset](https://archive.ics.uci.edu/ml/datasets/individual+household+electric+power+consumption) in `.xlsx` or `.csv` form  

---

## Configuration

1. Place dataset into the project root (next to `app.py`) **or** point to it via an env var:

   ```bash
   # macOS/Linux
   export HOUSEHOLD_DATA_PATH="/full/path/to/household_power_consumption.xlsx"

   # Windows PowerShell
   $env:HOUSEHOLD_DATA_PATH="C:\path\to\household_power_consumption.xlsx"

2. The app will fall back to ./household_power_consumption.xlsx if HOUSEHOLD_DATA_PATH is not set

---

## Quickstart

# 1. Clone & enter
git clone https://github.com/Rrmr3609/HomeEnergyMonitor.git
cd HomeEnergyMonitor

# 2. Create & activate virtual‑env
python3 -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows (cmd.exe)
venv\Scripts\activate.bat

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Set dataset path if not in project root
export HOUSEHOLD_DATA_PATH="/absolute/path/to/household_power_consumption.xlsx"

# 5. Launch the server
python app.py

# 6. Open in browser
http://localhost:5000

---

## API

`GET /current_status?resolution=<minute|30min|hour|day>`

Returns the next simulated time-slice, runs anomaly check, and returns:

**Response**:
json
{
  "status": "No Anomalies Detected!",
  "latestPower": 1.234,
  "time": "12:34",
  "date": "27/07/2025",
  "resolution": "minute"
}

status - Either "Anomaly Detected!" or "No Anomalies Detected!"

latestPower - Aggregated total_power for that time slice

time, date - Formatted timestamp

resolution - The selected sampling frequency

---

## Project Structure

HomeEnergyMonitor/
├── app.py                         # Flask server: routes, grouping & anomaly‑check logic
├── anomaly_detector.py           # Standalone ML logic for IsolationForest training & prediction
├── requirements.txt               # Pinned Python dependencies
├── household_power_consumption.xlsx (or .csv)
├── static/                        # All front‑end assets, served at /static/...
│   ├── index.html                 # Single‑page UI (no templates/ folder)
│   ├── style.css                  # Main stylesheet
│   ├── main.js                    # Front‑end logic (Chart.js, AJAX polling, UI updates)
│   └── img/                       # SVG icons (battery, thermostat, etc.)
└── tests/                         # Unit tests
    ├── test_app.py                # Tests for Flask endpoints
    └── test_anomaly_detector.py   # Tests for your isolation forest logic


app.py - Loads the dataset, updates time‑slice grouping, fits the IsolationForest, and serves both the static UI and the JSON API

anomaly_detector.py - Encapsulates the data‑processing & model code (so you can import/test it separately)

static/index.html - Bootstraps the single‑page UI; references /static/style.css and /static/main.js

tests/ - Holds pytest files to verify server responses and anomaly‑detector functionality
