import os
import threading
import requests
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from anomaly_detector import load_and_preprocess, group_power, fit_detector

#load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

#retrieve Telegram bot credentials from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

#initialise Flask app
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)
CORS(app)  #enable CORS

xlsx_path = os.getenv("HOUSEHOLD_DATA_PATH", "household_power_consumption.xlsx")  #path to the household power consumption Excel file (configurable via env)

data = load_and_preprocess(xlsx_path)  #load and preprocess the raw data upon startup

#group by minute and fit anomaly detection model
current_resolution = 'minute'
grouped_data = group_power(data, current_resolution)
model = fit_detector(grouped_data)

#track the current index in the grouped data for polling
current_index = 0  
index_lock = threading.Lock()  

@app.route("/")
def index():
    return app.send_static_file("index.html")  #serve the main HTML page

def send_telegram(msg: str):   #function to send a message via Telegram bot
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID")
    #only do if both token and chat ID are set
    if not (bot_token and chat_id):
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       msg,
        "parse_mode": "Markdown"  #use Markdown for text formatting
    }
    try:
        #send the HTTP POST to Telegram
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        app.logger.error("Telegram send failed: %s", e)


@app.route("/current_status", methods=["GET"])    #polling endpoint for the latest aggregated power usage, returns JSON with timestamp, power, anomaly status, and optional Telegram notification
def current_status():
    global current_resolution, grouped_data, model, current_index

    #handle resolution change if requested
    requested_resolution = request.args.get("resolution")
    if requested_resolution and requested_resolution != current_resolution:
        last_ts = None
        #save the timestamp of the last retrieved data point
        if grouped_data is not None and 0 <= current_index - 1 < len(grouped_data):
            last_ts = grouped_data.iloc[current_index - 1]['group']

        #update grouping and model
        current_resolution = requested_resolution
        grouped_data = group_power(data, current_resolution)
        model = fit_detector(grouped_data)

        #find the new index corresponding to the previously used timestamp
        if last_ts is not None:
            inds = grouped_data[grouped_data['group'] >= last_ts].index
            current_index = int(inds[0]) if len(inds) > 0 else 0
        else:
            current_index = 0

    with index_lock:
        #loop back to start if end is reached
        if current_index >= len(grouped_data):
            current_index = 0

        #extract the current data point
        row = grouped_data.iloc[current_index]
        timestamp = row['group']
        power = row['total_power']

        #prepare a DataFrame for the model prediction
        df = pd.DataFrame({'total_power': [power]})
        pred = model.predict(df)[0]
        anomaly = bool(pred == -1)

        #format date and time strings
        time_str = timestamp.strftime("%H:%M")
        date_str = timestamp.strftime("%d/%m") + "/2025"

        #build the base JSON response
        response = {
            "anomalyFound": anomaly,
            "time":         time_str,
            "date":         date_str,
            "latestPower":  round(power, 3),
            "status":       "Anomaly Detected!" if anomaly else "No Anomalies Detected!",
            "resolution":   current_resolution
        }

        current_index += 1  #move to the next data point for subsequent polls

        #if anomaly detected, compute deltas, insights, tips, and notify Telegram
        if response["anomalyFound"]:
            idx = current_index - 1

            #compute deltaKw vs previous period
            if idx >= 1:
                last_val = grouped_data['total_power'].iat[idx]
                prev_val = grouped_data['total_power'].iat[idx - 1]
                deltaKw  = round(last_val - prev_val, 3)
            else:
                deltaKw = 0.0

            #compute seven period percentage change if enough data available
            if idx >= 14:
                last7 = grouped_data['total_power'].iloc[idx-6:idx+1].sum()
                prev7 = grouped_data['total_power'].iloc[idx-13:idx-6].sum()
                sevenPctChange = round(((last7 - prev7) / prev7) * 100, 1) if prev7 else 0.0
            else:
                sevenPctChange = 0.0

            tips = []
            #default placeholder tips when insufficient insight data
            if sevenPctChange == 0.0 and deltaKw == 0.0:
                tips.append(
                    "Gathering data on your usage - more detailed insights will appear "
                    "once we have a full week of readings."
                )
                tips.append(
                    "Your usage is steady. Unused devices can still draw phantom power. "
                    "Try unplugging what you're not using."
                )
            else:
                #personalised tips based on computed metrics
                if sevenPctChange < 0:
                    tips.append(
                        f"Nice work cutting your average usage by {abs(sevenPctChange):.1f}% - "
                        "keep it up by scheduling your heating off 30 minutes earlier each evening."
                    )
                else:
                    tips.append(
                        f"Your average usage rose by {sevenPctChange:.1f}% - "
                        "try lowering your thermostat by 1°C during off-peak hours."
                    )

                if deltaKw > 0.5:
                    tips.append(
                        "We saw a spike this period. Check if any high-draw appliances (e.g. dryer) are still running."
                    )
                elif deltaKw < -0.2:
                    tips.append(
                        "Good job smoothing out that spike in usage - consider running washing/dishwashers "
                        "in eco-mode to save even more."
                    )
                else:
                    tips.append(
                        "Your usage is steady. Unused devices can still draw phantom power. "
                        "Try unplugging what you're not using."
                    )

            #ensure at least two tips
            if len(tips) < 2:
                tips.append("Try turning off any devices that are not currently in use.")

            #prepare insight lines for Telegram message
            insight_lines = []
            if sevenPctChange != 0.0:
                insight_lines.append(f"• 7-period Δ: {sevenPctChange:.1f}%")
            insight_lines.append(f"• Last-window Δ: {deltaKw:.3f} kW")

            #cleanup placeholder tips if no real insight
            if sevenPctChange == 0.0 and tips:
                tips.pop(0)

            #construct the alert message
            msg = (
                "⚠️ *Anomaly Detected!* ⚠️\n\n"
                f"*When:* {date_str} {time_str}\n"
                f"*Power:* {response['latestPower']} kW\n\n"
                "*Insights:*\n"
            )
            for line in insight_lines:
                msg += line + "\n"

            msg += "\n*Tips:*\n"
            for t in tips:
                msg += f"• {t}\n"

            send_telegram(msg)  #send the alert to Telegram bot

    #return JSON response to client
    return jsonify(response)

@app.route("/anomaly", methods=["GET"])    #alias endpoint to step back one index and return the previous status, useful for UI "back" behavior on detection
def anomaly_endpoint():
    global current_index
    with index_lock:
        if current_index > 0:
            current_index -= 1
    return current_status()

@app.route("/insights", methods=["GET"])   #returns a JSON payload with seven period percentage change and delta kW, used for chart annotations and summary
def insights():
    global grouped_data, current_index
    with index_lock:
        idx = current_index

    #compute deltaKw vs one period ago
    if idx >= 2:
        last_val = grouped_data['total_power'].iat[idx - 1]
        prev_val = grouped_data['total_power'].iat[idx - 2]
        deltaKw  = round(last_val - prev_val, 3)
    else:
        deltaKw = 0.0

    #compute seven period percentage change if enough data
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
def tips():   #returns JSON array of tips based on query params "sevenPctChange" and "deltaKw", falls back to default guidance if not enough data
    try:
        pct = float(request.args.get("sevenPctChange", 0))
        dk  = float(request.args.get("deltaKw",  0))
    except ValueError:
        pct, dk = 0.0, 0.0

    #default tips when no real data
    if pct == 0.0 and dk == 0.0:
        return jsonify({
            "tips": [
                "Gathering data on your usage - more detailed insights will appear once we have a full week of readings.",
                "Your usage is steady. Unused devices can still draw phantom power. Try unplugging what you're not using."
            ]
        })

    tips = []
    #compose personalised tips
    if pct < 0:
        tips.append(
            "Nice work cutting your average use by "
            f"{abs(pct):.1f}% - keep it up by scheduling your heating off 30 minutes earlier each evening."
        )
    else:
        tips.append(
            "Your average usage rose by "
            f"{pct:.1f}% — try lowering your thermostat by 1°C during off-peak hours."
        )

    if dk > 0.5:
        tips.append("We saw a spike this period. Check if any high-draw appliances (e.g. dryer) are still running.")
    elif dk < -0.2:
        tips.append("Good job smoothing out that spike in usage - consider running washing/dishwashers in eco-mode to save even more.")
    else:
        tips.append("Your usage is steady. Unused devices can still draw phantom power. Try unplugging what you're not using.")

    #ensure at least two tips
    if len(tips) < 2:
        tips.append("Try turning off any devices that are not currently in use.")

    return jsonify({"tips": tips})

#method for tests to create the Flask app instance
def create_app(test_config=None):
    return app

if __name__ == '__main__':
    #fun the Flask server
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
