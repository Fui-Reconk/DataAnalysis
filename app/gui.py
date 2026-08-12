"""DataMatcherApp：应用主控制器。

负责创建主窗口、左侧导航栏、页面调度，
并编排各引擎模块完成 加载/匹配/过滤/导出 流程，
同时统一更新状态栏与进度条，保证耗时操作时界面不卡死。
"""
from __future__ import annotations

import os

import customtkinter as ctk
from tkinter import filedialog, messagebox

from app import config
from app.data_loader import load_excel, scan_columns
from app.exporter import default_export_name, export_excel
from app.filter_engine import apply_query
from app.merge_engine import left_join
from app.pages import FilePage, MatchPage, FilterPage, StatsExportPage
from app.state import AppState
from app.stats import calculate_default_stats


class DataMatcherApp:
    """数据匹配与统计工具主控制器。"""

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.state = AppState()

        # 窗口基础设置
        self.root.title(config.APP_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # 构建界面
        self._build_sidebar()
        self._build_content()

        # 默认显示第一个功能区
        self._show_page(0)

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        """构建左侧导航栏。

        交互模型：
          - 默认展开（标题 + 图标 + 完整文字），主界面内容固定布局。
          - 侧边栏最下方开合按钮控制 展开⇄折叠，点击直接切换（无动画）。
          - 折叠状态下悬停侧边栏：半透明浮层快速展开并覆盖主界面
            （仅显示功能分区选项，不含顶部标题；不推动主界面内容）。
          - 导航图标 X 轴以折叠状态居中位置为基准，展开/浮层时保持不变。
          - 顶部标题区固定占位高度，折叠时内容隐藏但占位保留，导航图标 Y 轴不变。
        """
        # 侧边栏专用字体（固定字号）
        self.font_sidebar_title = ctk.CTkFont(family="Microsoft YaHei UI", size=18, weight="bold")
        self.font_sidebar_nav = ctk.CTkFont(family="Microsoft YaHei UI", size=13)
        self.font_sidebar_small = ctk.CTkFont(family="Microsoft YaHei UI", size=11)

        # 侧边栏宽度目标（首次 <Configure> 会立即修正为响应式实际值）
        self._width_collapsed = config.SIDEBAR_COLLAPSED_WIDTH
        self._width_expanded = config.SIDEBAR_WIDTH

        self.sidebar = ctk.CTkFrame(self.root, width=self._width_expanded, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # 顶部标题区：固定占位高度容器（折叠时内容隐藏但高度保留，导航图标Y轴不变）
        self.sidebar_header = ctk.CTkFrame(
            self.sidebar, height=config.SIDEBAR_HEADER_HEIGHT, fg_color="transparent")
        self.sidebar_header.grid(row=0, column=0, sticky="ew")
        self.sidebar_header.grid_propagate(False)
        self.sidebar_header.grid_columnconfigure(0, weight=1)

        # 标题区内容：展开时显示，折叠时整体隐藏（含其图标）
        self.nav_icon_label = ctk.CTkLabel(self.sidebar_header, text="📊",
                                           font=self.font_sidebar_title)
        self.nav_title_label = ctk.CTkLabel(self.sidebar_header, text=config.APP_TITLE,
                                            font=self.font_sidebar_title, wraplength=170)
        self.nav_subtitle_label = ctk.CTkLabel(
            self.sidebar_header, text=config.APP_SUBTITLE, font=self.font_sidebar_small,
            text_color=config.NAV_SUBTITLE_COLOR, wraplength=170, justify="center")

        # 功能分区导航项
        self.nav_items = [
            ("📂", "文件加载", 0),
            ("🔗", "匹配配置", 1),
            ("🔍", "过滤筛选", 2),
            ("📈", "统计与导出", 3),
        ]
        self._nav_rows = []  # 侧边栏导航项（元素: 行信息字典）
        for row, (icon, text, index) in enumerate(self.nav_items, start=1):
            self._build_nav_row(self.sidebar, row, icon, text, index, self._nav_rows)

        # 底部开合按钮：展开时 ◀（置于最右侧），折叠时 ▶；点击直接切换（无动画）
        self._toggle_btn = ctk.CTkButton(
            self.sidebar, text=config.SIDEBAR_TOGGLE_EXPANDED, font=self.font_sidebar_nav,
            width=28, height=28, corner_radius=8,
            fg_color="transparent", hover_color=config.NAV_HOVER_COLOR,
            text_color=config.NAV_TEXT_COLOR, command=self._toggle_sidebar)
        self._toggle_btn.grid(row=len(self.nav_items) + 2, column=0, sticky="se", padx=6, pady=8)
        # 弹性空白行：将开合按钮固定到侧边栏底部
        self.sidebar.grid_rowconfigure(len(self.nav_items) + 1, weight=1)

        # 半透明浮层状态
        self._overlay: ctk.CTkToplevel | None = None  # 浮层窗口（首次悬停时懒创建）
        self._overlay_rows = []         # 浮层内导航项（与侧边栏一致）
        self._overlay_visible = False
        self._overlay_width = self._width_collapsed
        self._overlay_hide_job = None   # 待执行的浮层收起判定任务
        self._overlay_anim_token = 0    # 浮层动画令牌，用于取消未完成的动画

        self._resize_job = None         # 待执行的窗口缩放任务
        self._current_page = 0
        self._expanded = True           # 默认展开

        # 悬停事件：仅功能分区按钮触发半透明浮层展开
        # 标题区、侧边栏空白、开合按钮不触发
        for info in self._nav_rows:
            self._bind_nav_hover_events(info["frame"])
            self._bind_nav_hover_events(info["icon_label"])
            self._bind_nav_hover_events(info["text_label"])

        # 应用初始展开内容
        self._apply_sidebar_content(True)

    def _build_nav_row(self, master, row, icon, text, index, container) -> None:
        """构建一个导航项行。

        图标列宽度固定为折叠栏宽度（图标在列内居中），展开时文字显示在图标
        右侧，折叠时文字隐藏。因此图标 X 轴位置在展开/折叠状态下完全一致。
        """
        frame = ctk.CTkFrame(master, fg_color="transparent", corner_radius=8,
                             height=config.NAV_ROW_HEIGHT)
        frame.grid(row=row, column=0, sticky="ew", pady=config.NAV_ROW_PADY)
        frame.grid_propagate(False)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=0)  # 图标列：固定宽度（折叠栏宽度）
        frame.grid_columnconfigure(1, weight=1)  # 文字列：占满剩余宽度

        icon_label = ctk.CTkLabel(frame, text=icon, font=self.font_sidebar_nav,
                                  text_color=config.NAV_TEXT_COLOR,
                                  width=self._width_collapsed, anchor="center")
        icon_label.grid(row=0, column=0, sticky="w")

        text_label = ctk.CTkLabel(frame, text=text, font=self.font_sidebar_nav,
                                  text_color=config.NAV_TEXT_COLOR, anchor="w")
        text_label.grid(row=0, column=1, sticky="w",
                        padx=(config.NAV_ICON_TEXT_GAP, 4))

        info = {"frame": frame, "icon_label": icon_label, "text_label": text_label,
                "icon": icon, "text": text, "index": index, "_hover_job": None}
        container.append(info)

        # 行内任意区域点击切换页面；悬停显示背景高亮（非激活项）
        for w in (frame, icon_label, text_label):
            w.bind("<Button-1>", lambda _e, i=index: self._show_page(i))
            self._bind_nav_hover(w, info)

    def _bind_nav_hover(self, widget, info) -> None:
        """为导航行内组件绑定悬停高亮（防抖，避免子组件间抖动）。"""
        widget.bind("<Enter>", lambda _e: self._apply_nav_hover(info, True))
        widget.bind("<Leave>", lambda _e: self._defer_nav_unhover(info))

    def _apply_nav_hover(self, info, hover: bool) -> None:
        """应用/取消导航行悬停背景；激活项始终保持主题色高亮。"""
        if info["index"] == self._current_page:
            return
        info["frame"].configure(fg_color=config.NAV_HOVER_COLOR if hover else "transparent")

    def _defer_nav_unhover(self, info) -> None:
        """延迟取消悬停高亮，避免指针在子组件间移动时闪烁。"""
        if info["_hover_job"] is not None:
            self.root.after_cancel(info["_hover_job"])
        info["_hover_job"] = self.root.after(80, lambda: self._maybe_unhover(info))

    def _maybe_unhover(self, info) -> None:
        """指针已离开该导航行时取消高亮。"""
        info["_hover_job"] = None
        if not self._pointer_in_widget(info["frame"]):
            self._apply_nav_hover(info, False)

    def _pointer_in_widget(self, widget) -> bool:
        """判断鼠标指针当前是否位于指定组件范围内。"""
        x, y = self.root.winfo_pointerxy()
        wx, wy, ww, wh = (widget.winfo_rootx(), widget.winfo_rooty(),
                          widget.winfo_width(), widget.winfo_height())
        return wx <= x <= wx + ww and wy <= y <= wy + wh

    # ------------------------------------------------------------------
    # 侧边栏状态切换（点击开合，无动画）
    # ------------------------------------------------------------------
    def _toggle_sidebar(self) -> None:
        """点击底部按钮：展开⇄折叠，直接呈现结果（无动画）。"""
        self._set_sidebar_expanded(not self._expanded)
        if self._overlay_visible:
            self._hide_overlay()

    def _set_sidebar_expanded(self, expanded: bool) -> None:
        """切换到展开/折叠状态（直接设置宽度，无过渡动画）。"""
        self._expanded = expanded
        target = self._width_expanded if expanded else self._width_collapsed
        self.sidebar.configure(width=target)
        self._apply_sidebar_content(expanded)
        self.sidebar.update_idletasks()

    def _apply_sidebar_content(self, expanded: bool) -> None:
        """根据状态切换标题区与导航项显示内容。"""
        # 顶部标题区：折叠时整体隐藏（含其图标）；容器占位高度保留，导航图标 Y 轴不变
        if expanded:
            self.nav_icon_label.grid(row=0, column=0, pady=(30, 2))
            self.nav_title_label.grid(row=1, column=0, pady=(0, 2))
            self.nav_subtitle_label.grid(row=2, column=0, pady=(0, 24))
        else:
            self.nav_icon_label.grid_remove()
            self.nav_title_label.grid_remove()
            self.nav_subtitle_label.grid_remove()

        # 导航项：展开显示文字（图标列宽度固定，X 轴不动），折叠仅显示居中图标
        for info in self._nav_rows:
            if expanded:
                info["text_label"].grid(row=0, column=1, sticky="w",
                                        padx=(config.NAV_ICON_TEXT_GAP, 4))
            else:
                info["text_label"].grid_remove()

        # 开合按钮箭头：展开 ◀ / 折叠 ▶
        self._toggle_btn.configure(
            text=config.SIDEBAR_TOGGLE_EXPANDED if expanded else config.SIDEBAR_TOGGLE_COLLAPSED)

    # ------------------------------------------------------------------
    # 半透明浮层（折叠状态悬停展开，覆盖主界面，不移动主界面内容）
    # ------------------------------------------------------------------
    def _bind_nav_hover_events(self, widget) -> None:
        """仅功能分区按钮区域悬停时触发半透明浮层展开。"""
        widget.bind("<Enter>", lambda _e: self._on_nav_area_enter())
        widget.bind("<Leave>", lambda _e: self._on_nav_area_leave())

    def _on_nav_area_enter(self) -> None:
        """折叠状态下鼠标进入功能分区按钮区域 → 取消收起，必要时展开浮层。"""
        if not self._expanded:
            # 总是先取消可能挂起的收起任务，避免计时器误收已可见的浮层
            self._cancel_overlay_hide()
            if not self._overlay_visible:
                self._show_overlay()

    def _on_nav_area_leave(self) -> None:
        """折叠状态下离开功能分区按钮区域 → 延迟判定收起浮层。"""
        if not self._expanded:
            self._schedule_overlay_hide()

    def _build_overlay(self) -> None:
        """构建半透明浮层窗口（覆盖主界面左侧，仅显示功能分区选项）。"""
        self._overlay = ctk.CTkToplevel(self.root)
        self._overlay.overrideredirect(True)
        self._overlay.attributes("-topmost", True)
        self._overlay.attributes("-alpha", config.SIDEBAR_OVERLAY_ALPHA)
        self._overlay.withdraw()

        self._overlay_frame = ctk.CTkFrame(self._overlay, corner_radius=0)
        self._overlay_frame.pack(fill="both", expand=True)
        self._overlay_frame.grid_columnconfigure(0, weight=1)

        # 顶部占位（不显示标题内容，仅保持导航图标与折叠栏 Y 轴一致）
        self._overlay_header = ctk.CTkFrame(
            self._overlay_frame, height=config.SIDEBAR_HEADER_HEIGHT, fg_color="transparent")
        self._overlay_header.grid(row=0, column=0, sticky="ew")
        self._overlay_header.grid_propagate(False)

        for row, (icon, text, index) in enumerate(self.nav_items, start=1):
            self._build_nav_row(self._overlay_frame, row, icon, text, index, self._overlay_rows)

        # 浮层底部开合按钮（折叠态显示 ▶，点击恢复展开）
        self._overlay_toggle = ctk.CTkButton(
            self._overlay_frame, text=config.SIDEBAR_TOGGLE_COLLAPSED, font=self.font_sidebar_nav,
            width=28, height=28, corner_radius=8,
            fg_color="transparent", hover_color=config.NAV_HOVER_COLOR,
            text_color=config.NAV_TEXT_COLOR, command=self._toggle_sidebar)
        self._overlay_toggle.grid(row=len(self.nav_items) + 2, column=0, sticky="se",
                                  padx=6, pady=8)
        self._overlay_frame.grid_rowconfigure(len(self.nav_items) + 1, weight=1)

        # 浮层自身悬停事件（移出浮层区域后收起）
        self._bind_overlay_events(self._overlay_frame)
        self._bind_overlay_events(self._overlay_header)
        for info in self._overlay_rows:
            self._bind_overlay_events(info["frame"])
            self._bind_overlay_events(info["icon_label"])
            self._bind_overlay_events(info["text_label"])
        self._bind_overlay_events(self._overlay_toggle)

        # 同步当前选中页高亮到浮层（浮层懒创建，初始时 _overlay_rows 为空，
        # _show_page 之前的高亮调用未覆盖到此处）
        active_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        for info in self._overlay_rows:
            if info["index"] == self._current_page:
                info["frame"].configure(fg_color=active_color)
                info["icon_label"].configure(text_color=config.NAV_ACTIVE_TEXT_COLOR)
                info["text_label"].configure(text_color=config.NAV_ACTIVE_TEXT_COLOR)

        # 窗口原生背景对齐浮层 frame 颜色：动画重绘滞后时不会露出浅色底（白块残影）
        self._overlay.configure(fg_color=self._overlay_frame.cget("fg_color"))

    def _bind_overlay_events(self, widget) -> None:
        widget.bind("<Enter>", lambda _e: self._cancel_overlay_hide())
        widget.bind("<Leave>", lambda _e: self._schedule_overlay_hide())

    def _cancel_overlay_hide(self) -> None:
        """指针回到浮层区域：取消挂起的收起任务。"""
        if self._overlay_hide_job is not None:
            self.root.after_cancel(self._overlay_hide_job)
            self._overlay_hide_job = None

    def _schedule_overlay_hide(self) -> None:
        """延迟执行浮层收起判定，避免在组件间移动时误收起。"""
        if self._overlay_hide_job is not None:
            self.root.after_cancel(self._overlay_hide_job)
        self._overlay_hide_job = self.root.after(150, self._maybe_hide_overlay)

    def _maybe_hide_overlay(self) -> None:
        """指针已离开浮层与所有功能分区按钮区域时执行收起。"""
        self._overlay_hide_job = None
        if not self._overlay_visible:
            return
        if self._cursor_over_overlay() or self._cursor_on_nav_rows():
            return
        self._hide_overlay()

    def _cursor_on_nav_rows(self) -> bool:
        """判断鼠标指针当前是否位于侧边栏任一功能分区按钮或开合按钮上。"""
        for info in self._nav_rows:
            if self._pointer_in_widget(info["frame"]):
                return True
        return False

    def _cursor_over_overlay(self) -> bool:
        """判断鼠标指针当前是否位于浮层窗口范围内。"""
        if self._overlay is None:
            return False
        return self._pointer_in_widget(self._overlay)

    def _show_overlay(self) -> None:
        """显示半透明浮层：直接以全宽快速淡入（覆盖主界面，不移动其内容）。

        不做"从窄变宽"的窗口缩放动画——Windows 下快速缩放窗口会产生
        重绘滞后（白色残影）与 emoji 字形渲染失败（白色方块），这正是
        之前"白块"反复出现的原因。改为固定尺寸 + 透明度淡入，从根上
        杜绝一切缩放类重绘瑕疵。
        """
        if self._expanded or self._overlay_visible:
            return
        # 防御：确保没有待处理的收起计时器
        self._cancel_overlay_hide()
        if self._overlay is None:
            self._build_overlay()
        assert self._overlay is not None
        # 先标为可见再做事，防止重入
        self._overlay_visible = True
        # 直接以全宽定位：文字/图标始终完整渲染，窗口尺寸保持不变
        self._set_overlay_geometry(self._width_expanded)
        self._sync_overlay_text(self._width_expanded)
        # 从不透明(0)快速淡入到半透明效果
        self._overlay.attributes("-alpha", 0.0)
        self._overlay.deiconify()
        self._overlay.lift()
        self._animate_overlay_alpha(config.SIDEBAR_OVERLAY_ALPHA)

    def _sync_overlay_text(self, width_logical: int) -> None:
        """浮层文字标签随宽度显隐：未展开到全宽时不显示文字。

        原缩放动画期间窗口比文字所需宽度窄，白色文字会被窗口右缘裁切，
        看起来就像白色块块在滑动；因此只有宽度达到全展开值才显示文字。
        """
        show = width_logical >= self._width_expanded
        if self._overlay is None:
            return
        for info in self._overlay_rows:
            label = info["text_label"]
            if show:
                label.grid(row=0, column=1, sticky="w",
                           padx=(config.NAV_ICON_TEXT_GAP, 4))
            else:
                label.grid_remove()

    def _hide_overlay(self) -> None:
        """收起半透明浮层：快速淡出后隐藏。"""
        self._cancel_overlay_hide()  # 防御：避免挂起的收起任务与新动画冲突
        if not self._overlay_visible:
            return
        assert self._overlay is not None
        self._overlay_visible = False
        self._animate_overlay_alpha(0.0, on_complete=self._overlay.withdraw)

    def _animate_overlay_alpha(self, target_alpha: float, on_complete=None) -> None:
        """浮层透明度过渡动画（快速淡入/淡出，令牌取消机制避免并发冲突）。

        只改变窗口透明度，不改变窗口尺寸，因此不会触发缩放重绘。
        """
        self._overlay_anim_token += 1
        token = self._overlay_anim_token
        start = float(self._overlay.attributes("-alpha"))
        steps = config.SIDEBAR_OVERLAY_ANIM_STEPS

        def tick(step: int) -> None:
            if token != self._overlay_anim_token:
                return  # 有更新的动画，取消本次
            if step > steps:
                return
            alpha = start + (target_alpha - start) * step / steps
            if step == steps:
                alpha = target_alpha
            self._overlay.attributes("-alpha", max(0.0, min(1.0, alpha)))
            if step < steps:
                self.root.after(config.SIDEBAR_OVERLAY_ANIM_INTERVAL, lambda: tick(step + 1))
            elif on_complete is not None:
                on_complete()

        tick(1)

    def _set_overlay_geometry(self, width_logical: int) -> None:
        """以侧边栏为基准定位浮层，并钳制在根窗口范围内（不超出界面）。

        CTkToplevel 的 geometry("WxH+X+Y") 会对其中的 W/H 再次应用 widget
        scaling，因此传入的是*逻辑*宽高（X/Y 为屏幕物理坐标，不缩放）。
        """
        self._overlay_width = width_logical
        assert self._overlay is not None
        scale = self.sidebar._apply_widget_scaling(1.0)

        x = self.sidebar.winfo_rootx()
        y = self.sidebar.winfo_rooty()
        # CTkToplevel 内部自行缩放 W/H → 传入逻辑值
        w_logical = width_logical
        h_logical = int(self.sidebar.winfo_height() / scale)

        # 钳制：保证最终物理尺寸不超出根窗口
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        max_w_phys = root_x + self.root.winfo_width() - x
        max_h_phys = root_y + self.root.winfo_height() - y
        w_logical = min(w_logical, max(1, int(max_w_phys / scale)))
        h_logical = min(h_logical, max(1, int(max_h_phys / scale)))

        self._overlay.geometry(f"{w_logical}x{h_logical}+{x}+{y}")

    def _build_content(self) -> None:
        """构建右侧内容区：页面容器 + 底部状态栏。"""
        content = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        # 页面容器（各功能区页面在此渲染，切换时隐藏其他页）
        self.page_container = ctk.CTkFrame(content, fg_color="transparent")
        self.page_container.grid(row=0, column=0, sticky="nsew")
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)

        # 实例化 4 个功能区页面
        self.pages = [
            FilePage(self.page_container, self),
            MatchPage(self.page_container, self),
            FilterPage(self.page_container, self),
            StatsExportPage(self.page_container, self),
        ]

        # 底部状态栏 + 进度条（常驻，所有页面可见）
        status_frame = ctk.CTkFrame(content, corner_radius=0)
        status_frame.grid(row=1, column=0, sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)

        self.status_var = ctk.StringVar(value=config.STATUS_READY)
        ctk.CTkLabel(status_frame, textvariable=self.status_var,
                     font=config.FONT_SMALL, anchor="w").grid(
            row=0, column=0, sticky="w", padx=14, pady=8)

        self.progress = ctk.CTkProgressBar(status_frame, mode="indeterminate", width=220)
        self.progress.grid(row=0, column=1, sticky="e", padx=14, pady=8)
        self.progress.set(0)

    def _show_page(self, index: int) -> None:
        """切换功能区页面：隐藏全部页面，仅显示选中页，并高亮导航项。"""
        self._current_page = index
        for i, page in enumerate(self.pages):
            if i == index:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()

        # 激活项常驻主题色高亮（白字保证对比度），未激活项保持透明底 + 高对比文字
        active_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        for rows in (self._nav_rows, self._overlay_rows):
            for info in rows:
                if info["index"] == index:
                    info["frame"].configure(fg_color=active_color)
                    info["icon_label"].configure(text_color=config.NAV_ACTIVE_TEXT_COLOR)
                    info["text_label"].configure(text_color=config.NAV_ACTIVE_TEXT_COLOR)
                else:
                    info["frame"].configure(fg_color="transparent")
                    info["icon_label"].configure(text_color=config.NAV_TEXT_COLOR)
                    info["text_label"].configure(text_color=config.NAV_TEXT_COLOR)

    # ------------------------------------------------------------------
    # 状态栏 / 进度条工具
    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        """更新状态栏文字并强制刷新 UI。"""
        self.status_var.set(text)
        self.root.update_idletasks()

    def start_progress(self) -> None:
        self.progress.start()

    def stop_progress(self) -> None:
        self.progress.stop()
        self.progress.set(0)

    # ------------------------------------------------------------------
    # 文件加载
    # ------------------------------------------------------------------
    def on_add_files(self) -> None:
        """选择并加载多个 Excel 文件（自动去重，读取失败则跳过并提示）。"""
        paths = filedialog.askopenfilenames(title="选择 Excel 文件",
                                            filetypes=config.EXCEL_FILE_TYPES)
        if not paths:
            return

        # 过滤已存在的文件，避免重复加载
        new_paths = [p for p in paths if p not in self.state.file_paths]
        added, failed = [], []

        self.start_progress()
        try:
            for path in new_paths:
                self.set_status(f"正在读取：{os.path.basename(path)} …")
                try:
                    df = load_excel(path)
                except Exception as exc:  # noqa: BLE001 —— 读取失败需逐个提示并跳过
                    failed.append((path, str(exc)))
                    continue
                self.state.dataframes[path] = df
                self.state.file_paths.append(path)
                added.append(path)
                self.root.update_idletasks()
        finally:
            self.stop_progress()

        # 文件集合变化后：重扫表头、使旧匹配结果失效、刷新页面
        self._rescan_columns()
        self._invalidate_result()
        self.pages[0].refresh()
        self._refresh_match_page()

        if failed:
            detail = "\n".join(f"• {os.path.basename(p)}：{e}" for p, e in failed)
            messagebox.showwarning("部分文件读取失败", f"以下文件读取失败，已跳过：\n{detail}")

        if added:
            self.set_status(f"已加载 {len(added)} 个文件，当前共 {len(self.state.file_paths)} 个。")
        else:
            self.set_status(config.STATUS_READY)

    def on_remove_selected(self) -> None:
        """移除文件列表中当前选中的文件。"""
        selected = self.pages[0].selected_paths
        if not selected:
            messagebox.showinfo("提示", "请先在文件列表中点击选中要移除的文件。")
            return
        for path in selected:
            self._remove_file(path)
        self._after_files_changed(f"已移除 {len(selected)} 个文件。")

    def on_remove_file(self, path: str) -> None:
        """移除单个文件。"""
        self._remove_file(path)
        self._after_files_changed(f"已移除：{os.path.basename(path)}")

    def _remove_file(self, path: str) -> None:
        """从状态中移除指定文件。"""
        if path in self.state.file_paths:
            self.state.file_paths.remove(path)
        self.state.dataframes.pop(path, None)

    def _after_files_changed(self, status_text: str) -> None:
        """文件集合变化后的统一刷新流程。"""
        self._rescan_columns()
        self._invalidate_result()
        self.pages[0].refresh()
        self._refresh_match_page()
        self.set_status(status_text)

    def _rescan_columns(self) -> None:
        """重新扫描全部表头并集。"""
        self.state.column_union = scan_columns(self.state.file_paths, self.state.dataframes)

    def _refresh_match_page(self) -> None:
        """刷新匹配页主键下拉框。"""
        self.pages[1].update_columns(self.state.column_union)

    def _invalidate_result(self) -> None:
        """文件集合变化时，使旧的匹配/过滤结果失效并清空相关提示。"""
        self.state.merged_df = None
        self.state.filtered_df = None
        self.pages[1].show_info("")
        self.pages[2].set_query("")
        self.pages[2].show_info("")
        self.pages[3].show_info("")

    # ------------------------------------------------------------------
    # 匹配
    # ------------------------------------------------------------------
    def on_execute_merge(self) -> None:
        """执行左连接匹配（以第一个文件为基准表）。"""
        key = self.pages[1].get_key()
        if not key:
            messagebox.showwarning("提示", "请先选择唯一标识项。")
            return
        if len(self.state.file_paths) < 2:
            messagebox.showwarning("提示", "至少需要添加两个表格才能执行匹配。")
            return

        self.state.key_column = key

        self.start_progress()
        self.set_status("正在执行左连接匹配，数据量较大时请耐心等待…")
        try:
            try:
                merged = left_join(self.state.dataframes, self.state.file_paths, key)
            except (ValueError, KeyError) as exc:
                messagebox.showerror("匹配失败", str(exc))
                return
            self.state.merged_df = merged
            self.state.filtered_df = merged.copy()
        finally:
            self.stop_progress()

        rows, cols = merged.shape
        base_rows = len(self.state.dataframes[self.state.file_paths[0]])
        self.pages[1].show_info(
            f"✔ 匹配完成：基准表 {base_rows} 行，合并后 {rows} 行 × {cols} 列。\n"
            f"主键「{key}」；重复列名已按文件序号加后缀区分。")
        self.pages[2].show_info(f"当前数据：{rows} 行 × {cols} 列（匹配后全量数据）")
        self.set_status("匹配完成，可进行过滤或导出。")

    # ------------------------------------------------------------------
    # 过滤
    # ------------------------------------------------------------------
    def on_apply_filter(self) -> None:
        """对合并结果应用用户输入的条件过滤。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行过滤。")
            return

        query = self.pages[2].get_query()
        if not query:
            messagebox.showinfo("提示", "请输入过滤条件，例如：销售额 > 1000 and 地区 == '华东'")
            return

        self.start_progress()
        self.set_status("正在应用过滤条件…")
        try:
            try:
                result = apply_query(self.state.merged_df, query)
            except Exception as exc:  # noqa: BLE001 —— 过滤语法错误需弹窗提示，不崩溃
                messagebox.showerror("过滤失败", f"过滤语句解析失败：\n{exc}\n\n请检查字段名与语法。")
                return
            self.state.filtered_df = result
        finally:
            self.stop_progress()

        total = len(self.state.merged_df)
        rows = len(result)
        self.pages[2].show_info(f"✔ 过滤完成：{total} 行 → {rows} 行，已过滤 {total - rows} 行。")
        self.set_status(f"过滤完成：{rows}/{total} 行。")

    def on_reset_filter(self) -> None:
        """重置过滤，恢复为匹配后的全量数据。"""
        if self.state.merged_df is None:
            return
        self.state.filtered_df = self.state.merged_df.copy()
        self.pages[2].set_query("")
        rows = len(self.state.merged_df)
        self.pages[2].show_info(f"已重置，当前为匹配后全量数据：{rows} 行。")
        self.set_status("已重置过滤。")

    # ------------------------------------------------------------------
    # 统计与导出
    # ------------------------------------------------------------------
    def on_export(self) -> None:
        """导出最终结果（Sheet1 数据 / Sheet2 统计）到 Excel。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行导出。")
            return

        # 导出的数据：优先使用过滤后的结果，未过滤则用合并结果
        data_df = self.state.filtered_df if self.state.filtered_df is not None else self.state.merged_df

        # 调用预留统计模块（calculate_default_stats）
        self.start_progress()
        self.set_status("正在计算统计…")
        try:
            try:
                stats_df = calculate_default_stats(data_df)
            except Exception as exc:  # noqa: BLE001 —— 统计逻辑由用户编写，出错需兜底
                messagebox.showerror("统计计算失败", f"calculate_default_stats 执行出错：\n{exc}")
                stats_df = None
        finally:
            self.stop_progress()

        # 选择保存路径（默认文件名：匹配结果_时间戳.xlsx）
        path = filedialog.asksaveasfilename(
            title="保存导出结果",
            defaultextension=".xlsx",
            initialfile=default_export_name(),
            filetypes=[("Excel 文件", "*.xlsx")])
        if not path:
            return

        self.start_progress()
        self.set_status("正在写入 Excel…")
        try:
            try:
                out_path = export_excel(data_df, stats_df, path) # type: ignore
            except Exception as exc:  # noqa: BLE001 —— 写入失败需弹窗提示
                messagebox.showerror("导出失败", f"写入文件失败：\n{exc}")
                return
        finally:
            self.stop_progress()

        self.pages[3].show_info(f"✔ 已导出至：\n{out_path}")
        self.set_status("导出成功。")
        messagebox.showinfo("导出成功", f"结果已保存到：\n{out_path}")
