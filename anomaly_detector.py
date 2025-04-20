import pandas as pd
from sklearn.ensemble import IsolationForest

def load_and_preprocess(xlsx_path):

    data = pd.read_excel(xlsx_path, na_values=['?']) #read the Excel file; '?' marks missing values
    
    data.columns = data.columns.str.strip() #clean column names by stripping extra whitespace

    data['datetime'] = pd.to_datetime(data['Date'].astype(str) + ' ' + data['Time'].astype(str))  #combine the "Date" and "Time" columns into a datetime column

    #convert energy measurement columns to numeric
    numeric_cols = [
        'Global_active_power', 'Global_reactive_power',
        'Voltage', 'Global_intensity',
        'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3'
    ]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    #compute total power using two methods and average them for robustness
    data['recorded_power'] = data['Global_active_power'] + data['Global_reactive_power']  #recorded_power
    data['calc_power'] = (data['Voltage'] * data['Global_intensity']) / 1000.0             #calc_power in kW
    data['total_power'] = (data['recorded_power'] + data['calc_power']) / 2.0               #average both measures

    return data

def group_power(data, resolution):   #group total_power by the chosen time resolution, supporting both real and test DataFrames
    df = data.copy()

    #find or build a datetime column
    if 'datetime' not in df.columns:
        if 'Datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['Datetime'])
        else:
            raise KeyError("No 'datetime' or 'Datetime' column found")

    #find or build a total_power column
    if 'total_power' not in df.columns:
        if 'Global_active_power' in df.columns:
            df['total_power'] = df['Global_active_power']
        else:
            raise KeyError("No 'total_power' or 'Global_active_power' column found")

    #map resolution to pandas freq
    freq_map = {'minute': 'min', '30min': '30T', 'hour': 'h', 'day': 'D'}
    freq = freq_map.get(resolution, 'T')

    #floor to that period and group the sum
    df['group'] = df['datetime'].dt.floor(freq)
    grouped = df.groupby('group')['total_power'].sum().reset_index()

    return grouped.sort_values('group').reset_index(drop=True)


def fit_detector(grouped_df):         #fit an IsolationForest on the grouped power data
    model = IsolationForest(contamination=0.10, random_state=42)
    model.fit(grouped_df[['total_power']])
    orig_predict = model.predict
    model.predict = lambda df: orig_predict(df).tolist()
    return model

def find_first_anomaly(grouped_df, model):   #iterate through grouped data to find the first anomaly
    for _, row in grouped_df.iterrows():
        #use a DataFrame with correct feature name to suppress warnings
        prediction = model.predict(pd.DataFrame([[row['total_power']]], columns=['total_power']))
        if prediction[0] == -1:
            #return timestamp and power of first detected anomaly
            return row['group'], row['total_power']
    return None, None

def run_anomaly_detection():             #standalone script for anomaly detection over the full dataset
    xlsx_path = "../household_power_consumption.xlsx"  #path to Excel file
    data = load_and_preprocess(xlsx_path)

    #aggregate minute usage
    data['minute'] = data['datetime'].dt.floor('min')
    minute_power = data.groupby('minute')['total_power'].sum().reset_index()
    minute_power = minute_power.sort_values(by='minute').reset_index(drop=True)

    #debug prints
    print("Columns:", data.columns.tolist())
    print("Total rows in dataset:", len(data))
    print("Number of minute groups:", len(minute_power))
    print("Minute Aggregated Data (last 5 rows):")
    print(minute_power.tail())

    #fit model and detect anomaly
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