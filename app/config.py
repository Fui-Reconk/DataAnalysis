"""全局配置加载：从项目根目录的 config.cfg 读取全部可调参数。

config.py 仅保留加载与解析逻辑，所有可调参数集中在项目根目录的
config.cfg（INI 格式，支持 # 注释）中维护，改配置无需动代码；
config.cfg 缺失时全部回退到代码内置默认值，应用仍可正常运行。
"""
from __future__ import annotations

import configparser
from pathlib import Path

_CFG_PATH = Path(__file__).resolve().parent.parent / "config.cfg"

_cfg = configparser.ConfigParser()
if _CFG_PATH.exists():
    _cfg.read(_CFG_PATH, encoding="utf-8")


def _pair(section: str, key: str, fallback: tuple) -> tuple:
    """读取逗号分隔的二元组（如浅色/深色颜色对）。"""
    raw = _cfg.get(section, key, fallback=",".join(str(x) for x in fallback))
    return tuple(p.strip() for p in raw.split(","))


def _font(section: str, key: str, fallback: tuple) -> tuple:
    """读取字体配置：family,size[,weight]。"""
    raw = _cfg.get(section, key, fallback=",".join(str(x) for x in fallback))
    parts = [p.strip() for p in raw.split(",")]
    size = int(parts[1])
    if len(parts) >= 3:
        return (parts[0], size, parts[2])
    return (parts[0], size)


def _file_types() -> list:
    """读取文件对话框可选类型（label:pattern，逗号分隔）。"""
    raw = _cfg.get("files", "excel_types",
                   fallback="Excel 文件:*.xlsx *.xls,所有文件:*.*")
    result = []
    for item in raw.split(","):
        item = item.strip()
        if ":" in item:
            label, pattern = item.split(":", 1)
            result.append((label.strip(), pattern.strip()))
    return result


# ---------- CustomTkinter 外观 ----------
APPEARANCE_MODE = _cfg.get("app", "appearance_mode", fallback="system")
COLOR_THEME = _cfg.get("app", "color_theme", fallback="blue")

# ---------- 窗口尺寸 ----------
WINDOW_WIDTH = _cfg.getint("app", "window_width", fallback=1000)
WINDOW_HEIGHT = _cfg.getint("app", "window_height", fallback=680)
WINDOW_MIN_WIDTH = _cfg.getint("app", "window_min_width", fallback=900)
WINDOW_MIN_HEIGHT = _cfg.getint("app", "window_min_height", fallback=600)

# ---------- 侧边栏 ----------
SIDEBAR_WIDTH = _cfg.getint("sidebar", "width", fallback=210)
SIDEBAR_COLLAPSED_WIDTH = _cfg.getint("sidebar", "collapsed_width", fallback=56)
SIDEBAR_HEADER_HEIGHT = _cfg.getint("sidebar", "header_height", fallback=150)
NAV_ROW_HEIGHT = _cfg.getint("sidebar", "nav_row_height", fallback=44)
NAV_ROW_PADY = _cfg.getint("sidebar", "nav_row_pady", fallback=4)
NAV_ICON_TEXT_GAP = _cfg.getint("sidebar", "nav_icon_text_gap", fallback=10)
SIDEBAR_TOGGLE_EXPANDED = _cfg.get("sidebar", "toggle_expanded", fallback="◀")
SIDEBAR_TOGGLE_COLLAPSED = _cfg.get("sidebar", "toggle_collapsed", fallback="▶")
SIDEBAR_OVERLAY_ALPHA = _cfg.getfloat("sidebar", "overlay_alpha", fallback=0.9)
SIDEBAR_OVERLAY_ANIM_STEPS = _cfg.getint("sidebar", "overlay_anim_steps", fallback=8)
SIDEBAR_OVERLAY_ANIM_INTERVAL = _cfg.getint("sidebar", "overlay_anim_interval", fallback=12)
NAV_TEXT_COLOR = _pair("nav", "text_color", ("#222831", "#E8EAF0"))
NAV_HOVER_COLOR = _pair("nav", "hover_color", ("#A9B4C2", "#3E4754"))
NAV_ACTIVE_TEXT_COLOR = _cfg.get("nav", "active_text_color", fallback="#FFFFFF")
NAV_SUBTITLE_COLOR = _pair("nav", "subtitle_color", ("#5A6472", "#9AA4B2"))

# ---------- 字体 ----------
FONT_TITLE = _font("font", "title", ("Microsoft YaHei UI", 18, "bold"))
FONT_NAV = _font("font", "nav", ("Microsoft YaHei UI", 13))
FONT_BODY = _font("font", "body", ("Microsoft YaHei UI", 12))
FONT_SMALL = _font("font", "small", ("Microsoft YaHei UI", 11))

# ---------- 状态栏文案 ----------
STATUS_READY = _cfg.get("status", "ready", fallback="就绪")
STATUS_BUSY = _cfg.get("status", "busy", fallback="处理中，请稍候…")

# ---------- 统计占位文案 ----------
STATS_PLACEHOLDER_TEXT = _cfg.get(
    "stats", "placeholder_text",
    fallback="默认统计项：预留（请在代码 calculate_default_stats 中自定义）")

# ---------- 应用信息 ----------
APP_TITLE = _cfg.get("app", "title", fallback="数据匹配与统计工具")
APP_SUBTITLE = _cfg.get("app", "subtitle",
                        fallback="Excel 多表左连接匹配 · 动态过滤 · 统计导出")

# ---------- 文件类型 ----------
EXCEL_FILE_TYPES = _file_types()

# ---------- 对话框 ----------
SHEET_PICKER_WIDTH = _cfg.getint("dialog", "sheet_picker_width", fallback=400)
SHEET_PICKER_HEIGHT = _cfg.getint("dialog", "sheet_picker_height", fallback=460)

# ---------- 文件加载页工作表行配色 ----------
FILE_ROW_TEXT_COLOR = _pair("file_list", "text_color", ("#1A1A1A", "#F2F2F2"))
FILE_ROW_SUBTEXT_COLOR = _pair("file_list", "subtext_color", ("#5A6472", "#AEB6C2"))
FILE_ROW_HOVER_COLOR = _pair("file_list", "hover_color", ("#D5DCE4", "#39424F"))

# ---------- 数据预览 ----------
PREVIEW_ROWS = _cfg.getint("preview", "rows", fallback=50)
PREVIEW_WIDTH = _cfg.getint("preview", "dialog_width", fallback=680)
PREVIEW_HEIGHT = _cfg.getint("preview", "dialog_height", fallback=480)
PREVIEW_AUTO_SHOW = _cfg.getboolean("preview", "auto_show", fallback=True)
PREVIEW_AUTO_SHOW_COUNT = _cfg.getint("preview", "auto_show_count", fallback=1)

# ---------- 右键菜单批量操作确认 ----------
MENU_CONFIRM_THRESHOLD = _cfg.getint("context_menu", "multi_confirm_threshold", fallback=5)
MENU_FOLDER_CONFIRM_THRESHOLD = _cfg.getint(
    "context_menu", "folder_confirm_threshold", fallback=MENU_CONFIRM_THRESHOLD)

# ---------- 日志 ----------
LOG_ENABLED = _cfg.getboolean("log", "enabled", fallback=True)
LOG_LEVEL = _cfg.get("log", "level", fallback="INFO")
