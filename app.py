# app.py
import os
import threading
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from anomaly_detector import load_and_preprocess, group_power, fit_detector

# load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)
CORS(app)

# Configuration
xlsx_path = os.getenv("HOUSEHOLD_DATA_PATH", "household_power_consumption.xlsx")
data = load_and_preprocess(xlsx_path)

current_resolution = 'minute'
grouped_data = group_power(data, current_resolution)
model = fit_detector(grouped_data)

current_index = 0
index_lock = threading.Lock()

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/current_status", methods=["GET"])
def current_status():
    global current_resolution, grouped_data, model, current_index

    requested_resolution = request.args.get("resolution")
    if requested_resolution and requested_resolution != current_resolution:
        last_ts = None
        if grouped_data is not None and 0 <= current_index - 1 < len(grouped_data):
            last_ts = grouped_data.iloc[current_index - 1]['group']

        current_resolution = requested_resolution
        grouped_data = group_power(data, current_resolution)
        model = fit_detector(grouped_data)

        if last_ts is not None:
            inds = grouped_data[grouped_data['group'] >= last_ts].index
            current_index = int(inds[0]) if len(inds) > 0 else 0
        else:
            current_index = 0

    with index_lock:
        if current_index >= len(grouped_data):
            current_index = 0

        row = grouped_data.iloc[current_index]
        timestamp = row['group']
        power = row['total_power']

        df = pd.DataFrame({'total_power': [power]})
        pred = model.predict(df)[0]
        anomaly = bool(pred == -1)

        time_str = timestamp.strftime("%H:%M")
        date_str = timestamp.strftime("%d/%m/%Y")

        response = {
            "anomalyFound": anomaly,
            "time":         time_str,
            "date":         date_str,
            "latestPower":  round(power, 3),
            "status":       "Anomaly Detected!" if anomaly else "No Anomalies Detected!",
            "resolution":   current_resolution
        }

        current_index += 1

    return jsonify(response)

@app.route("/anomaly", methods=["GET"])
def anomaly_endpoint():
    return current_status()

@app.route("/insights", methods=["GET"])
def insights():
    global grouped_data, current_index
    # snapshot the index under lock, in case it’s advancing concurrently
    with index_lock:
        idx = current_index

    # Insight 2: last window delta (needs at least 2 points)
    if idx >= 2:
        last_val = grouped_data['total_power'].iat[idx - 1]
        prev_val = grouped_data['total_power'].iat[idx - 2]
        deltaKw  = round(last_val - prev_val, 3)
    else:
        deltaKw = 0.0

    # Insight 1: last 7 vs previous 7 (needs at least 14 points)
    if idx >= 14:
        last7 = grouped_data['total_power'].iloc[idx - 7 : idx].sum()
        prev7 = grouped_data['total_power'].iloc[idx - 14: idx - 7].sum()
        sevenPctChange = round(((last7 - prev7) / prev7) * 100, 1) if prev7 else 0.0
    else:
        sevenPctChange = 0.0

    return jsonify({
        "sevenPctChange": sevenPctChange,
        "deltaKw":        deltaKw
    })

@app.route("/tips", methods=["GET"])
def tips():
    # read in the two insight values the client just passed
    try:
        pct = float(request.args.get("sevenPctChange", 0))
        dk  = float(request.args.get("deltaKw",  0))
    except ValueError:
        pct, dk = 0.0, 0.0

    tips = []

    # if they got _better_ over last 7
    if pct < 0:
        tips.append("Nice work cutting your average use by "
                    f"{abs(pct):.1f}% — keep it up by scheduling your heating off 30 minutes earlier each evening.")

    else:
        tips.append("Your average use rose by "
                    f"{pct:.1f}% — try lowering your thermostat by 1°C during off‑peak hours.")

    # if current window demand jumped
    if dk > 0.5:
        tips.append("We saw a spike this period. Check if any high‑draw appliances (e.g. dryer) are still running.")

    elif dk < -0.2:
        tips.append("Good job smoothing out that spike — consider running washing/dishwashers in eco‑mode to save even more.")

    else:
        tips.append("Your usage held steady. Unused devices can still draw phantom power—try unplugging what you’re not using.")

    # always at least two
    if len(tips) < 2:
        tips.append("Try turning off any devices that are not currently in use.")

    return jsonify({"tips": tips})




if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
