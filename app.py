import os
import threading
import requests
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from anomaly_detector import load_and_preprocess, group_power, fit_detector

#load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

#env variables of the Telegram bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)
CORS(app)

#configuration
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

def send_telegram(msg: str):     #function that enables the anomaly messafe to be sent
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       msg,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        app.logger.error("Telegram send failed: %s", e)


@app.route("/current_status", methods=["GET"])
def current_status():
    global current_resolution, grouped_data, model, current_index

    #handle resolution switch if requested
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
        #wrap the index if it exceeds the dataset length
        if current_index >= len(grouped_data):
            current_index = 0

        row = grouped_data.iloc[current_index]
        timestamp = row['group']
        power = row['total_power']

        #perform anomaly prediction
        df = pd.DataFrame({'total_power': [power]})
        pred = model.predict(df)[0]
        anomaly = bool(pred == -1)

        #format time and force year to 2025
        time_str = timestamp.strftime("%H:%M")
        date_str = timestamp.strftime("%d/%m") + "/2025"

        response = {
            "anomalyFound": anomaly,
            "time":         time_str,
            "date":         date_str,
            "latestPower":  round(power, 3),
            "status":       "Anomaly Detected!" if anomaly else "No Anomalies Detected!",
            "resolution":   current_resolution
        }

        current_index += 1   #advance index for next call

        #if anomaly, compute insights & send Telegram
        if response["anomalyFound"]:
            idx = current_index - 1  #index of this anomaly

            #Insight 2 - deltaKw
            if idx >= 1:
                last_val = grouped_data['total_power'].iat[idx]
                prev_val = grouped_data['total_power'].iat[idx - 1]
                deltaKw  = round(last_val - prev_val, 3)
            else:
                deltaKw = 0.0

            #Insight 1 - sevenPctChange
            if idx >= 14:
                last7 = grouped_data['total_power'].iloc[idx-6:idx+1].sum()
                prev7 = grouped_data['total_power'].iloc[idx-13:idx-6].sum()
                sevenPctChange = round(((last7 - prev7) / prev7) * 100, 1) if prev7 else 0.0
            else:
                sevenPctChange = 0.0

            #build personalised tips
            tips = []
            if sevenPctChange < 0:
                tips.append(
                    f"Nice work cutting your average usage by {abs(sevenPctChange):.1f}% — "
                    "keep it up by scheduling your heating off 30 minutes earlier each evening."
                )
            else:
                tips.append(
                    f"Your average usage rose by {sevenPctChange:.1f}% — "
                    "try lowering your thermostat by 1°C during off‑peak hours."
                )

            if deltaKw > 0.5:
                tips.append("We saw a spike this period. Check if any high‑draw appliances (e.g. dryer) are still running.")
            elif deltaKw < -0.2:
                tips.append("Good job smoothing out that spike in usage — consider running washing/dishwashers in eco‑mode to save even more.")
            else:
                tips.append("Your usage is steady. Unused devices can still draw phantom power. Try unplugging what you’re not using.")

            if len(tips) < 2:
                tips.append("Try turning off any devices that are not currently in use.")

            #format and send the Telegram message
            msg = (
                f"⚠️ *Anomaly Detected!* ⚠️\n\n"
                f"*When:* {date_str} {time_str}\n"
                f"*Power:* {response['latestPower']} kW\n\n"
                f"*Insights:*\n"
                f"• 7‑period Δ: {sevenPctChange:.1f}%\n"
                f"• Last‑window Δ: {deltaKw:.3f} kW\n\n"
                f"*Tips:* \n"
            )
            for t in tips:
                msg += f"• {t}\n"

            send_telegram(msg)

    return jsonify(response)


@app.route("/anomaly", methods=["GET"])
def anomaly_endpoint():
    return current_status()


@app.route("/insights", methods=["GET"])
def insights():
    global grouped_data, current_index
    with index_lock:
        idx = current_index

    #Insight 2 - last window delta
    if idx >= 2:
        last_val = grouped_data['total_power'].iat[idx - 1]
        prev_val = grouped_data['total_power'].iat[idx - 2]
        deltaKw  = round(last_val - prev_val, 3)
    else:
        deltaKw = 0.0

    #Insight 1 - last 7 vs previous 7
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
    #read the two insight values passed by the client
    try:
        pct = float(request.args.get("sevenPctChange", 0))
        dk  = float(request.args.get("deltaKw",  0))
    except ValueError:
        pct, dk = 0.0, 0.0

    tips = []

    if pct < 0:
        tips.append(
            "Nice work cutting your average use by "
            f"{abs(pct):.1f}% — keep it up by scheduling your heating off 30 minutes earlier each evening."
        )
    else:
        tips.append(
            "Your average usage rose by "
            f"{pct:.1f}% — try lowering your thermostat by 1°C during off‑peak hours."
        )

    if dk > 0.5:
        tips.append("We saw a spike this period. Check if any high‑draw appliances (e.g. dryer) are still running.")
    elif dk < -0.2:
        tips.append("Good job smoothing out that spike in usage — consider running washing/dishwashers in eco‑mode to save even more.")
    else:
        tips.append("Your usage is steady. Unused devices can still draw phantom power. Try unplugging what you’re not using.")

    if len(tips) < 2:
        tips.append("Try turning off any devices that are not currently in use.")

    return jsonify({"tips": tips})


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
