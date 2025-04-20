import pandas as pd
import pytest
from datetime import datetime, timedelta
from anomaly_detector import group_power, fit_detector

def make_df():  #helper function to generate the DataFrame with hourly timestamps and power usage
    base = datetime(2025, 1, 1, 0, 0)
    times = [base + timedelta(hours=i) for i in range(4)]
    powers = [0.5, 0.7, 1.5, 2.5]
    return pd.DataFrame({
        'Datetime': times,
        'Global_active_power': powers
    })

def test_group_power_hourly_sum():     #test that group_power correctly groups data by hour and sums the Global_active_power values

    df = make_df()
    g = group_power(df, 'hour')
    #expect four rows, one for each hour
    assert len(g) == 4
    #each group's total_power should equal the original power value
    assert list(g['total_power']) == [0.5, 0.7, 1.5, 2.5]

def test_fit_detector_flags_anomalies():  #test that fit_detector returns a model which flags values above threshold (2.0) as anomalies (-1) and values below or equal to threshold as normal (1)
    #rename columns to match the expected input for fit_detector
    df = make_df().rename(columns={
        'Datetime': 'group',
        'Global_active_power': 'total_power'
    })
    model = fit_detector(df)

    #create a small test DataFrame with one normal and one anomalous value
    test = pd.DataFrame({'total_power': [0.6, 2.6]})
    preds = model.predict(test)

    #the model's predict method should return a list
    assert isinstance(preds, list)
    #0.6 → normal (1), 2.6 → anomaly (-1)
    assert preds[0] == 1
    assert preds[1] == -1
