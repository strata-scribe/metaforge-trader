import statistics
from typing import List, Union

class AnomalyDetector:
    def __init__(self, z_score_threshold: float = 3.0, iqr_multiplier: float = 1.5):
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier

    def detect_anomalies_z_score(self, prices: List[float]) -> List[bool]:
        """Detect anomalies using Z-score method."""
        if len(prices) < 2:
            return [False] * len(prices)

        try:
            mean = statistics.mean(prices)
            std_dev = statistics.stdev(prices)
        except statistics.StatisticsError:
            return [False] * len(prices)

        if std_dev == 0:
            return [False] * len(prices)

        anomalies = []
        for price in prices:
            z_score = (price - mean) / std_dev
            anomalies.append(abs(z_score) > self.z_score_threshold)

        return anomalies

    def detect_anomalies_iqr(self, prices: List[float]) -> List[bool]:
        """Detect anomalies using Interquartile Range (IQR) method."""
        if len(prices) < 4:
            # Not enough data for reliable quartiles
            return [False] * len(prices)

        try:
            quartiles = statistics.quantiles(prices, n=4, method='inclusive')
            q1 = quartiles[0]
            q3 = quartiles[2]
            iqr = q3 - q1
        except statistics.StatisticsError:
            return [False] * len(prices)

        lower_bound = q1 - self.iqr_multiplier * iqr
        upper_bound = q3 + self.iqr_multiplier * iqr

        anomalies = []
        for price in prices:
            anomalies.append(price < lower_bound or price > upper_bound)

        return anomalies

    def is_anomaly(self, price: float, historical_prices: List[float]) -> bool:
        """
        Determine if a price is an anomaly compared to historical prices.
        A price is considered an anomaly if both Z-score and IQR methods flag it.
        """
        all_prices = historical_prices + [price]

        z_score_anomalies = self.detect_anomalies_z_score(all_prices)
        iqr_anomalies = self.detect_anomalies_iqr(all_prices)

        # Check the last element which corresponds to the new price
        is_z_score_anomaly = z_score_anomalies[-1] if z_score_anomalies else False
        is_iqr_anomaly = iqr_anomalies[-1] if iqr_anomalies else False

        # Consider it an anomaly if either method flags it (flash crash could be picked up by one)
        # Actually IQR is often better for skewed data, Z-score is better for normal.
        # Let's say it's an anomaly if BOTH methods flag it, to be conservative, or EITHER if we want to be sensitive.
        # Let's use EITHER to ensure we catch flash crashes.
        return is_z_score_anomaly or is_iqr_anomaly
