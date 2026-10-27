import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

import numpy as np

from config import SAMPLING_RATE, BLINK_MIN_INTERVAL_MS
from signal_processing.filter import RealtimeFilter


class IntentLevel(Enum):
    WEAK = 1
    MEDIUM = 2
    STRONG = 3
    NONE = 0


@dataclass
class BlinkEvent:
    timestamp_ms: int
    amplitude_uv: float
    intent: IntentLevel
    raw_peak_index: int


class BlinkDetector:
    """
    基于幅值阈值的有意眨眼检测器
    支持在线校准以确定个体化弱/中/强阈值
    """

    def __init__(self, fs: int = SAMPLING_RATE):
        self.fs = fs
        self.filter = RealtimeFilter()
        self._window_samples = int(0.5 * fs)   # 500ms 滑动窗
        self._min_interval_samples = int(BLINK_MIN_INTERVAL_MS / 1000.0 * fs)
        self._recent = []
        self._last_blink_idx = -self._min_interval_samples
        self._sample_counter = 0

        # 阈值 (通过 calibrate 确定)
        self.base_threshold = 50.0   # 基础检测阈值 (uV)
        self.mid_threshold = 100.0   # 弱→中分界
        self.strong_threshold = 180.0  # 中→强分界

        # 回调
        self.on_blink: Optional[Callable[[BlinkEvent], None]] = None

    # -------------------- 实时处理 --------------------
    def feed(self, raw_uv: float) -> Optional[BlinkEvent]:
        """逐样本输入，若检测到眨眼则返回 BlinkEvent"""
        filt = self.filter.process_sample(raw_uv)
        self._recent.append(filt)
        idx = self._sample_counter
        self._sample_counter += 1

        if len(self._recent) > self._window_samples:
            self._recent.pop(0)

        # 消抖: 距离上次眨眼必须足够远
        if idx - self._last_blink_idx < self._min_interval_samples:
            return None

        # 检测局部负向极值 (眨眼在 Fp1 常为负向尖峰)
        if len(self._recent) < self._window_samples:
            return None

        # 取窗口中心点
        center = self._window_samples // 2
        center_val = self._recent[center]

        # 极值条件: 中心点为窗口最小值，且绝对值超过阈值
        if center_val < -self.base_threshold:
            if center_val == min(self._recent):
                amp = abs(center_val)
                intent = self._classify(amp)
                self._last_blink_idx = idx
                evt = BlinkEvent(
                    timestamp_ms=int(time.time() * 1000),
                    amplitude_uv=round(amp, 2),
                    intent=intent,
                    raw_peak_index=idx,
                )
                if self.on_blink:
                    self.on_blink(evt)
                return evt
        return None

    def feed_batch(self, arr: np.ndarray) -> List[BlinkEvent]:
        """批量处理 (用于离线分析)"""
        evts = []
        for x in arr:
            e = self.feed(float(x))
            if e:
                evts.append(e)
        return evts

    def reset(self):
        self.filter.reset()
        self._recent.clear()
        self._sample_counter = 0
        self._last_blink_idx = -self._min_interval_samples

    # -------------------- 校准 --------------------
    def calibrate(self, calibration_segments: dict) -> dict:
        """
        根据校准数据计算个体化阈值
        calibration_segments: {"spontaneous": ndarray, "weak": ndarray,
                               "medium": ndarray, "strong": ndarray}
        返回报告字典
        """
        # 检测各类别中的眨眼峰值
        def find_peaks(seg: np.ndarray) -> List[float]:
            temp_det = BlinkDetector(self.fs)
            evts = temp_det.feed_batch(seg)
            return [e.amplitude_uv for e in evts]

        spont_peaks = find_peaks(calibration_segments.get("spontaneous", np.array([])))
        weak_peaks = find_peaks(calibration_segments.get("weak", np.array([])))
        med_peaks = find_peaks(calibration_segments.get("medium", np.array([])))
        strong_peaks = find_peaks(calibration_segments.get("strong", np.array([])))

        # 基础阈值 = 自发眨眼最大值的 1.5 倍 (防误触)
        t_base = max(spont_peaks) * 1.5 if spont_peaks else 50.0

        # 分界点用均值中点
        t_mid = (np.mean(weak_peaks) + np.mean(med_peaks)) / 2.0 if weak_peaks and med_peaks else 100.0
        t_strong = (np.mean(med_peaks) + np.mean(strong_peaks)) / 2.0 if med_peaks and strong_peaks else 180.0

        self.base_threshold = max(t_base, 30.0)
        self.mid_threshold = max(t_mid, self.base_threshold * 1.5)
        self.strong_threshold = max(t_strong, self.mid_threshold * 1.5)

        return {
            "base_threshold": self.base_threshold,
            "mid_threshold": self.mid_threshold,
            "strong_threshold": self.strong_threshold,
            "spont_count": len(spont_peaks),
            "weak_count": len(weak_peaks),
            "medium_count": len(med_peaks),
            "strong_count": len(strong_peaks),
        }

    # -------------------- 内部工具 --------------------
    def _classify(self, amp: float) -> IntentLevel:
        if amp >= self.strong_threshold:
            return IntentLevel.STRONG
        if amp >= self.mid_threshold:
            return IntentLevel.MEDIUM
        return IntentLevel.WEAK
