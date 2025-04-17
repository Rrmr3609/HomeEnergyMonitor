import pandas as pd
from sklearn.ensemble import IsolationForest

def run_anomaly_detection():

    xlsx_path = "../household_power_consumption.xlsx"      #set the path to Excel file
    
    data = pd.read_excel(xlsx_path, na_values=['?'])   #read the Excel file; '?' marks missing values
    
    data.columns = data.columns.str.strip()    #clean column names by stripping extra whitespace
    
    #print columns and row count to ensure full dataset is loaded
    print("Columns:", data.columns.tolist())
    print("Total rows in dataset:", len(data))
    
    data['datetime'] = pd.to_datetime(data['Date'].astype(str) + ' ' + data['Time'].astype(str))   #combine the "Date" and "Time" columns into a datetime column
    
    #convert energy measurement columns to numeric
    numeric_cols = ['Global_active_power', 'Global_reactive_power', 
                    'Voltage', 'Global_intensity', 
                    'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    
    #compute total power using two methods:
    data['recorded_power'] = data['Global_active_power'] + data['Global_reactive_power']     #1. recorded_power - sum of Global_active_power and Global_reactive_power

    data['calc_power'] = (data['Voltage'] * data['Global_intensity']) / 1000.0       #2. calc_power - (Voltage * Global_intensity) / 1000 (in kW)

    data['total_power'] = (data['recorded_power'] + data['calc_power']) / 2.0       #average both measures for robustness
    
    #aggregate minute usage: truncate datetime to the minute and sum total_power per minute
    data['minute'] = data['datetime'].dt.floor('min')
    minute_power = data.groupby('minute')['total_power'].sum().reset_index()
    
    minute_power = minute_power.sort_values(by='minute').reset_index(drop=True)     #sort aggregated data to ensure chronological order
    
    #print the number of minute groups and last few rows
    print("Number of minute groups:", len(minute_power))
    print("Minute Aggregated Data (last 5 rows):")
    print(minute_power.tail())
    
    #set up IsolationForest with a 10% expected anomaly rate for increased sensitivity
    clf = IsolationForest(contamination=0.10, random_state=42)
    clf.fit(minute_power[['total_power']])
    
    #iterate through each minute and stop at first anomaly
    anomaly_found = False
    for idx, row in minute_power.iterrows():
        current_minute = row['minute']
        current_total = row['total_power']
        #use a DataFrame with the correct feature name to suppress warnings
        prediction = clf.predict(pd.DataFrame([[current_total]], columns=['total_power']))
        if prediction[0] == -1:
            print(f"Anomaly detected at {current_minute}: Total power = {current_total:.3f} kW")
            print("Status: Anomaly Detected!")
            print("Border color should be: red")
            anomaly_found = True
            break  #stop as soon as an anomaly is detected
    
    if not anomaly_found:
        print("No anomalies detected across the entire dataset.")
        print("Status: No Anomalies Detected!")
        print("Border color should be: green")

if __name__ == '__main__':
    run_anomaly_detection()
