import pyttsx3
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from config import STYLE, TTS_RATE, TTS_VOLUME


class VoiceLabel(QLabel):
    """支持点击语音播报的大字标签"""

    def __init__(self, text: str = "", font_size: int = None, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fs = font_size or STYLE["font_size_normal"]
        self.setFont(QFont(STYLE["font_family"], fs))
        self._tts_text = text
        self._engine = None

    def set_tts_text(self, text: str):
        self._tts_text = text

    def speak(self):
        try:
            if self._engine is None:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", self._engine.getProperty("rate") + TTS_RATE)
                self._engine.setProperty("volume", TTS_VOLUME)
            self._engine.say(self._tts_text or self.text())
            self._engine.runAndWait()
        except Exception as e:
            print(f"[TTS] 语音播报失败: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.speak()


class BigButton(QPushButton):
    """AD友好大按钮：支持 variant 属性以适配 QSS 主题"""

    def __init__(self, text: str = "", font_size: int = None, variant: str = "primary", parent=None):
        super().__init__(text, parent)
        fs = font_size or STYLE["font_size_normal"]
        self.setFont(QFont(STYLE["font_family"], fs, QFont.Weight.Bold))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("variant", variant)


class Card(QFrame):
    """通用卡片容器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {STYLE['color_card']};
                border: 1px solid {STYLE['color_border']};
                border-radius: 12px;
            }}
        """)


class SectionTitle(QLabel):
    """分节标题"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(QFont(STYLE["font_family"], STYLE["font_size_prompt"], QFont.Weight.Bold))
        self.setStyleSheet(f"color: {STYLE['color_text_subtle']}; letter-spacing: 1px;")


class MutedLabel(QLabel):
    """次要文字"""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setFont(QFont(STYLE["font_family"], STYLE["font_size_small"]))
        self.setStyleSheet(f"color: {STYLE['color_text_subtle']};")


class StatusBar(QWidget):
    """底部状态栏"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"background-color: {STYLE['color_surface']}; "
            f"border-top: 1px solid {STYLE['color_border']};"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 4, 20, 4)
        layout.setSpacing(24)

        self.hardware_label = MutedLabel("硬件: 未连接")
        layout.addWidget(self.hardware_label)

        layout.addStretch()

        self.user_label = MutedLabel("当前用户: 未选择")
        layout.addWidget(self.user_label)

        layout.addStretch()

        self.status_label = MutedLabel("")
        layout.addWidget(self.status_label)

        self.time_label = MutedLabel("")
        layout.addWidget(self.time_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)
        self._timer.start(1000)
        self._update_time()

    def set_hardware_status(self, connected: bool, mode: str = ""):
        color = STYLE["color_correct"] if connected else STYLE["color_wrong"]
        text = f"● 硬件: 已连接 ({mode})" if connected else "○ 硬件: 未连接"
        self.hardware_label.setText(text)
        self.hardware_label.setStyleSheet(f"color: {color};")

    def set_user(self, user_id: str, user_name: str = ""):
        text = f"当前用户: {user_name} ({user_id})" if user_name else f"当前用户: {user_id}"
        self.user_label.setText(text)
        self.user_label.setStyleSheet(f"color: {STYLE['color_text']};")

    def set_update_status(self, status: str):
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {STYLE['color_accent']};")

    def _update_time(self):
        self.time_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M"))
