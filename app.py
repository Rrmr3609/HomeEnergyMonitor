from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
from sklearn.ensemble import IsolationForest
import threading
from dotenv import load_dotenv
import os


load_dotenv()

app = Flask(
    __name__,
    static_folder="static",     
    static_url_path="/static"          # ← serve them at “/…”
)

CORS(app)  # Enable CORS for all routes

@app.route("/")
def index():
    return app.send_static_file("index.html")


# Load the dataset once (from your Excel file)
xlsx_path = os.getenv("HOUSEHOLD_DATA_PATH", "household_power_consumption.xlsx")
data = pd.read_excel(xlsx_path, na_values=['?'])
data.columns = data.columns.str.strip()
data['datetime'] = pd.to_datetime(data['Date'].astype(str) + ' ' + data['Time'].astype(str))

# Convert energy measurement columns to numeric
numeric_cols = ['Global_active_power', 'Global_reactive_power', 'Voltage', 
                'Global_intensity', 'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']
for col in numeric_cols:
    data[col] = pd.to_numeric(data[col], errors='coerce')

# Compute two measures of power and average them (instantaneous measurement in kW)
data['recorded_power'] = data['Global_active_power'] + data['Global_reactive_power']
data['calc_power'] = (data['Voltage'] * data['Global_intensity']) / 1000.0
data['total_power'] = (data['recorded_power'] + data['calc_power']) / 2.0

# Global variables for dynamic grouping
resolution_to_freq = {
    "minute": "T",    # Minute frequency
    "30min": "30T",   # 30 minutes frequency
    "hour": "H",      # Hourly frequency
    "day": "D"        # Daily frequency
}
current_resolution = "minute"  # Default resolution
grouped_data = None            # Will store the aggregated DataFrame
current_model = None           # IsolationForest model fitted on grouped_data
current_index = 0              # Pointer into the grouped data for simulation
index_lock = threading.Lock()

def update_grouping(resolution):
    """Update the grouped data and model based on the given resolution without resetting to the start if possible."""
    global grouped_data, current_model, current_index, current_resolution
    
    # Save current grouping timestamp if available
    last_timestamp = None
    if grouped_data is not None and current_index > 0:
        last_timestamp = grouped_data.iloc[current_index - 1]['group']
    
    # Determine frequency for grouping
    freq = resolution_to_freq.get(resolution, "T")
    # Create a new grouping column based on the chosen frequency
    data['group'] = data['datetime'].dt.floor(freq)
    new_grouped = data.groupby('group')['total_power'].sum().reset_index()
    new_grouped = new_grouped.sort_values(by='group').reset_index(drop=True)
    grouped_data = new_grouped

    # Fit IsolationForest on the new grouped data
    current_model = IsolationForest(contamination=0.10, random_state=42)
    current_model.fit(grouped_data[['total_power']])
    
    # Try to maintain the pointer by finding the first record with a group timestamp >= last_timestamp
    if last_timestamp is not None:
        indices = grouped_data[grouped_data['group'] >= last_timestamp].index
        if len(indices) > 0:
            current_index = int(indices[0])
        else:
            current_index = 0
    else:
        current_index = 0
    
    current_resolution = resolution
    print(f"Grouping updated to {resolution} ({freq}). Total groups: {len(grouped_data)}")

# Initialize with the default resolution
update_grouping("minute")

@app.route("/current_status", methods=["GET"])
def current_status():
    global current_index
    # Check if a resolution query parameter is provided and if it differs from the current setting
    requested_resolution = request.args.get("resolution")
    if requested_resolution and requested_resolution != current_resolution:
        update_grouping(requested_resolution)
    
    with index_lock:
        # Loop back to the beginning if we reach the end
        if current_index >= len(grouped_data):
            current_index = 0
        
        # Get the current grouped record
        row = grouped_data.iloc[current_index]
        current_group = row['group']
        current_total = row['total_power']
        
        # Check anomaly status using IsolationForest
        prediction = current_model.predict(pd.DataFrame([[current_total]], columns=['total_power']))
        anomaly = bool(prediction[0] == -1)
        
        # Format time and date based on the current grouping timestamp
        time_str = current_group.strftime("%H:%M")
        date_str = current_group.strftime("%d/%m/%Y")
        
        response = {
            "anomalyFound": anomaly,
            "hour": current_group.strftime("%Y-%m-%d %H:%M:%S"),  # For backward compatibility
            "time": time_str,
            "date": date_str,
            "latestPower": round(current_total, 3),
            "status": "Anomaly Detected!" if anomaly else "No Anomalies Detected!",
            "borderColor": "red" if anomaly else "green",
            "resolution": current_resolution  # Return current resolution to let the frontend update labels
        }
        current_index += 1  # Move pointer to the next record for subsequent requests
    return jsonify(response)

@app.route("/anomaly", methods=["GET"])
def anomaly_endpoint():
    return current_status()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
