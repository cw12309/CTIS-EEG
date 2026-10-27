import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_files")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 硬件参数 ====================
SAMPLING_RATE = 512          # Hz
SERIAL_BAUDRATE = 57600
SERIAL_TIMEOUT = 1           # seconds
DEFAULT_COM_PORT = "COM3"

# ==================== 滤波参数 ====================
FILTER_LOWCUT = 0.5          # Hz
FILTER_HIGHCUT = 45.0        # Hz
FILTER_ORDER = 4

# ==================== 眨眼检测 ====================
BLINK_MIN_INTERVAL_MS = 300  # 两次眨眼最小间隔
BLINK_WINDOW_MS = 500        # 眨眼段长度 (峰值前100ms + 后400ms)
BLINK_BASE_THRESHOLD_UV = 50 # 默认基础阈值 (微伏)，校准后会覆盖

# ==================== 监测路径 FFT ====================
FFT_WINDOW_SEC = 30
FFT_STEP_SEC = 5
ALPHA_BAND = (8, 13)
THETA_BAND = (4, 7)

# ==================== GUI 样式 (AD友好) ====================
STYLE = {
    "font_family": "Microsoft YaHei, SimHei, sans-serif",
    "font_size_title": 36,
    "font_size_question": 32,
    "font_size_option": 36,
    "font_size_prompt": 24,
    "font_size_normal": 20,
    "font_size_small": 18,
    "color_bg": "#F4F6FA",
    "color_surface": "#FFFFFF",
    "color_text": "#1F2933",
    "color_text_subtle": "#5A6675",
    "color_highlight": "#FF8C00",
    "color_correct": "#2E7D32",
    "color_wrong": "#C62828",
    "color_rest": "#1A1A1A",
    "color_card": "#FFFFFF",
    "color_primary": "#3A6BAA",
    "color_primary_dark": "#244A7A",
    "color_accent": "#00A8A8",
    "color_border": "#D7DEE8",
}

# ==================== 任务难度参数 ====================
DIFFICULTY = {
    "orient": {
        "L1": {"options": 3, "dwell_ms": 1500, "scan_total_ms": 6000},
        "L2": {"options": 4, "dwell_ms": 1200, "scan_total_ms": 6000},
        "L3": {"options": 4, "dwell_ms": 900,  "scan_total_ms": 6000},
    },
    "trailblink": {
        "L1": {"dwell_ms": 1500, "steps": 6},
        "L2": {"dwell_ms": 900,  "steps": 10},
        "L3": {"dwell_ms": 600,  "steps": 16},
    },
    "memencode": {
        "L1": {"words": 8,  "presentation_ms": 3000, "judge_ms": 2000, "distractors": 8},
        "L2": {"words": 12, "presentation_ms": 3000, "judge_ms": 2000, "distractors": 12},
        "L3": {"words": 16, "presentation_ms": 3000, "judge_ms": 2000, "distractors": 16},
    },
    "semflow": {
        "L1": {"image_ms": 1500, "distractor_ratio": 0.2, "categories": 3},
        "L2": {"image_ms": 1200, "distractor_ratio": 0.2, "categories": 3},
        "L3": {"image_ms": 900,  "distractor_ratio": 0.3, "categories": 3},
    },
    "nameblink": {
        "L1": {"timeout_ms": 10000, "options": 3},
        "L2": {"timeout_ms": 8000,  "options": 4},
        "L3": {"timeout_ms": 6000,  "options": 4},
    },
}

# ==================== 语音配置 ====================
TTS_RATE = -20               # 语速调整百分比 (负值为更慢)
TTS_VOLUME = 1.0
