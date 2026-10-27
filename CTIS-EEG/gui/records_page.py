import json
import os
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from config import DATA_DIR, STYLE
from gui.widgets import BigButton, Card, MutedLabel, SectionTitle, VoiceLabel


class RecordsPage(QWidget):
    sig_back = pyqtSignal()

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
        h.addWidget(SectionTitle("个人训练记录"), 1)
        self.summary_label = MutedLabel("")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self.summary_label)
        root.addWidget(header)

        # 列表卡片
        list_card = Card()
        lv = QVBoxLayout(list_card)
        lv.setContentsMargins(16, 12, 16, 12)
        lv.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        lv.addWidget(scroll, 1)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.scroll_content)

        root.addWidget(list_card, 1)

        back_btn = BigButton("返回主页", STYLE["font_size_normal"], "ghost")
        back_btn.setMinimumHeight(56)
        back_btn.clicked.connect(self.sig_back.emit)
        root.addWidget(back_btn)

    def load_records(self, user_id: str):
        # 清空旧记录
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not user_id:
            self.summary_label.setText("未选择用户")
            return

        records = self._fetch_user_records(user_id)
        total_sessions = len(records)
        total_score = sum(r.get("ct30", 0) for r in records)
        total_trials = sum(r.get("trial_count", 0) for r in records)

        self.summary_label.setText(
            f"用户 {user_id}  |  训练 {total_sessions} 次  |  累计 {total_trials} 试次  |  总分 {total_score}"
        )

        if not records:
            empty = MutedLabel("暂无训练记录，完成训练后会在此显示")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(empty)
            return

        for rec in records:
            self.scroll_layout.addWidget(self._build_card(rec))
        self.scroll_layout.addStretch()

    def _fetch_user_records(self, user_id: str) -> list[dict]:
        records = []
        prefix = f"session_{user_id}_"
        if not os.path.isdir(DATA_DIR):
            return records
        for fname in os.listdir(DATA_DIR):
            if not fname.startswith(prefix) or not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(DATA_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line in reversed(lines):
                    obj = json.loads(line)
                    if obj.get("event") == "session_summary":
                        records.append(obj)
                        break
            except Exception:
                continue
        records.sort(key=lambda x: x.get("session_id", 0), reverse=True)
        return records

    def _build_card(self, rec: dict) -> QWidget:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {STYLE['color_bg']};
                border: 1px solid {STYLE['color_border']};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        sid = rec.get("session_id", 0)
        dt = datetime.fromtimestamp(sid).strftime("%Y-%m-%d %H:%M")
        score = rec.get("ct30", 0)
        trials = rec.get("trial_count", 0)
        duration = rec.get("duration_sec", 0)

        header_row = QHBoxLayout()
        title = QLabel(f"训练时间  {dt}")
        title.setFont(QFont(STYLE["font_family"], STYLE["font_size_normal"], QFont.Weight.Bold))
        header_row.addWidget(title, 1)
        score_lbl = QLabel(f"得分 {score}")
        score_lbl.setStyleSheet(f"color: {STYLE['color_primary']};")
        score_lbl.setFont(QFont(STYLE["font_family"], STYLE["font_size_normal"], QFont.Weight.Bold))
        header_row.addWidget(score_lbl)
        layout.addLayout(header_row)

        detail = MutedLabel(f"试次数 {trials}  ·  时长 {int(duration)} 秒")
        layout.addWidget(detail)

        return card
