import random
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from config import DIFFICULTY, STYLE
from gui.widgets import VoiceLabel
from signal_processing.blink_detector import BlinkEvent, IntentLevel
from tasks.base_task import BaseTask, TaskState


class TaskTrailBlink(BaseTask):
    """
    EEG-TrailBlink: 注意追踪训练
    在 N x N 网格中，目标按序闪烁，患者在目标高亮时眨眼确认。
    """

    def __init__(self, user_id: str, difficulty: str = "L2", parent=None):
        super().__init__(user_id, difficulty, parent)
        self.cfg = DIFFICULTY.get("trailblink", DIFFICULTY["orient"])
        self.cfg = self.cfg.get(difficulty, self.cfg["L2"])
        self.max_trials = 5
        self._grid_size = self.cfg.get("grid_size", 3)
        self._dwell_ms = self.cfg.get("dwell_ms", 1200)
        self._target_sequence: list[int] = []  # 目标位置索引序列
        self._seq_idx = 0
        self._cells: list[QLabel] = []
        self._scan_timer: QTimer | None = None
        self._current_highlight = -1
        self._trial_start_ms = 0
        self._has_responded = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        self.title_label = VoiceLabel("注意追踪训练", STYLE["font_size_title"])
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.prompt_label = VoiceLabel("请追踪闪烁的目标，高亮时眨眼", STYLE["font_size_prompt"])
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.prompt_label)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(15)
        layout.addWidget(self.grid_widget, 1)

        self.score_label = VoiceLabel("得分: 0 / 0", STYLE["font_size_small"])
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.score_label)

    # -------------------- 状态机 --------------------
    def on_enter_fixation(self):
        self._has_responded = False
        self._seq_idx = 0
        n = self._grid_size * self._grid_size
        self._target_sequence = random.sample(range(n), min(3, n))
        self.prompt_label.setText(f"本轮需追踪 {len(self._target_sequence)} 个目标")
        self._build_grid()
        self._single_shot(1500, lambda: self._transition_to(TaskState.STIMULUS))

    def on_enter_stimulus(self):
        self._trial_start_ms = int(time.time() * 1000)
        self._start_scan()

    def on_enter_feedback(self):
        self._stop_scan()
        is_correct = self.current_trial_data["is_correct"]
        if is_correct:
            self.prompt_label.setText("正确！")
            self.prompt_label.setStyleSheet(f"color: {STYLE['color_correct']};")
        else:
            self.prompt_label.setText("错误")
            self.prompt_label.setStyleSheet(f"color: {STYLE['color_wrong']};")
        self._single_shot(1500, self._finish_trial)

    def on_enter_inter_trial(self):
        self.prompt_label.setText("")
        self.prompt_label.setStyleSheet("")
        self._single_shot(800, self._start_next_trial)

    # -------------------- 核心逻辑 --------------------
    def _build_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells = []
        for i in range(self._grid_size):
            for j in range(self._grid_size):
                cell = QLabel("")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setStyleSheet(f"""
                    background-color: {STYLE['color_card']};
                    border: 4px solid {STYLE['color_primary']};
                    border-radius: 15px;
                """)
                cell.setMinimumSize(80, 80)
                self.grid_layout.addWidget(cell, i, j)
                self._cells.append(cell)

    def _start_scan(self):
        n = len(self._cells)
        if n == 0:
            return
        self._current_highlight = 0
        self._highlight(self._current_highlight)
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._next_highlight)
        self._scan_timer.start(self._dwell_ms)

    def _stop_scan(self):
        if self._scan_timer:
            self._scan_timer.stop()
            self._scan_timer = None

    def _next_highlight(self):
        self._current_highlight = (self._current_highlight + 1) % len(self._cells)
        self._highlight(self._current_highlight)

    def _highlight(self, idx: int):
        for i, cell in enumerate(self._cells):
            if i == idx:
                cell.setStyleSheet(f"""
                    background-color: {STYLE['color_highlight']};
                    border: 6px solid {STYLE['color_primary']};
                    border-radius: 15px;
                """)
            else:
                cell.setStyleSheet(f"""
                    background-color: {STYLE['color_card']};
                    border: 4px solid {STYLE['color_primary']};
                    border-radius: 15px;
                """)

    def on_blink(self, evt: BlinkEvent):
        if self.state != TaskState.STIMULUS or self._has_responded:
            return
        if evt.intent == IntentLevel.WEAK:
            return

        self._has_responded = True
        chosen_idx = self._current_highlight
        target = self._target_sequence[self._seq_idx]
        is_correct = (chosen_idx == target)

        rt = int(time.time() * 1000) - self._trial_start_ms
        self.current_trial_data.update({
            "start_time": self._trial_start_ms,
            "end_time": int(time.time() * 1000),
            "is_correct": is_correct,
            "intent_level": evt.intent.value,
            "reaction_time_ms": rt,
            "target": target,
            "chosen": chosen_idx,
        })

        if is_correct:
            self.score += 10
            self.correct_count += 1
            self._seq_idx += 1
            if self._seq_idx >= len(self._target_sequence):
                # 完成本轮所有目标
                pass
            else:
                # 继续扫描下一个目标
                self._has_responded = False
                self._trial_start_ms = int(time.time() * 1000)
                return  # 不切换状态，继续扫描

        self.score_label.setText(f"得分: {self.score} / {self.trial_number * 10}")
        self._transition_to(TaskState.FEEDBACK)
