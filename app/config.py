"""全局配置：主题、字号、窗口尺寸与提示文案。

集中管理 UI 常量，便于统一调整外观与文案。
"""
from __future__ import annotations

# ---------- CustomTkinter 外观 ----------
# 外观模式："system"（跟随系统）/ "light" / "dark"
APPEARANCE_MODE = "system"
# 主题色："blue" / "green" / "dark-blue"
COLOR_THEME = "blue"

# ---------- 窗口尺寸 ----------
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 680
WINDOW_MIN_WIDTH = 900
WINDOW_MIN_HEIGHT = 600

# ---------- 侧边栏 ----------
SIDEBAR_WIDTH = 210                # 展开宽度（默认状态 / 半透明浮层展开宽度）
SIDEBAR_COLLAPSED_WIDTH = 56       # 折叠宽度（点击开合按钮后的窄图标栏宽度）
SIDEBAR_HEADER_HEIGHT = 150        # 顶部标题区固定占位高度（折叠时内容隐藏但占位保留，导航图标Y轴不变）
NAV_ROW_HEIGHT = 44                # 每个导航项占位高度
NAV_ROW_PADY = 4                   # 导航项上下间距
NAV_ICON_TEXT_GAP = 10             # 展开时图标与文字的间距
# 底部开合按钮（点击切换，无动画直接呈现结果）
SIDEBAR_TOGGLE_EXPANDED = "◀"      # 展开状态：箭头朝左，置于侧边栏最右侧
SIDEBAR_TOGGLE_COLLAPSED = "▶"     # 折叠状态：箭头朝右
# 半透明浮层：折叠状态下悬停侧边栏，快速展开并覆盖主界面（不移动主界面内容）
SIDEBAR_OVERLAY_ALPHA = 0.9        # 浮层窗口透明度（0~1，越小越透明）
SIDEBAR_OVERLAY_ANIM_STEPS = 8     # 浮层展开/收起动画步数（加快帧率）
SIDEBAR_OVERLAY_ANIM_INTERVAL = 12  # 浮层淡入/淡出每步间隔（毫秒，加快帧率）
# 导航文字 / 背景对比度（(浅色模式, 深色模式) 二元组，CTk 主题色语法）
# 默认（未悬停）状态下即保证高对比可读，不依赖鼠标移入
NAV_TEXT_COLOR = ("#222831", "#E8EAF0")    # 未激活项文字
NAV_HOVER_COLOR = ("#A9B4C2", "#3E4754")   # 未激活项悬停背景（明显，具备良好标识作用）
NAV_ACTIVE_TEXT_COLOR = "#FFFFFF"          # 激活项文字（主题色底上用白色）
NAV_SUBTITLE_COLOR = ("#5A6472", "#9AA4B2")  # 侧边栏副标题

# ---------- 字体 ----------
# Windows 使用微软雅黑，macOS/Linux 回退到系统中文字体
FONT_TITLE = ("Microsoft YaHei UI", 18, "bold")
FONT_NAV = ("Microsoft YaHei UI", 13)
FONT_BODY = ("Microsoft YaHei UI", 12)
FONT_SMALL = ("Microsoft YaHei UI", 11)

# ---------- 状态栏文案 ----------
STATUS_READY = "就绪"
STATUS_BUSY = "处理中，请稍候…"

# ---------- 统计占位文案 ----------
STATS_PLACEHOLDER_TEXT = "默认统计项：预留（请在代码 calculate_default_stats 中自定义）"

# ---------- 应用信息 ----------
APP_TITLE = "数据匹配与统计工具"
APP_SUBTITLE = "Excel 多表左连接匹配 · 动态过滤 · 统计导出"

# ---------- 文件类型 ----------
EXCEL_FILE_TYPES = [
    ("Excel 文件", "*.xlsx *.xls"),
    ("所有文件", "*.*"),
]
