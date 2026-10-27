import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from config import DATA_DIR


class SessionPhase(Enum):
    IDLE = "idle"
    BASELINE = "baseline"          # 2min 静息
    CALIBRATION = "calibration"    # 眨眼校准
    ASSESSMENT = "assessment"      # BCI-MoCA
    TRAINING = "training"          # 训练任务
    REST = "rest"                  # 模块间休息
    REPORT = "report"              # 会话报告


@dataclass
class TrialRecord:
    trial_id: int
    task_type: str
    stimulus: str
    blink_type: str          # "intentional" | "spontaneous" | "none"
    intent_level: int        # 0|1|2|3
    is_correct: bool
    reaction_time_ms: int
    difficulty: str          # "L1" | "L2" | "L3"
    timestamp: float
    extra: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """单次会话的状态机与数据记录"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.session_id = int(time.time())
        self.phase = SessionPhase.IDLE
        self.start_time = time.time()
        self.trial_counter = 0
        self.trials: List[TrialRecord] = []
        self.cognitive_vector = [0.0] * 5   # D1-D5
        self.ct30_score = 0.0
        self.log_path = os.path.join(
            DATA_DIR, f"session_{user_id}_{self.session_id}.jsonl"
        )

    def set_phase(self, phase: SessionPhase):
        self.phase = phase
        self._append_log({"event": "phase_change", "phase": phase.value, "t": time.time()})

    def add_trial(self, record: TrialRecord):
        self.trials.append(record)
        self.trial_counter += 1
        self._append_log(record.__dict__)

    def add_event(self, event_type: str, payload: dict):
        payload["event"] = event_type
        payload["t"] = time.time()
        self._append_log(payload)

    def finalize(self, ct30: float, cog_vec: List[float]):
        self.ct30_score = ct30
        self.cognitive_vector = cog_vec
        summary = {
            "event": "session_summary",
            "user_id": self.user_id,
            "session_id": self.session_id,
            "duration_sec": time.time() - self.start_time,
            "ct30": ct30,
            "cognitive_vector": cog_vec,
            "trial_count": len(self.trials),
        }
        self._append_log(summary)
        return summary

    def _append_log(self, obj: dict):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
