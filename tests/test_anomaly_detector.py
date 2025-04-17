from backend.anomaly_detector import run_anomaly_detection
import pytest

def test_run_does_not_crash(capfd):
    # This will at least execute the function and print something
    run_anomaly_detection()
    captured = capfd.readouterr()
    assert "Anomaly" in captured.out or "No anomalies" in captured.out
