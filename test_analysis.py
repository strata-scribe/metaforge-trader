import pytest
from analysis import AnomalyDetector

@pytest.fixture
def detector():
    return AnomalyDetector(z_score_threshold=2.0, iqr_multiplier=1.5)

def test_detect_anomalies_z_score_normal(detector):
    prices = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3]
    anomalies = detector.detect_anomalies_z_score(prices)
    assert not any(anomalies)

def test_detect_anomalies_z_score_flash_crash(detector):
    # Mean will be ~10, stdev small. 2.0 is a clear outlier.
    prices = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3, 2.0]
    anomalies = detector.detect_anomalies_z_score(prices)
    # The last element should be an anomaly
    assert anomalies[-1] is True

def test_detect_anomalies_iqr_normal(detector):
    prices = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3]
    anomalies = detector.detect_anomalies_iqr(prices)
    assert not any(anomalies)

def test_detect_anomalies_iqr_flash_crash(detector):
    prices = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3, 1.0]
    anomalies = detector.detect_anomalies_iqr(prices)
    assert anomalies[-1] is True

def test_detect_anomalies_iqr_spike(detector):
    prices = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3, 25.0]
    anomalies = detector.detect_anomalies_iqr(prices)
    assert anomalies[-1] is True

def test_insufficient_data_z_score(detector):
    prices = [10.0]
    anomalies = detector.detect_anomalies_z_score(prices)
    assert anomalies == [False]

def test_insufficient_data_iqr(detector):
    prices = [10.0, 10.5, 9.8] # needs 4 for quantiles
    anomalies = detector.detect_anomalies_iqr(prices)
    assert anomalies == [False, False, False]

def test_zero_variance_z_score(detector):
    prices = [10.0, 10.0, 10.0, 10.0]
    anomalies = detector.detect_anomalies_z_score(prices)
    assert anomalies == [False, False, False, False]

def test_zero_variance_iqr(detector):
    prices = [10.0, 10.0, 10.0, 10.0]
    anomalies = detector.detect_anomalies_iqr(prices)
    assert anomalies == [False, False, False, False]

def test_is_anomaly(detector):
    historical = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3]
    assert not detector.is_anomaly(10.0, historical)
    assert detector.is_anomaly(1.0, historical)  # Flash crash
    assert detector.is_anomaly(30.0, historical) # Price spike
