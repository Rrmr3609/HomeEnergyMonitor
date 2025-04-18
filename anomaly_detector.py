# anomaly_detector.py
import pandas as pd
from sklearn.ensemble import IsolationForest


def load_and_preprocess(xlsx_path):
    """Load Excel data and preprocess for anomaly detection."""
    # Read the Excel file; '?' marks missing values
    data = pd.read_excel(xlsx_path, na_values=['?'])
    # Clean column names by stripping extra whitespace
    data.columns = data.columns.str.strip()
    # Combine the "Date" and "Time" columns into a datetime column
    data['datetime'] = pd.to_datetime(data['Date'].astype(str) + ' ' + data['Time'].astype(str))

    # Convert energy measurement columns to numeric
    numeric_cols = [
        'Global_active_power', 'Global_reactive_power',
        'Voltage', 'Global_intensity',
        'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
    ]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    # Compute total power using two methods and average them for robustness
    data['recorded_power'] = data['Global_active_power'] + data['Global_reactive_power']  # recorded_power
    data['calc_power'] = (data['Voltage'] * data['Global_intensity']) / 1000.0             # calc_power in kW
    data['total_power'] = (data['recorded_power'] + data['calc_power']) / 2.0               # average both measures

    return data


def group_power(data, resolution):
    """Group total_power by the chosen time resolution."""
    # Map resolution key to pandas frequency string
    freq_map = {
        'minute': 'min',
        '30min': '30T',
        'hour': 'H',
        'day': 'D'
    }
    freq = freq_map.get(resolution, 'T')
    # Truncate datetime to the chosen frequency and sum
    data['group'] = data['datetime'].dt.floor(freq)
    grouped = data.groupby('group')['total_power'].sum().reset_index()
    # Sort chronologically
    return grouped.sort_values(by='group').reset_index(drop=True)


def fit_detector(grouped_df):
    """Fit an IsolationForest on the grouped power data."""
    model = IsolationForest(contamination=0.10, random_state=42)
    model.fit(grouped_df[['total_power']])
    return model


def find_first_anomaly(grouped_df, model):
    """Iterate through grouped data to find the first anomaly."""
    for _, row in grouped_df.iterrows():
        # Use a DataFrame with correct feature name to suppress warnings
        prediction = model.predict(pd.DataFrame([[row['total_power']]], columns=['total_power']))
        if prediction[0] == -1:
            # Return timestamp and power of first detected anomaly
            return row['group'], row['total_power']
    return None, None


def run_anomaly_detection():
    """Standalone script for anomaly detection over the full dataset."""
    xlsx_path = "../household_power_consumption.xlsx"  # Path to Excel file
    data = load_and_preprocess(xlsx_path)

    # Aggregate minute usage
    data['minute'] = data['datetime'].dt.floor('min')
    minute_power = data.groupby('minute')['total_power'].sum().reset_index()
    minute_power = minute_power.sort_values(by='minute').reset_index(drop=True)

    # Debug prints
    print("Columns:", data.columns.tolist())
    print("Total rows in dataset:", len(data))
    print("Number of minute groups:", len(minute_power))
    print("Minute Aggregated Data (last 5 rows):")
    print(minute_power.tail())

    # Fit model and detect anomaly
    clf = fit_detector(minute_power)
    current_minute, current_total = find_first_anomaly(minute_power, clf)

    if current_minute is not None:
        print(f"Anomaly detected at {current_minute}: Total power = {current_total:.3f} kW")
        print("Status: Anomaly Detected!")
        print("Border color should be: red")
    else:
        print("No anomalies detected across the entire dataset.")
        print("Status: No Anomalies Detected!")
        print("Border color should be: green")


if __name__ == '__main__':
    run_anomaly_detection()