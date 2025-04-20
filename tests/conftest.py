import pytest
import pandas as pd
import app as app_module
import anomaly_detector as det
from app import create_app

#setting up the Flask app and sample data for testing
@pytest.fixture
def app():
    return create_app(test_config={})      #the Flask app instance configured for testing

@pytest.fixture
def sample_raw_df():
    #create a small DataFrame simulating raw power consumption data
    return pd.DataFrame({
        "Datetime": pd.to_datetime([
            "2025-01-01 00:00:00",
            "2025-01-01 00:01:00",
            "2025-01-01 00:02:00",
            "2025-01-01 00:03:00",
        ]),
        "Global_active_power": [1.0, 1.2, 5.0, 1.1]
    })

@pytest.fixture(autouse=True)
def patch_detector_and_app(monkeypatch, sample_raw_df):   #Monkeypatch the anomaly_detector module to use dummy functions instead of relying on real data

    #dummy load_and_preprocess, returning the sample DataFrame
    monkeypatch.setattr(
        det,
        'load_and_preprocess',
        lambda path: sample_raw_df.copy()
    )

    #dummy group_power, rename columns to match grouped_data format
    monkeypatch.setattr(
        det,
        'group_power',
        lambda df, res: df.rename(columns={
            'Datetime': 'group',
            'Global_active_power': 'total_power'
        })[['group','total_power']].reset_index(drop=True)
    )

    #dummy fit_detector, returns a model that flags total_power > 2.0 as anomalies
    class DummyModel:
        def predict(self, df):
            return [-1 if x > 2.0 else 1 for x in df['total_power']]

    monkeypatch.setattr(
        det,
        'fit_detector',
        lambda df: DummyModel()
    )

    #override the app's global variables so endpoints use the dummy data/model
    app_module.data = sample_raw_df.copy()
    app_module.current_resolution = 'minute'
    app_module.grouped_data = det.group_power(app_module.data, 'minute')
    app_module.model = det.fit_detector(app_module.grouped_data)
    app_module.current_index = 0
