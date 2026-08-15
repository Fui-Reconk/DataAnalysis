"""OverlayMixin：半透明浮层（折叠状态悬停展开）。

折叠状态下鼠标进入功能分区按钮区域时，快速淡入一个覆盖主界面左侧的
半透明浮层（仅显示功能分区选项，不含顶部标题），移出后延迟判定并淡出收起。
"""
from __future__ import annotations

import customtkinter as ctk

from app import config

# Windows 上禁用 CTkToplevel 的标题栏颜色操纵（CustomTkinter 官方提供的类级开关）。
# 该机制在 __init__ 内部会调用 update() 泵事件循环，并 after(5ms) 调度窗口状态
# 恢复回调——可能在不受控的时机把窗口映射出来，闪现一个标题为 "CTkToplevel"
# 的独立窗口（即用户看到的"新窗口"）。浮层是无边框无标题的半透明窗口，
# 完全不需要这套机制；必须在任何 CTkToplevel 创建前设置。
ctk.CTkToplevel._deactivate_windows_window_header_manipulation = True


class OverlayMixin:
    """半透明浮层：懒创建、淡入淡出动画与移出收起判定。"""

    def _bind_nav_hover_events(self, widget) -> None:
        """仅功能分区按钮区域悬停时触发半透明浮层展开。

        CTk 组件的 bind 默认 add=True（追加），不会覆盖 _build_nav_row
        中已绑定的悬停高亮事件。
        """
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
        """构建半透明浮层窗口（覆盖主界面左侧，仅显示功能分区选项）。

        幂等：浮层窗口只允许存在一个，重复调用直接返回，杜绝"多个浮层"。
        """
        if self._overlay is not None:
            return
        self._overlay = ctk.CTkToplevel(self.root)
        self._overlay.title("")                        # 空标题：任何情况下不显示 "CTkToplevel" 字样
        self._overlay.overrideredirect(True)           # 无边框无标题栏
        self._overlay.attributes("-toolwindow", True)  # 工具窗口：不进任务栏、不进 Alt-Tab
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

        # 应用失焦（切换到其他应用/alt-tab）→ 立即收起浮层，避免置顶窗口
        # 滞留在其他应用上层。Windows 上 Tk 对应用级激活事件有两种写法，
        # 全部绑定以防兼容差异；绑定一次即可（本方法幂等）。
        self.root.bind("<Deactivate>", self._on_app_deactivate)
        self.root.bind("<<Deactivate>>", self._on_app_deactivate)
        self.root.bind("<FocusOut>", self._on_root_focus_out, add="+")
        self._overlay.bind("<Deactivate>", self._on_app_deactivate)
        self._overlay.bind("<<Deactivate>>", self._on_app_deactivate)

    def _bind_overlay_events(self, widget) -> None:
        """浮层内组件悬停：回到浮层取消收起，离开浮层延迟判定收起。

        CTk 组件 bind 默认 add=True（追加），导航行的悬停高亮事件保留。
        """
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
        # 自愈：浮层窗口若已被外部销毁，标记重建（保证始终只有一个浮层）
        if self._overlay is not None and not self._overlay.winfo_exists():
            self._overlay = None
        if self._overlay is None:
            self._build_overlay()
        assert self._overlay is not None
        # 先标为可见再做事，防止重入
        self._overlay_visible = True
        # 直接以全宽定位：文字/图标始终完整渲染，窗口尺寸保持不变
        self._set_overlay_geometry(self._width_expanded)
        self._sync_overlay_text(self._width_expanded)
        # 从不透明(0)快速淡入到半透明效果；
        # deiconify 前先置顶并清零透明度，映射完成后强制刷新，
        # 避免 Windows 分层窗口半映射残留（幽灵浮层/多个浮层）
        self._overlay.attributes("-topmost", True)
        self._overlay.attributes("-alpha", 0.0)
        self._overlay.deiconify()
        self._overlay.lift()
        self._overlay.update_idletasks()
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
        self._animate_overlay_alpha(0.0, on_complete=self._finish_hide)

    def _finish_hide(self) -> None:
        """淡出完成：移除置顶属性并隐藏窗口。

        先取消 -topmost 再 withdraw，避免 Windows 分层置顶窗口在
        取消映射时残留"幽灵窗口"叠在其他应用之上。
        """
        if self._overlay is None or not self._overlay.winfo_exists():
            return
        self._overlay.attributes("-topmost", False)
        self._overlay.withdraw()
        self._overlay.update_idletasks()

    def _hide_overlay_instant(self) -> None:
        """立即隐藏浮层（无动画）：应用失焦/切走时使用，杜绝浮层滞留。

        同时取消进行中的淡入/淡出动画，防止动画回调把窗口再次拉起。
        """
        self._cancel_overlay_hide()
        self._overlay_anim_token += 1  # 取消未完成的透明度动画
        self._overlay_visible = False
        if self._overlay is not None and self._overlay.winfo_exists():
            self._overlay.attributes("-alpha", 0.0)
            self._overlay.attributes("-topmost", False)
            self._overlay.withdraw()

    def _on_app_deactivate(self, event=None) -> None:
        """应用失去激活（alt-tab / 点击其他应用）→ 立即收起浮层。"""
        if self._overlay_visible:
            self._hide_overlay_instant()

    def _on_root_focus_out(self, event=None) -> None:
        """根窗口失去焦点：焦点若落在浮层内（用户正在操作浮层）则保留，否则收起。"""
        if not self._overlay_visible:
            return
        focus = self.root.focus_get()
        if focus is not None and self._overlay is not None:
            widget = focus
            while widget is not None:
                if widget is self._overlay:
                    return  # 焦点在浮层内：不收起（点击浮层按钮/导航项时）
                try:
                    widget = widget.master
                except Exception:
                    break
        self._hide_overlay_instant()

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
