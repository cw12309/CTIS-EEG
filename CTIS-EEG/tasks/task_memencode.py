import random
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from config import DIFFICULTY, STYLE
from gui.widgets import VoiceLabel
from signal_processing.blink_detector import BlinkEvent, IntentLevel
from tasks.base_task import BaseTask, TaskState


class TaskMemEncode(BaseTask):
    """
    EEG-MemEncode: 记忆编码训练
    呈现词语+颜色/形状配对，询问是否匹配，患者通过眨眼选择是/否。
    """

    PAIRS = [
        ("红色", "#DC143C"), ("绿色", "#228B22"), ("蓝色", "#1E90FF"),
        ("黄色", "#FFD700"), ("白色", "#F5F5F5"), ("黑色", "#000000"),
        ("橙色", "#FF8C00"), ("紫色", "#800080"),
    ]

    def __init__(self, user_id: str, difficulty: str = "L2", parent=None):
        super().__init__(user_id, difficulty, parent)
        self.cfg = DIFFICULTY.get("memencode", DIFFICULTY["orient"])
        self.cfg = self.cfg.get(difficulty, self.cfg["L2"])
        self.max_trials = 5
        self._word = ""
        self._color = ""
        self._is_match = False
        self._options = ["是", "否"]
        self._option_labels: list[VoiceLabel] = []
        self._scan_idx = 0
        self._scan_timer = None
        self._dwell_ms = self.cfg.get("dwell_ms", 1200)
        self._has_responded = False
        self._trial_start_ms = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        self.word_label = VoiceLabel("", STYLE["font_size_question"])
        self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.word_label.setStyleSheet(f"color: {STYLE['color_primary']};")
        layout.addWidget(self.word_label)

        self.color_block = QLabel()
        self.color_block.setMinimumHeight(200)
        self.color_block.setStyleSheet(f"border: 4px solid {STYLE['color_primary']}; border-radius: 20px;")
        layout.addWidget(self.color_block, 1)

        self.question_label = VoiceLabel("这个词语和颜色是否匹配？", STYLE["font_size_prompt"])
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.question_label)

        self.options_widget = QWidget()
        self.options_layout = QHBoxLayout(self.options_widget)
        self.options_layout.setSpacing(30)
        layout.addWidget(self.options_widget)

        self.score_label = VoiceLabel("得分: 0 / 0", STYLE["font_size_small"])
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.score_label)

    def on_enter_fixation(self):
        self._has_responded = False
        self._generate_trial()
        self.word_label.setText(self._word)
        self.color_block.setStyleSheet(
            f"background-color: {self._color}; border: 4px solid {STYLE['color_primary']}; border-radius: 20px;"
        )
        self._render_options()
        self._single_shot(1500, lambda: self._transition_to(TaskState.STIMULUS))

    def on_enter_stimulus(self):
        self._trial_start_ms = int(time.time() * 1000)
        self._start_scan()

    def on_enter_feedback(self):
        self._stop_scan()
        is_correct = self.current_trial_data["is_correct"]
        if is_correct:
            self.question_label.setText("回答正确！")
            self.question_label.setStyleSheet(f"color: {STYLE['color_correct']};")
        else:
            correct = "是" if self._is_match else "否"
            self.question_label.setText(f"正确答案是: {correct}")
            self.question_label.setStyleSheet(f"color: {STYLE['color_wrong']};")
        self._single_shot(2000, self._finish_trial)

    def on_enter_inter_trial(self):
        self.question_label.setText("这个词语和颜色是否匹配？")
        self.question_label.setStyleSheet("")
        self._single_shot(1000, self._start_next_trial)

    def _generate_trial(self):
        word, true_color = random.choice(self.PAIRS)
        self._is_match = random.choice([True, False])
        if self._is_match:
            self._color = true_color
        else:
            others = [c for w, c in self.PAIRS if c != true_color]
            self._color = random.choice(others)
        self._word = word

    def _render_options(self):
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_labels = []
        for opt in self._options:
            lbl = VoiceLabel(opt, STYLE["font_size_option"])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"""
                background-color: {STYLE['color_card']};
                border: 4px solid {STYLE['color_primary']};
                border-radius: 20px;
                padding: 20px;
            """)
            lbl.setSizePolicy(
                lbl.sizePolicy().Policy.Expanding,
                lbl.sizePolicy().Policy.Expanding,
            )
            self.options_layout.addWidget(lbl)
            self._option_labels.append(lbl)

    def _start_scan(self):
        n = len(self._option_labels)
        if n == 0:
            return
        self._scan_idx = 0
        self._highlight(0)
        from PyQt6.QtCore import QTimer
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._next_highlight)
        self._scan_timer.start(self._dwell_ms)

    def _stop_scan(self):
        if self._scan_timer:
            self._scan_timer.stop()
            self._scan_timer = None

    def _next_highlight(self):
        self._scan_idx = (self._scan_idx + 1) % len(self._option_labels)
        self._highlight(self._scan_idx)

    def _highlight(self, idx: int):
        for i, lbl in enumerate(self._option_labels):
            if i == idx:
                lbl.setStyleSheet(f"""
                    background-color: {STYLE['color_highlight']};
                    border: 6px solid {STYLE['color_primary']};
                    border-radius: 20px;
                    padding: 20px;
                    color: #FFFFFF;
                """)
            else:
                lbl.setStyleSheet(f"""
                    background-color: {STYLE['color_card']};
                    border: 4px solid {STYLE['color_primary']};
                    border-radius: 20px;
                    padding: 20px;
                """)

    def on_blink(self, evt: BlinkEvent):
        if self.state != TaskState.STIMULUS or self._has_responded:
            return
        if evt.intent == IntentLevel.WEAK:
            return

        self._has_responded = True
        chosen_text = self._options[self._scan_idx]
        correct_text = "是" if self._is_match else "否"
        is_correct = (chosen_text == correct_text)

        rt = int(time.time() * 1000) - self._trial_start_ms
        self.current_trial_data.update({
            "start_time": self._trial_start_ms,
            "end_time": int(time.time() * 1000),
            "is_correct": is_correct,
            "intent_level": evt.intent.value,
            "reaction_time_ms": rt,
            "word": self._word,
            "color": self._color,
            "chosen": chosen_text,
        })

        if is_correct:
            self.score += 10
            self.correct_count += 1
        self.score_label.setText(f"得分: {self.score} / {self.trial_number * 10}")
        self._transition_to(TaskState.FEEDBACK)
