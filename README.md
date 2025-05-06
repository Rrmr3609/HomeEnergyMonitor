# Home Energy Monitor

A lightweight web app built with Flask and vanilla JS that visualises household energy usage and detects anomalies in real time.

---

## Table of Contents

1. [Features](#features)  
2. [Prerequisites](#prerequisites)  
3. [Configuration](#configuration)  
4. [Telegram Alerts Setup](#telegram-alerts-setup)
5. [Quickstart](#quickstart)  
6. [Testing](#testing)
7. [File Overview](#file-overview)  

---

## Features

- **Real‑time line charts** at minute / 30‑min / hourly / daily resolutions  
- **Anomaly detection** powered by `IsolationForest` (10% contamination)  
- **Temperature animation** and target‑adjust controls  
- **Responsive** CSS layout  
- **Telegram alerts** with real-time anomaly insights
- **Interactive tutorial** (via Intro.js)
---

## Prerequisites

- **Python 3.8+**  
- [pip](https://pip.pypa.io/)  
- A copy of the [Household Power Consumption dataset](https://www.kaggle.com/datasets/thedevastator/240000-household-electricity-consumption-records/data) in `.xlsx` form  
- Credits to Georges Hébrail and Alice Bérard, the original authors of the dataset that is being utilised.
---

## Configuration

1. Place the dataset into the project root (next to `app.py`) **or** point to it via an environment variable:

   ```bash
   # macOS/Linux
   export HOUSEHOLD_DATA_PATH="/full/path/to/household_power_consumption.xlsx"

   # Windows PowerShell
   $env:HOUSEHOLD_DATA_PATH="C:\path\to\household_power_consumption.xlsx"


2. The app will fall back to ./household_power_consumption.xlsx if HOUSEHOLD_DATA_PATH is not set.

---

## Telegram Alerts Setup

1. Create a Telgram Bot

- Download and open Telegram and search for @BotFather
- Run /newbot, follow the prompts and save the bot token it gives you

2. Obtain your chat ID

- Start a chat with your new bot
- In your broswer url space type - https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
- Send a message to your bot, then refresh the page to find your chat.id within the given JSON response

3. Set up your environment variables
- Create a .env file in the project root with the following:
     
    TELEGRAM_BOT_TOKEN=your_bot_token_here
    TELEGRAM_CHAT_ID=your_chat_id_here

---

## Quickstart

### 1. Clone & enter
git clone https://github.com/Rrmr3609/HomeEnergyMonitor.git
cd HomeEnergyMonitor

### 2. Create & activate virtual environment
python3 -m venv venv

### macOS / Linux
source venv/bin/activate

### Windows (cmd.exe)
venv\Scripts\activate.bat

### 3. Install dependencies
pip install -r requirements.txt

### 4. (Optional) Set dataset path if not in project root
export HOUSEHOLD_DATA_PATH="/absolute/path/to/household_power_consumption.xlsx"

### 5. Launch the server
python app.py

### 6. Open in browser
http://127.0.0.1:5000

---

## Testing

1. Open terminal
2. Go to project root directory
3. Do 'python -m pytest -s'
4. Happy Testing!

---

## File Overview

app.py — Loads the dataset, manages time-slice grouping, fits the IsolationForest model, and serves both the static UI and the JSON API

anomaly_detector.py — Encapsulates preprocessing and ML logic, allowing independent testing

static/index.html — The single-page frontend UI; references /static/style.css and /static/main.js

tests/ — Contains pytest files to verify API functionality and model behavior