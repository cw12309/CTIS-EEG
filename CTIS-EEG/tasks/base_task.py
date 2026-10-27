from enum import Enum
from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QWidget

from signal_processing.blink_detector import BlinkEvent


class TaskState(Enum):
    IDLE = "idle"
    FIXATION = "fixation"
    STIMULUS = "stimulus"
    RESPONSE = "response"
    FEEDBACK = "feedback"
    INTER_TRIAL = "inter_trial"
    REST = "rest"
    FINISHED = "finished"


class BaseTask(QWidget):
    """
    认知训练任务基类
    所有具体任务继承此类，实现 on_enter_* 方法
    """

    sig_trial_complete = pyqtSignal(dict)      # 试次结束，发送 trial 数据 dict
    sig_task_finished = pyqtSignal(dict)       # 任务全部结束
    sig_request_blink = pyqtSignal()           # 请求主控检查眨眼事件
    sig_play_sound = pyqtSignal(str)           # 请求播放音效/语音
    sig_update_status = pyqtSignal(str)        # 更新状态栏文字

    def __init__(self, user_id: str, difficulty: str = "L2", parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.difficulty = difficulty
        self.state = TaskState.IDLE
        self.trial_number = 0
        self.max_trials = 10
        self.score = 0
        self.correct_count = 0
        self.current_trial_data: Dict[str, Any] = {}

        self._timers: list[QTimer] = []

    # -------------------- 生命周期 --------------------
    def start_task(self):
        self.trial_number = 0
        self.score = 0
        self.correct_count = 0
        self._transition_to(TaskState.IDLE)
        self._start_next_trial()

    def stop_task(self):
        for t in self._timers:
            t.stop()
        self._timers.clear()
        self._transition_to(TaskState.FINISHED)
        self.sig_task_finished.emit({
            "user_id": self.user_id,
            "score": self.score,
            "correct_count": self.correct_count,
            "total_trials": self.trial_number,
        })

    def on_blink(self, evt: BlinkEvent):
        """子类重写：处理眨眼事件"""
        pass

    # -------------------- 状态机 --------------------
    def _transition_to(self, new_state: TaskState):
        self.state = new_state
        method_name = f"on_enter_{new_state.value}"
        if hasattr(self, method_name):
            getattr(self, method_name)()

    def _start_next_trial(self):
        if self.trial_number >= self.max_trials:
            self.stop_task()
            return
        self.trial_number += 1
        self.current_trial_data = {
            "trial_id": self.trial_number,
            "difficulty": self.difficulty,
            "start_time": 0,
            "end_time": 0,
            "is_correct": False,
            "intent_level": 0,
            "reaction_time_ms": 0,
        }
        self._transition_to(TaskState.FIXATION)

    def _finish_trial(self):
        self.current_trial_data["end_time"] = 0  # 由子类填充
        self.sig_trial_complete.emit(self.current_trial_data.copy())
        self._transition_to(TaskState.INTER_TRIAL)

    # -------------------- 计时器工具 --------------------
    def _single_shot(self, ms: int, callback: Callable):
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(callback)
        t.start(ms)
        self._timers.append(t)
        return t

    def clear_timers(self):
        for t in self._timers:
            t.stop()
        self._timers.clear()
