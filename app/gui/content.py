"""ContentMixin：右侧内容区、页面调度与状态栏/进度条。"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

import customtkinter as ctk

from app import config
from app.gui.base import AppBase
from app.pages import FilePage, FilterPage, MatchPage, StatsExportPage

if TYPE_CHECKING:
    from app.gui.controller import DataMatcherApp


class ContentMixin(AppBase):
    """内容区：构建页面容器、切换功能区页面、更新状态栏与进度条。"""

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

        # 实例化 4 个功能区页面（运行时 self 即 DataMatcherApp，此处仅做类型收窄）
        self.pages = [
            FilePage(self.page_container, cast("DataMatcherApp", self)),
            MatchPage(self.page_container, cast("DataMatcherApp", self)),
            FilterPage(self.page_container, cast("DataMatcherApp", self)),
            StatsExportPage(self.page_container, cast("DataMatcherApp", self)),
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

    def set_status(self, text: str) -> None:
        """更新状态栏文字并强制刷新 UI。"""
        self.status_var.set(text)
        self.root.update_idletasks()

    def start_progress(self) -> None:
        self.progress.start()

    def stop_progress(self) -> None:
        self.progress.stop()
        self.progress.set(0)
