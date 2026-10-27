import random
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from config import DIFFICULTY, STYLE
from gui.widgets import VoiceLabel
from signal_processing.blink_detector import BlinkEvent, IntentLevel
from tasks.base_task import BaseTask, TaskState


class TaskSemFlow(BaseTask):
    """
    EEG-SemFlow: 语义流畅训练
    给出类别（如水果），展示若干词语，患者选择属于该类别的词语。
    """

    CATEGORIES = {
        "水果": [("苹果", True), ("香蕉", True), ("汽车", False), ("桌子", False)],
        "动物": [("老虎", True), ("狮子", True), ("铅笔", False), ("书本", False)],
        "颜色": [("红色", True), ("蓝色", True), ("跑步", False), ("吃饭", False)],
        "家具": [("椅子", True), ("沙发", True), ("苹果", False), ("太阳", False)],
    }

    def __init__(self, user_id: str, difficulty: str = "L2", parent=None):
        super().__init__(user_id, difficulty, parent)
        self.cfg = DIFFICULTY.get("semflow", DIFFICULTY["orient"])
        self.cfg = self.cfg.get(difficulty, self.cfg["L2"])
        self.max_trials = 5
        self._category = ""
        self._options: list[tuple[str, bool]] = []  # (word, is_target)
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

        self.cat_label = VoiceLabel("", STYLE["font_size_title"])
        self.cat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cat_label.setStyleSheet(f"color: {STYLE['color_primary']};")
        layout.addWidget(self.cat_label)

        self.prompt_label = VoiceLabel("请选择属于该类别的词语", STYLE["font_size_prompt"])
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.prompt_label)

        self.options_widget = QWidget()
        self.options_layout = QHBoxLayout(self.options_widget)
        self.options_layout.setSpacing(20)
        layout.addWidget(self.options_widget, 1)

        self.score_label = VoiceLabel("得分: 0 / 0", STYLE["font_size_small"])
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.score_label)

    def on_enter_fixation(self):
        self._has_responded = False
        self._generate_trial()
        self.cat_label.setText(f"类别: {self._category}")
        self.cat_label.speak()
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
            correct = [w for w, t in self._options if t]
            self.prompt_label.setText(f"正确答案: {', '.join(correct)}")
            self.prompt_label.setStyleSheet(f"color: {STYLE['color_wrong']};")
        self._single_shot(2000, self._finish_trial)

    def on_enter_inter_trial(self):
        self.prompt_label.setText("请选择属于该类别的词语")
        self.prompt_label.setStyleSheet("")
        self._single_shot(1000, self._start_next_trial)

    def _generate_trial(self):
        self._category = random.choice(list(self.CATEGORIES.keys()))
        pool = self.CATEGORIES[self._category][:]
        random.shuffle(pool)
        n = self.cfg.get("options", 4)
        targets = [p for p in pool if p[1]]
        distractors = [p for p in pool if not p[1]]
        # 确保至少1个目标，1个干扰
        chosen = []
        if targets:
            chosen.append(targets[0])
        if distractors:
            chosen.append(distractors[0])
        # 补齐到n个
        remaining = [p for p in pool if p not in chosen]
        random.shuffle(remaining)
        while len(chosen) < n and remaining:
            chosen.append(remaining.pop())
        random.shuffle(chosen)
        self._options = chosen

    def _render_options(self):
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._option_labels = []
        for word, _ in self._options:
            lbl = VoiceLabel(word, STYLE["font_size_option"])
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
        chosen_idx = self._scan_idx
        chosen_word, is_target = self._options[chosen_idx]
        is_correct = is_target

        rt = int(time.time() * 1000) - self._trial_start_ms
        self.current_trial_data.update({
            "start_time": self._trial_start_ms,
            "end_time": int(time.time() * 1000),
            "is_correct": is_correct,
            "intent_level": evt.intent.value,
            "reaction_time_ms": rt,
            "category": self._category,
            "chosen": chosen_word,
        })

        if is_correct:
            self.score += 10
            self.correct_count += 1
        self.score_label.setText(f"得分: {self.score} / {self.trial_number * 10}")
        self._transition_to(TaskState.FEEDBACK)
