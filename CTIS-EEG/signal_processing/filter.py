import numpy as np
from scipy.signal import butter, lfilter, iirnotch

from config import SAMPLING_RATE, FILTER_LOWCUT, FILTER_HIGHCUT, FILTER_ORDER


class RealtimeFilter:
    """因果 IIR 带通滤波器，支持逐样本实时处理"""

    def __init__(self, lowcut=FILTER_LOWCUT, highcut=FILTER_HIGHCUT,
                 fs=SAMPLING_RATE, order=FILTER_ORDER):
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        self.b, self.a = butter(order, [low, high], btype="band")
        self.zi = np.zeros(max(len(self.a), len(self.b)) - 1)

    def process_sample(self, x: float) -> float:
        y, self.zi = lfilter(self.b, self.a, [x], zi=self.zi)
        return float(y[0])

    def process_batch(self, x: np.ndarray) -> np.ndarray:
        y, self.zi = lfilter(self.b, self.a, x, zi=self.zi)
        return y

    def reset(self):
        self.zi = np.zeros(max(len(self.a), len(self.b)) - 1)


class NotchFilter:
    """50Hz 工频陷波 (中国地区)"""

    def __init__(self, freq=50.0, fs=SAMPLING_RATE, Q=30.0):
        self.b, self.a = iirnotch(freq, Q, fs)
        self.zi = np.zeros(max(len(self.a), len(self.b)) - 1)

    def process_sample(self, x: float) -> float:
        y, self.zi = lfilter(self.b, self.a, [x], zi=self.zi)
        return float(y[0])

    def reset(self):
        self.zi = np.zeros(max(len(self.a), len(self.b)) - 1)
