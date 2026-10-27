import statistics
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from config import STYLE
from gui.widgets import BigButton, Card, MutedLabel, SectionTitle, VoiceLabel
from signal_processing.blink_detector import BlinkEvent


class CalibrationPage(QWidget):
    sig_finished = pyqtSignal(dict)  # {"base": float, "mid": float, "strong": float}
    sig_back = pyqtSignal()

    PHASES = [
        ("relax", "请保持放松，不要眨眼", 3000),
        ("weak", "请轻轻眨一下眼睛（弱）", 5000),
        ("mid", "请正常眨一下眼睛（中）", 5000),
        ("strong", "请用力眨一下眼睛（强）", 5000),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples: dict[str, list[float]] = {
            "weak": [], "mid": [], "strong": [],
        }
        self._phase_index = -1
        self._start_ms = 0
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(20)

        # 顶部条
        header = Card()
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 12, 20, 12)
        title = SectionTitle("眨眼强度校准")
        h.addWidget(title, 1)
        tip = MutedLabel("依次完成 弱 / 中 / 强 三档眨眼")
        tip.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(tip)
        root.addWidget(header)

        # 主卡片
        main = Card()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(24, 24, 24, 24)
        mv.setSpacing(20)

        self.instruction = VoiceLabel("准备开始校准", STYLE["font_size_question"])
        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction.setStyleSheet(f"color: {STYLE['color_primary']};")
        mv.addWidget(self.instruction)

        self.progress = __import__("PyQt6.QtWidgets", fromlist=["QProgressBar"]).QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        mv.addWidget(self.progress)

        self.feedback = MutedLabel("")
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mv.addWidget(self.feedback)

        mv.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        self.start_btn = BigButton("开始校准", STYLE["font_size_option"], "success")
        self.start_btn.setMinimumHeight(70)
        self.start_btn.clicked.connect(self._start_calibration)
        btn_row.addWidget(self.start_btn, 2)

        self.back_btn = BigButton("返回主页", STYLE["font_size_normal"], "ghost")
        self.back_btn.setMinimumHeight(70)
        self.back_btn.clicked.connect(self.sig_back.emit)
        btn_row.addWidget(self.back_btn, 1)

        mv.addLayout(btn_row)
        root.addWidget(main, 1)

    # -------------------- 校准流程 --------------------
    def reset(self):
        self.samples = {"weak": [], "mid": [], "strong": []}
        self._phase_index = -1
        self.progress.setValue(0)
        self.instruction.setText("准备开始校准")
        self.feedback.setText("")
        self.start_btn.setEnabled(True)
        self.start_btn.setText("开始校准")

    def _start_calibration(self):
        self.start_btn.setEnabled(False)
        self.start_btn.setText("校准中...")
        self._phase_index = 0
        self._run_phase()

    def _run_phase(self):
        if self._phase_index >= len(self.PHASES):
            self._finish()
            return

        phase_key, text, duration_ms = self.PHASES[self._phase_index]
        self.instruction.setText(text)
        self.instruction.speak()
        self.progress.setValue(int((self._phase_index / len(self.PHASES)) * 100))
        self._start_ms = int(time.time() * 1000)

        QTimer.singleShot(duration_ms, self._phase_next)

    def _phase_next(self):
        self._phase_index += 1
        self._run_phase()

    def on_blink(self, evt: BlinkEvent):
        if self._phase_index < 0 or self._phase_index >= len(self.PHASES):
            return
        phase_key = self.PHASES[self._phase_index][0]
        if phase_key in self.samples:
            self.samples[phase_key].append(evt.amplitude_uv)
            self.feedback.setText(f"检测到 {phase_key}: {evt.amplitude_uv:.1f} uV")

    def _finish(self):
        result = {}
        for k, vals in self.samples.items():
            if vals:
                result[k] = round(statistics.median(vals), 2)
            else:
                result[k] = 0.0

        if result["weak"] == 0:
            result["weak"] = 50.0
        if result["mid"] == 0:
            result["mid"] = max(result["weak"] * 1.5, 100.0)
        if result["strong"] == 0:
            result["strong"] = max(result["mid"] * 1.5, 180.0)

        thresholds = {
            "base": max(30.0, result["weak"] * 0.7),
            "mid": (result["weak"] + result["mid"]) / 2,
            "strong": (result["mid"] + result["strong"]) / 2,
        }

        summary = (
            f"校准完成\n"
            f"弱 {result['weak']:.1f} / 中 {result['mid']:.1f} / 强 {result['strong']:.1f} uV"
        )
        self.instruction.setText(summary)
        self.feedback.setText("阈值已保存，可开始训练")
        self.progress.setValue(100)
        self.start_btn.setEnabled(True)
        self.start_btn.setText("重新校准")
        self.sig_finished.emit(thresholds)
