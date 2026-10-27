from config import STYLE


def get_ad_stylesheet() -> str:
    """AD友好型全局 QSS"""
    f = STYLE["font_family"]
    bg = STYLE["color_bg"]
    surface = STYLE["color_surface"]
    text = STYLE["color_text"]
    subtle = STYLE["color_text_subtle"]
    primary = STYLE["color_primary"]
    primary_dark = STYLE["color_primary_dark"]
    accent = STYLE["color_accent"]
    card = STYLE["color_card"]
    highlight = STYLE["color_highlight"]
    correct = STYLE["color_correct"]
    wrong = STYLE["color_wrong"]
    border = STYLE["color_border"]

    return f"""
    QWidget {{
        font-family: {f};
        background-color: {bg};
        color: {text};
    }}

    QMainWindow {{
        background-color: {bg};
    }}

    QLabel {{
        font-size: {STYLE['font_size_normal']}px;
        color: {text};
        background: transparent;
    }}

    QLabel#muted {{
        color: {subtle};
    }}

    /* === 通用按钮 === */
    QPushButton {{
        font-size: {STYLE['font_size_normal']}px;
        background-color: {primary};
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px 24px;
        min-height: 56px;
    }}
    QPushButton:hover {{
        background-color: {primary_dark};
    }}
    QPushButton:pressed {{
        background-color: {primary_dark};
        padding-top: 14px;
    }}
    QPushButton:disabled {{
        background-color: #B0B7C2;
        color: #EEEEEE;
    }}

    QPushButton[variant="primary"] {{
        background-color: {primary};
        color: white;
    }}
    QPushButton[variant="primary"]:hover {{
        background-color: {primary_dark};
    }}

    QPushButton[variant="success"] {{
        background-color: {correct};
        color: white;
    }}
    QPushButton[variant="warning"] {{
        background-color: {highlight};
        color: white;
    }}
    QPushButton[variant="ghost"] {{
        background-color: transparent;
        color: {primary};
        border: 2px solid {primary};
    }}
    QPushButton[variant="ghost"]:hover {{
        background-color: {primary};
        color: white;
    }}

    /* === 输入框 === */
    QLineEdit, QComboBox {{
        font-size: {STYLE['font_size_normal']}px;
        border: 1px solid {border};
        border-radius: 8px;
        padding: 10px 12px;
        background-color: {surface};
        min-height: 44px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 2px solid {primary};
    }}

    /* === 列表 === */
    QListWidget {{
        font-size: {STYLE['font_size_normal']}px;
        border: 1px solid {border};
        border-radius: 8px;
        padding: 4px;
        background-color: {surface};
        outline: 0;
    }}
    QListWidget::item {{
        padding: 14px 12px;
        border-bottom: 1px solid {border};
    }}
    QListWidget::item:selected {{
        background-color: {primary};
        color: white;
    }}
    QListWidget::item:hover:!selected {{
        background-color: #EEF2F8;
    }}

    /* === 进度条 === */
    QProgressBar {{
        font-size: {STYLE['font_size_small']}px;
        border: 1px solid {border};
        border-radius: 8px;
        text-align: center;
        height: 28px;
        background-color: {surface};
    }}
    QProgressBar::chunk {{
        background-color: {primary};
        border-radius: 6px;
    }}

    /* === 滚动条 === */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {border};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {subtle};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    /* === 消息框 === */
    QMessageBox {{
        font-size: {STYLE['font_size_normal']}px;
    }}
    QMessageBox QPushButton {{
        min-width: 100px;
        min-height: 44px;
    }}
    """
