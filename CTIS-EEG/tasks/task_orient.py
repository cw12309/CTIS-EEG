import random
import time
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from config import DIFFICULTY, STYLE
from gui.widgets import VoiceLabel
from signal_processing.blink_detector import BlinkEvent, IntentLevel
from tasks.base_task import BaseTask, TaskState


class TaskOrient(BaseTask):
    """
    EEG-Orient: 定向力训练
    提问关于时间/地点/人物的问题，用户通过眨眼选择答案。
    采用 SCIMT 单目标扫描：选项逐个高亮，意图眨眼锁定。
    """

    def __init__(self, user_id: str, difficulty: str = "L2", parent=None):
        super().__init__(user_id, difficulty, parent)
        self.cfg = DIFFICULTY["orient"][difficulty]
        self.max_trials = 5
        self._options: list[str] = []
        self._correct_idx = 0
        self._scan_idx = 0
        self._dwell_ms = self.cfg["dwell_ms"]
        self._scan_total_ms = self.cfg["scan_total_ms"]
        self._scan_timer: QTimer | None = None
        self._question_start_ms = 0
        self._has_responded = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        self.question_label = VoiceLabel("", STYLE["font_size_question"])
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_label.setStyleSheet(f"color: {STYLE['color_primary']};")
        layout.addWidget(self.question_label)

        self.options_widget = QWidget()
        self.options_layout = QHBoxLayout(self.options_widget)
        self.options_layout.setSpacing(20)
        layout.addWidget(self.options_widget, 1)

        self.hint_label = VoiceLabel("请等待选项高亮后眨眼选择", STYLE["font_size_prompt"])
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        self.score_label = VoiceLabel("得分: 0 / 0", STYLE["font_size_small"])
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.score_label)

    # -------------------- 状态机 --------------------
    def on_enter_fixation(self):
        self._has_responded = False
        self._generate_question()
        self.question_label.setText(self._question_text)
        self.question_label.speak()
        self.hint_label.setText("准备...")
        self._render_options()
        self._single_shot(1500, lambda: self._transition_to(TaskState.STIMULUS))

    def on_enter_stimulus(self):
        self.hint_label.setText("选项正在扫描，请在高亮时眨眼")
        self._scan_idx = 0
        self._question_start_ms = int(time.time() * 1000)
        self._start_scan()

    def on_enter_feedback(self):
        self._stop_scan()
        is_correct = self.current_trial_data["is_correct"]
        if is_correct:
            self.hint_label.setText("回答正确！")
            self.hint_label.setStyleSheet(f"color: {STYLE['color_correct']};")
        else:
            correct = self._options[self._correct_idx]
            self.hint_label.setText(f"正确答案是: {correct}")
            self.hint_label.setStyleSheet(f"color: {STYLE['color_wrong']};")
        self._single_shot(2000, self._finish_trial)

    def on_enter_inter_trial(self):
        self.hint_label.setText("")
        self.hint_label.setStyleSheet("")
        self._single_shot(1000, self._start_next_trial)

    # -------------------- 核心逻辑 --------------------
    def _generate_question(self):
        now = datetime.now()
        q_types = ["year", "month", "weekday", "season"]
        q_type = random.choice(q_types)

        if q_type == "year":
            self._question_text = f"今年是哪一年？"
            self._correct_idx = 0
            opts = [str(now.year)]
            while len(opts) < self.cfg["options"]:
                y = now.year + random.choice([-1, 1, -2, 2])
                if str(y) not in opts:
                    opts.append(str(y))
        elif q_type == "month":
            months = ["一月", "二月", "三月", "四月", "五月", "六月",
                      "七月", "八月", "九月", "十月", "十一月", "十二月"]
            self._question_text = "现在是几月？"
            self._correct_idx = now.month - 1
            opts = months[:]
            if self.cfg["options"] < 12:
                # 随机选取包含正确答案的子集
                others = list(range(12))
                others.remove(self._correct_idx)
                chosen = [self._correct_idx] + random.sample(others, self.cfg["options"] - 1)
                chosen.sort()
                opts = [months[i] for i in chosen]
                self._correct_idx = chosen.index(self._correct_idx)
            else:
                self._correct_idx = now.month - 1
        elif q_type == "weekday":
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            self._question_text = "今天是星期几？"
            wd = now.weekday()
            self._correct_idx = wd
            opts = weekdays[:]
            if self.cfg["options"] < 7:
                others = list(range(7))
                others.remove(wd)
                chosen = [wd] + random.sample(others, self.cfg["options"] - 1)
                chosen.sort()
                opts = [weekdays[i] for i in chosen]
                self._correct_idx = chosen.index(wd)
        elif q_type == "season":
            seasons = ["春季", "夏季", "秋季", "冬季"]
            self._question_text = "现在是什么季节？"
            m = now.month
            season_idx = (m - 1) // 3
            self._correct_idx = season_idx
            opts = seasons[:]
            if self.cfg["options"] < 4:
                others = list(range(4))
                others.remove(season_idx)
                chosen = [season_idx] + random.sample(others, self.cfg["options"] - 1)
                chosen.sort()
                opts = [seasons[i] for i in chosen]
                self._correct_idx = chosen.index(season_idx)

        random.shuffle(opts)
        # 重新定位正确答案
        correct_text = opts[self._correct_idx] if q_type != "year" else str(now.year)
        # 对于year，opts已经shuffle，需要重新找index
        if q_type == "year":
            correct_text = str(now.year)
        self._correct_idx = opts.index(correct_text)
        self._options = opts

    def _render_options(self):
        # 清空旧选项
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
        interval = self._scan_total_ms // n
        self._scan_idx = 0
        self._highlight(0)

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._next_highlight)
        self._scan_timer.start(interval)

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

    # -------------------- 眨眼交互 --------------------
    def on_blink(self, evt: BlinkEvent):
        if self.state != TaskState.STIMULUS or self._has_responded:
            return
        # 只有中等及以上强度视为有效确认
        if evt.intent == IntentLevel.WEAK:
            return

        self._has_responded = True
        chosen_idx = self._scan_idx
        is_correct = (chosen_idx == self._correct_idx)

        rt = int(time.time() * 1000) - self._question_start_ms
        self.current_trial_data.update({
            "start_time": self._question_start_ms,
            "end_time": int(time.time() * 1000),
            "is_correct": is_correct,
            "intent_level": evt.intent.value,
            "reaction_time_ms": rt,
            "question": self._question_text,
            "chosen": self._options[chosen_idx],
            "correct": self._options[self._correct_idx],
        })

        if is_correct:
            self.score += 10
            self.correct_count += 1
        self.score_label.setText(f"得分: {self.score} / {self.trial_number * 10}")

        self._transition_to(TaskState.FEEDBACK)
