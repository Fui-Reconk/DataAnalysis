"""Mixin 组合基类与共享类型声明。

DataMatcherApp 由多个 Mixin 组合而成（SidebarMixin / OverlayMixin /
ContentMixin / FileOpsMixin / OperationsMixin），各 Mixin 之间会互相引用
彼此定义的属性与方法——运行时通过类的 MRO 解析，功能完全正常，但 IDE /
类型检查器在单独分析每个 Mixin 时无法看到其它 Mixin 的成员，会误报大量
"找不到引用 / 类属性访问错误"。

本模块把这类跨 Mixin 成员集中声明在 AppBase 中，仅供静态分析识别：
  - 属性：只写类型注解、不赋默认值，不会创建共享类属性，不改变运行行为；
  - 方法：桩实现（...），运行时由真正定义它们的 Mixin 经 MRO 覆盖。
"""
from __future__ import annotations

from typing import TypedDict

import customtkinter as ctk

from app.state import AppState


class NavRowInfo(TypedDict):
    """侧边栏 / 浮层中一个导航项行的信息结构。"""

    frame: ctk.CTkFrame
    icon_label: ctk.CTkLabel
    text_label: ctk.CTkLabel
    icon: str
    text: str
    index: int
    _hover_job: str | None


class AppBase:
    """跨 Mixin 共享成员的静态声明（不含运行行为）。"""

    # ---- 控制器 / 状态 ----
    root: ctk.CTk
    state: AppState

    # ---- 侧边栏（SidebarMixin 定义） ----
    sidebar: ctk.CTkFrame
    nav_items: list[tuple[str, str, int]]
    font_sidebar_title: ctk.CTkFont
    font_sidebar_nav: ctk.CTkFont
    font_sidebar_small: ctk.CTkFont
    _nav_rows: list[NavRowInfo]
    _overlay_rows: list[NavRowInfo]
    _width_collapsed: int
    _width_expanded: int
    _current_page: int
    _expanded: bool

    # ---- 半透明浮层（OverlayMixin 定义） ----
    _overlay: ctk.CTkToplevel | None
    _overlay_visible: bool
    _overlay_width: int
    _overlay_hide_job: str | None
    _overlay_anim_token: int

    # ---- 内容区（ContentMixin 定义） ----
    pages: list

    # ---- 跨 Mixin 调用的方法（桩声明，真实实现见各 Mixin） ----
    def set_status(self, text: str) -> None:
        raise NotImplementedError  # 实际由 ContentMixin 实现

    def start_progress(self) -> None:
        raise NotImplementedError  # 实际由 ContentMixin 实现

    def stop_progress(self) -> None:
        raise NotImplementedError  # 实际由 ContentMixin 实现

    def _show_page(self, index: int) -> None:
        raise NotImplementedError  # 实际由 ContentMixin 实现

    def _toggle_sidebar(self) -> None:
        raise NotImplementedError  # 实际由 SidebarMixin 实现

    def _pointer_in_widget(self, widget) -> bool:
        raise NotImplementedError  # 实际由 SidebarMixin 实现

    def _build_nav_row(self, master, row: int, icon: str, text: str,
                       index: int, container: list[NavRowInfo]) -> None:
        raise NotImplementedError  # 实际由 SidebarMixin 实现

    def _bind_nav_hover_events(self, widget) -> None:
        raise NotImplementedError  # 实际由 OverlayMixin 实现

    def _open_preview(self, title: str, df, shift: tuple = (0, 0)):
        raise NotImplementedError  # 实际由 FileOpsMixin 实现

    def _build_overlay(self) -> None:
        raise NotImplementedError  # 实际由 OverlayMixin 实现

    def _hide_overlay(self) -> None:
        raise NotImplementedError  # 实际由 OverlayMixin 实现
