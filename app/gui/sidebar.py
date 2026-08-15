"""SidebarMixin：左侧导航栏的构建与交互。

交互模型：
  - 默认展开（标题 + 图标 + 完整文字），主界面内容固定布局。
  - 侧边栏最下方开合按钮控制 展开⇄折叠，点击直接切换（无动画）。
  - 折叠状态下悬停侧边栏：半透明浮层快速展开并覆盖主界面
    （仅显示功能分区选项，不含顶部标题；不推动主界面内容）。
  - 导航图标 X 轴以折叠状态居中位置为基准，展开/浮层时保持不变。
  - 顶部标题区固定占位高度，折叠时内容隐藏但占位保留，导航图标 Y 轴不变。
"""
from __future__ import annotations

import customtkinter as ctk

from app import config


class SidebarMixin:
    """侧边栏：构建导航项、悬停高亮与展开/折叠切换。"""

    def _build_sidebar(self) -> None:
        """构建左侧导航栏（含标题区、功能分区导航项与底部开合按钮）。"""
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

        # 浮层窗口在启动时预创建（隐藏）：触发时只是淡入既有窗口，
        # 不再"触发时才新建窗口"，杜绝新窗口闪现/任务栏闪烁
        self._build_overlay()

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
