import sys
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from config import STYLE
from gui.calibration_page import CalibrationPage
from gui.home_page import HomePage
from gui.records_page import RecordsPage
from gui.styles import get_ad_stylesheet
from gui.task_select_page import TaskSelectPage
from gui.widgets import StatusBar
from core.session_manager import SessionManager, SessionPhase, TrialRecord
from hardware.tgam_interface import TGAMInterface
from signal_processing.blink_detector import BlinkDetector
from tasks.task_memencode import TaskMemEncode
from tasks.task_nameblink import TaskNameBlink
from tasks.task_orient import TaskOrient
from tasks.task_semflow import TaskSemFlow
from tasks.task_trailblink import TaskTrailBlink


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CTIS-EEG 阿尔茨海默症认知训练与干预系统")
        self.showFullScreen()

        # 硬件 & 信号处理
        self.tgam = TGAMInterface(mode="sim")
        self.detector = BlinkDetector()
        self.tgam.on_raw_sample = self._on_raw_sample

        # 中心容器：堆叠窗口 + 底部状态栏
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 状态栏
        self.status_bar = StatusBar(self)
        self.status_bar.set_hardware_status(False, "sim")

        # 堆叠窗口
        self.stack = QStackedWidget()

        # 主页
        self.home_page = HomePage()
        self.home_page.sig_user_changed.connect(self._on_user_changed)
        self.home_page.sig_start_training.connect(self._on_start_training)
        self.home_page.sig_start_calibration.connect(self._on_start_calibration)
        self.home_page.sig_view_records.connect(self._on_view_records)
        self.stack.addWidget(self.home_page)

        # 任务选择页
        self.task_select = TaskSelectPage()
        self.task_select.sig_select_task.connect(self._on_select_task)
        self.task_select.sig_back.connect(self._go_home)
        self.stack.addWidget(self.task_select)

        # 校准页
        self.calib_page = CalibrationPage()
        self.calib_page.sig_finished.connect(self._on_calibration_finished)
        self.calib_page.sig_back.connect(self._go_home)
        self.stack.addWidget(self.calib_page)

        # 训练任务页 (EEG-Orient)
        self.task_orient = TaskOrient("", "L2")
        self.task_orient.sig_task_finished.connect(self._on_task_finished)
        self.stack.addWidget(self.task_orient)

        # 训练任务页 (EEG-TrailBlink)
        self.task_trail = TaskTrailBlink("", "L2")
        self.task_trail.sig_task_finished.connect(self._on_task_finished)
        self.stack.addWidget(self.task_trail)

        # 训练任务页 (EEG-MemEncode)
        self.task_mem = TaskMemEncode("", "L2")
        self.task_mem.sig_task_finished.connect(self._on_task_finished)
        self.stack.addWidget(self.task_mem)

        # 训练任务页 (EEG-SemFlow)
        self.task_sem = TaskSemFlow("", "L2")
        self.task_sem.sig_task_finished.connect(self._on_task_finished)
        self.stack.addWidget(self.task_sem)

        # 训练任务页 (EEG-NameBlink)
        self.task_name = TaskNameBlink("", "L2")
        self.task_name.sig_task_finished.connect(self._on_task_finished)
        self.stack.addWidget(self.task_name)

        # 记录查看页
        self.records_page = RecordsPage()
        self.records_page.sig_back.connect(self._go_home)
        self.stack.addWidget(self.records_page)

        layout.addWidget(self.stack, 1)
        layout.addWidget(self.status_bar)
        self.setCentralWidget(central)

        # 启动 TGAM
        self.tgam.start_stream()
        self.status_bar.set_hardware_status(True, self.tgam.mode)

        self._current_user_id = ""
        self._session_mgr: SessionManager | None = None
        self._task_difficulty = {
            "orient": "L2", "trailblink": "L2", "memencode": "L2",
            "semflow": "L2", "nameblink": "L2",
        }
        self._recent_correct = []  # 最近试次正确记录，用于IGAD

        # 连接各任务的 trial_complete 信号
        self.task_orient.sig_trial_complete.connect(self._on_trial_complete)
        self.task_trail.sig_trial_complete.connect(self._on_trial_complete)
        self.task_mem.sig_trial_complete.connect(self._on_trial_complete)
        self.task_sem.sig_trial_complete.connect(self._on_trial_complete)
        self.task_name.sig_trial_complete.connect(self._on_trial_complete)

    # -------------------- 信号回调 --------------------
    def _on_raw_sample(self, idx: int, uv: float):
        evt = self.detector.feed(uv)
        if evt:
            print(f"[Blink] {evt.intent.name} amp={evt.amplitude_uv:.1f}uV")
            # 转发给当前页面
            current = self.stack.currentWidget()
            if hasattr(current, "on_blink"):
                current.on_blink(evt)

    def _on_user_changed(self, user_id: str, user_name: str):
        self._current_user_id = user_id
        self.status_bar.set_user(user_id, user_name)

    def _on_start_training(self, user_id: str):
        if not user_id:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先选择或创建用户")
            return
        self.stack.setCurrentWidget(self.task_select)
        self.status_bar.set_update_status(f"选择任务 - {user_id}")

    def _on_select_task(self, task_key: str, difficulty: str):
        diff = self._task_difficulty.get(task_key, "L2")
        self._session_mgr = SessionManager(self._current_user_id)
        self._session_mgr.set_phase(SessionPhase.TRAINING)
        self._recent_correct = []

        if task_key == "orient":
            self.task_orient.user_id = self._current_user_id
            self.task_orient.difficulty = diff
            self.task_orient.start_task()
            self.stack.setCurrentWidget(self.task_orient)
            self.status_bar.set_update_status(f"定向力训练 - {self._current_user_id}")
        elif task_key == "trailblink":
            self.task_trail.user_id = self._current_user_id
            self.task_trail.difficulty = diff
            self.task_trail.start_task()
            self.stack.setCurrentWidget(self.task_trail)
            self.status_bar.set_update_status(f"注意追踪训练 - {self._current_user_id}")
        elif task_key == "memencode":
            self.task_mem.user_id = self._current_user_id
            self.task_mem.difficulty = diff
            self.task_mem.start_task()
            self.stack.setCurrentWidget(self.task_mem)
            self.status_bar.set_update_status(f"记忆编码训练 - {self._current_user_id}")
        elif task_key == "semflow":
            self.task_sem.user_id = self._current_user_id
            self.task_sem.difficulty = diff
            self.task_sem.start_task()
            self.stack.setCurrentWidget(self.task_sem)
            self.status_bar.set_update_status(f"语义流畅训练 - {self._current_user_id}")
        elif task_key == "nameblink":
            self.task_name.user_id = self._current_user_id
            self.task_name.difficulty = diff
            self.task_name.start_task()
            self.stack.setCurrentWidget(self.task_name)
            self.status_bar.set_update_status(f"人名再认训练 - {self._current_user_id}")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", f"任务 {task_key} 正在开发中")

    def _on_start_calibration(self, user_id: str):
        if not user_id:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先选择或创建用户")
            return
        self.calib_page.reset()
        self.stack.setCurrentWidget(self.calib_page)
        self.status_bar.set_update_status(f"校准中 - {user_id}")

    def _on_calibration_finished(self, thresholds: dict):
        self.detector.base_threshold = thresholds["base"]
        self.detector.mid_threshold = thresholds["mid"]
        self.detector.strong_threshold = thresholds["strong"]
        print(f"[Main] 校准阈值更新: {thresholds}")
        # 可在此保存到用户数据库

    def _on_trial_complete(self, data: dict):
        if self._session_mgr is None:
            return
        record = TrialRecord(
            trial_id=data.get("trial_id", 0),
            task_type="unknown",
            stimulus=data.get("question", data.get("category", "")),
            blink_type="intentional",
            intent_level=data.get("intent_level", 0),
            is_correct=data.get("is_correct", False),
            reaction_time_ms=data.get("reaction_time_ms", 0),
            difficulty=data.get("difficulty", "L2"),
            timestamp=time.time(),
            extra=data,
        )
        self._session_mgr.add_trial(record)
        self._recent_correct.append(data.get("is_correct", False))
        if len(self._recent_correct) > 5:
            self._recent_correct.pop(0)

    def _apply_igad(self, task_key: str):
        if len(self._recent_correct) < 3:
            return
        recent = self._recent_correct[-3:]
        acc = sum(recent) / len(recent)
        current = self._task_difficulty.get(task_key, "L2")
        levels = ["L1", "L2", "L3"]
        idx = levels.index(current)
        if acc >= 0.8 and idx < 2:
            self._task_difficulty[task_key] = levels[idx + 1]
            print(f"[IGAD] 准确率 {acc:.0%}，难度提升: {current} -> {levels[idx + 1]}")
        elif acc <= 0.4 and idx > 0:
            self._task_difficulty[task_key] = levels[idx - 1]
            print(f"[IGAD] 准确率 {acc:.0%}，难度降低: {current} -> {levels[idx - 1]}")

    def _on_task_finished(self, result: dict):
        if self._session_mgr:
            ct30 = result.get("score", 0)
            cog_vec = [0.0] * 5
            summary = self._session_mgr.finalize(ct30, cog_vec)
            print(f"[Session] 已保存: {summary['log_path']}")

        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "训练完成",
            f"用户: {result['user_id']}\n"
            f"得分: {result['score']}\n"
            f"正确数: {result['correct_count']} / {result['total_trials']}"
        )
        self._go_home()

    def _on_view_records(self, user_id: str):
        if not user_id:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先选择或创建用户")
            return
        self.records_page.load_records(user_id)
        self.stack.setCurrentWidget(self.records_page)
        self.status_bar.set_update_status(f"查看记录 - {user_id}")

    def _go_home(self):
        self.stack.setCurrentWidget(self.home_page)
        self.status_bar.set_update_status("")

    # -------------------- 键盘退出全屏 --------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key.Key_Q and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.tgam.stop_stream()
        event.accept()


def run_app():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(get_ad_stylesheet())

    # 全局字体
    font = app.font()
    font.setFamily(STYLE["font_family"])
    font.setPointSize(14)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
