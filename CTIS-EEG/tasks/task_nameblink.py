import random
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from config import DIFFICULTY, STYLE
from gui.widgets import VoiceLabel
from signal_processing.blink_detector import BlinkEvent, IntentLevel
from tasks.base_task import BaseTask, TaskState


class TaskNameBlink(BaseTask):
    """
    EEG-NameBlink: 人名再认训练
    展示模拟人物信息（颜色块+关系标签），下方给出人名选项，患者选择正确人名。
    """

    PERSONS = [
        ("张三", "父亲", "#2B579A"),
        ("李四", "母亲", "#228B22"),
        ("王五", "配偶", "#DC143C"),
        ("赵六", "子女", "#FF8C00"),
        ("孙七", "朋友", "#800080"),
        ("周八", "邻居", "#1E90FF"),
    ]

    def __init__(self, user_id: str, difficulty: str = "L2", parent=None):
        super().__init__(user_id, difficulty, parent)
        self.cfg = DIFFICULTY.get("nameblink", DIFFICULTY["orient"])
        self.cfg = self.cfg.get(difficulty, self.cfg["L2"])
        self.max_trials = 5
        self._correct_name = ""
        self._relation = ""
        self._face_color = ""
        self._options: list[str] = []
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

        self.prompt_label = VoiceLabel("这个人是谁？", STYLE["font_size_title"])
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt_label.setStyleSheet(f"color: {STYLE['color_primary']};")
        layout.addWidget(self.prompt_label)

        self.relation_label = VoiceLabel("", STYLE["font_size_prompt"])
        self.relation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.relation_label)

        self.face_block = QLabel("照片")
        self.face_block.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_block.setMinimumHeight(250)
        self.face_block.setStyleSheet(f"border: 4px solid {STYLE['color_primary']}; border-radius: 20px; font-size: 48px;")
        layout.addWidget(self.face_block, 1)

        self.options_widget = QWidget()
        self.options_layout = QHBoxLayout(self.options_widget)
        self.options_layout.setSpacing(20)
        layout.addWidget(self.options_widget)

        self.score_label = VoiceLabel("得分: 0 / 0", STYLE["font_size_small"])
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.score_label)

    def on_enter_fixation(self):
        self._has_responded = False
        self._generate_trial()
        self.relation_label.setText(f"关系: {self._relation}")
        self.face_block.setStyleSheet(
            f"background-color: {self._face_color}; border: 4px solid {STYLE['color_primary']}; "
            f"border-radius: 20px; font-size: 48px; color: #FFFFFF;"
        )
        self.face_block.setText(self._correct_name[0] + "*")
        self._render_options()
        self._single_shot(1500, lambda: self._transition_to(TaskState.STIMULUS))

    def on_enter_stimulus(self):
        self._trial_start_ms = int(time.time() * 1000)
        self._start_scan()

    def on_enter_feedback(self):
        self._stop_scan()
        is_correct = self.current_trial_data["is_correct"]
        if is_correct:
            self.prompt_label.setText("回答正确！")
            self.prompt_label.setStyleSheet(f"color: {STYLE['color_correct']};")
        else:
            self.prompt_label.setText(f"正确答案是: {self._correct_name}")
            self.prompt_label.setStyleSheet(f"color: {STYLE['color_wrong']};")
        self._single_shot(2000, self._finish_trial)

    def on_enter_inter_trial(self):
        self.prompt_label.setText("这个人是谁？")
        self.prompt_label.setStyleSheet(f"color: {STYLE['color_primary']};")
        self._single_shot(1000, self._start_next_trial)

    def _generate_trial(self):
        person = random.choice(self.PERSONS)
        self._correct_name, self._relation, self._face_color = person
        n = self.cfg.get("options", 4)
        others = [p for p in self.PERSONS if p[0] != self._correct_name]
        distractors = random.sample(others, min(n - 1, len(others)))
        self._options = [self._correct_name] + [d[0] for d in distractors]
        random.shuffle(self._options)

    def _render_options(self):
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_labels = []
        for name in self._options:
            lbl = VoiceLabel(name, STYLE["font_size_option"])
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
        chosen_name = self._options[self._scan_idx]
        is_correct = (chosen_name == self._correct_name)

        rt = int(time.time() * 1000) - self._trial_start_ms
        self.current_trial_data.update({
            "start_time": self._trial_start_ms,
            "end_time": int(time.time() * 1000),
            "is_correct": is_correct,
            "intent_level": evt.intent.value,
            "reaction_time_ms": rt,
            "relation": self._relation,
            "chosen": chosen_name,
            "correct": self._correct_name,
        })

        if is_correct:
            self.score += 10
            self.correct_count += 1
        self.score_label.setText(f"得分: {self.score} / {self.trial_number * 10}")
        self._transition_to(TaskState.FEEDBACK)
