from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from config import STYLE
from core.user_profile import UserDatabase, UserProfile
from gui.widgets import BigButton, Card, MutedLabel, SectionTitle, VoiceLabel


class HomePage(QWidget):
    """系统主页：顶部欢迎条 + 左侧用户管理 + 右侧功能导航"""

    sig_start_training = pyqtSignal(str)
    sig_start_calibration = pyqtSignal(str)
    sig_view_records = pyqtSignal(str)
    sig_user_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = UserDatabase()
        self.current_user_id = ""
        self.current_user_name = ""
        self._init_ui()
        self._refresh_user_list()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(20)

        # ========== 顶部欢迎条 ==========
        header = Card()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 16, 24, 16)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = VoiceLabel("CTIS-EEG 认知训练与干预系统", STYLE["font_size_title"])
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_box.addWidget(title)

        subtitle = MutedLabel("基于单通道脑电与意图眨眼的闭环干预平台")
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box, 1)

        self.header_user = MutedLabel("当前未选择用户")
        self.header_user.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.header_user.setStyleSheet(f"color: {STYLE['color_text_subtle']};")
        header_layout.addWidget(self.header_user)

        root.addWidget(header)

        # ========== 中部双栏 ==========
        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, 1)

        # 左：用户管理
        user_card = Card()
        user_layout = QVBoxLayout(user_card)
        user_layout.setContentsMargins(20, 16, 20, 16)
        user_layout.setSpacing(12)

        user_layout.addWidget(SectionTitle("用户管理"))

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("姓名")
        form.addRow(self.name_input)

        self.age_input = QLineEdit()
        self.age_input.setPlaceholderText("年龄")
        form.addRow(self.age_input)

        self.gender_input = QLineEdit()
        self.gender_input.setPlaceholderText("性别 (男/女)")
        form.addRow(self.gender_input)

        self.diagnosis_input = QLineEdit()
        self.diagnosis_input.setPlaceholderText("诊断 (如 MCI / 早期AD)")
        form.addRow(self.diagnosis_input)

        user_layout.addLayout(form)

        self.add_user_btn = BigButton("+ 新建用户", STYLE["font_size_normal"], "ghost")
        self.add_user_btn.setMaximumHeight(52)
        self.add_user_btn.clicked.connect(self._add_user)
        user_layout.addWidget(self.add_user_btn)

        user_layout.addSpacing(4)
        user_layout.addWidget(SectionTitle("已有用户"))

        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self._on_user_selected)
        user_layout.addWidget(self.user_list, 1)

        self.refresh_btn = BigButton("刷新列表", STYLE["font_size_small"], "ghost")
        self.refresh_btn.setMaximumHeight(44)
        self.refresh_btn.clicked.connect(self._refresh_user_list)
        user_layout.addWidget(self.refresh_btn)

        body.addWidget(user_card, 2)

        # 右：功能导航
        nav_card = Card()
        nav_layout = QVBoxLayout(nav_card)
        nav_layout.setContentsMargins(20, 16, 20, 16)
        nav_layout.setSpacing(14)

        nav_layout.addWidget(SectionTitle("功能入口"))

        self.btn_training = BigButton("开始训练", STYLE["font_size_option"], "success")
        self.btn_training.setMinimumHeight(90)
        self.btn_training.clicked.connect(self._on_training)
        nav_layout.addWidget(self.btn_training)

        self.btn_calibration = BigButton("眨眼校准", STYLE["font_size_option"], "warning")
        self.btn_calibration.setMinimumHeight(90)
        self.btn_calibration.clicked.connect(self._on_calibration)
        nav_layout.addWidget(self.btn_calibration)

        self.btn_records = BigButton("查看记录", STYLE["font_size_option"], "primary")
        self.btn_records.setMinimumHeight(90)
        self.btn_records.clicked.connect(self._on_records)
        nav_layout.addWidget(self.btn_records)

        nav_layout.addStretch()

        self.selected_hint = MutedLabel("请先在左侧选择或新建用户")
        self.selected_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_hint.setStyleSheet(f"color: {STYLE['color_wrong']};")
        nav_layout.addWidget(self.selected_hint)

        body.addWidget(nav_card, 3)

    # -------------------- 用户管理 --------------------
    def _refresh_user_list(self):
        self.user_list.clear()
        users = self.db.list_users()
        for u in users:
            display = f"{u.name}  ·  {u.diagnosis or '未标注'}"
            self.user_list.addItem(display)
            item = self.user_list.item(self.user_list.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, u.user_id)

    def _on_user_selected(self, item):
        user_id = item.data(Qt.ItemDataRole.UserRole)
        user = self.db.get_user(user_id)
        if user:
            self.current_user_id = user.user_id
            self.current_user_name = user.name
            self.selected_hint.setText(
                f"✓ 已选择: {user.name}  |  {user.age}岁  |  {user.diagnosis or '无诊断'}"
            )
            self.selected_hint.setStyleSheet(f"color: {STYLE['color_correct']};")
            self.header_user.setText(f"当前用户: {user.name} ({user.user_id})")
            self.header_user.setStyleSheet(f"color: {STYLE['color_primary']};")
            self.sig_user_changed.emit(user.user_id, user.name)

    def _add_user(self):
        name = self.name_input.text().strip()
        age_str = self.age_input.text().strip()
        gender = self.gender_input.text().strip()
        diagnosis = self.diagnosis_input.text().strip()

        if not name:
            QMessageBox.warning(self, "提示", "请输入姓名")
            return
        try:
            age = int(age_str) if age_str else 0
        except ValueError:
            QMessageBox.warning(self, "提示", "年龄必须为数字")
            return

        user_id = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        profile = UserProfile(
            user_id=user_id,
            name=name,
            age=age,
            gender=gender,
            diagnosis=diagnosis,
            created_at=datetime.now().isoformat(),
        )
        if self.db.add_user(profile):
            self.name_input.clear()
            self.age_input.clear()
            self.gender_input.clear()
            self.diagnosis_input.clear()
            self._refresh_user_list()
            for i in range(self.user_list.count()):
                item = self.user_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == user_id:
                    self.user_list.setCurrentItem(item)
                    self._on_user_selected(item)
                    break
        else:
            QMessageBox.warning(self, "错误", "用户创建失败")

    # -------------------- 功能导航 --------------------
    def _on_training(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "提示", "请先选择用户")
            return
        self.sig_start_training.emit(self.current_user_id)

    def _on_calibration(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "提示", "请先选择用户")
            return
        self.sig_start_calibration.emit(self.current_user_id)

    def _on_records(self):
        self.sig_view_records.emit(self.current_user_id or "")

    def _on_settings(self):
        QMessageBox.information(self, "系统设置", "设置功能即将上线")
