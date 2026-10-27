from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QLabel, QHBoxLayout

from config import STYLE
from gui.widgets import BigButton, Card, MutedLabel, SectionTitle


class TaskSelectPage(QWidget):
    """任务选择页：左侧列表 + 右侧详情描述"""

    sig_select_task = pyqtSignal(str, str)  # task_key, difficulty
    sig_back = pyqtSignal()

    TASKS = [
        ("orient", "EEG-Orient", "定向力训练", "识别时间、地点、人物"),
        ("memencode", "EEG-MemEncode", "记忆编码训练", "图片-词语配对记忆"),
        ("trailblink", "EEG-TrailBlink", "注意追踪训练", "追踪闪烁目标"),
        ("semflow", "EEG-SemFlow", "语义流畅训练", "类别词语联想"),
        ("nameblink", "EEG-NameBlink", "人名再认训练", "亲友面孔识别"),
    ]

    TASK_DESC = {
        "orient": "通过问题与选项扫描训练时间/空间/人物定向力。",
        "memencode": "呈现图片-词语配对，回忆阶段判断是否匹配。",
        "trailblink": "网格中目标顺序闪烁，用户依次用眨眼确认。",
        "semflow": "连续呈现目标类别词与干扰词，识别语义类别。",
        "nameblink": "展示亲友照片与陌生人对照，眨眼确认是否认识。",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(16)

        # 顶部条
        header = Card()
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 12, 20, 12)
        h.addWidget(SectionTitle("选择训练任务"), 1)
        tip = MutedLabel("点击进入相应训练")
        tip.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(tip)
        root.addWidget(header)

        # 列表
        list_card = Card()
        lv = QVBoxLayout(list_card)
        lv.setContentsMargins(16, 12, 16, 12)
        lv.setSpacing(10)

        for key, name, short, desc in self.TASKS:
            item = self._build_item(key, name, short, desc)
            lv.addWidget(item)

        root.addWidget(list_card, 1)

        back_btn = BigButton("返回主页", STYLE["font_size_normal"], "ghost")
        back_btn.setMinimumHeight(56)
        back_btn.clicked.connect(self.sig_back.emit)
        root.addWidget(back_btn)

    def _build_item(self, key: str, name: str, short: str, desc: str) -> QWidget:
        from PyQt6.QtWidgets import QFrame
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {STYLE['color_bg']};
                border: 1px solid {STYLE['color_border']};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border: 1px solid {STYLE['color_primary']};
                background-color: {STYLE['color_surface']};
            }}
        """)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        t = QLabel(f"{name} · {short}")
        t.setFont(QFont(STYLE["font_family"], STYLE["font_size_option"], QFont.Weight.Bold))
        text_box.addWidget(t)
        d = MutedLabel(self.TASK_DESC.get(key, desc))
        text_box.addWidget(d)
        layout.addLayout(text_box, 1)

        btn = BigButton("开始", STYLE["font_size_normal"], "primary")
        btn.setMinimumWidth(120)
        btn.setMinimumHeight(56)
        btn.clicked.connect(lambda checked, k=key: self._on_task(k))
        layout.addWidget(btn)
        return card

    def _on_task(self, key: str):
        self.sig_select_task.emit(key, "L2")
