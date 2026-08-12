"""4 个功能区页面（视图层）。

每个页面只负责控件布局、取值与状态刷新，
具体的业务逻辑通过调用控制器（DataMatcherApp）的方法完成。
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import customtkinter as ctk

from app import config

if TYPE_CHECKING:
    from app.gui import DataMatcherApp


class FilePage(ctk.CTkFrame):
    """文件加载区：添加/移除文件，展示已加载文件列表。"""

    def __init__(self, master, app: "DataMatcherApp", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._selected_paths: set = set()  # 当前选中的文件路径

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 标题
        ctk.CTkLabel(self, text="文件加载", font=config.FONT_TITLE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 操作按钮行
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="＋ 添加文件", command=self.app.on_add_files,
                      font=config.FONT_BODY, width=120).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="移除选中", command=self.app.on_remove_selected,
                      font=config.FONT_BODY, width=120, fg_color="gray35",
                      hover_color="gray45").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(btn_frame, text="（点击文件行可选中，第一个文件为匹配基准表）",
                     font=config.FONT_SMALL, text_color="gray60").pack(side="left", padx=(10, 0))

        # 文件列表（可滚动）
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.refresh()

    # ---- 列表刷新 ----
    def refresh(self) -> None:
        """根据 AppState 重新渲染文件列表。"""
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._selected_paths.clear()

        paths = self.app.state.file_paths
        if not paths:
            ctk.CTkLabel(self.list_frame, text="尚未添加文件", font=config.FONT_BODY,
                         text_color="gray60").grid(row=0, column=0, pady=40)
            return

        for index, path in enumerate(paths):
            self._create_row(index, path)

    def _create_row(self, index: int, path: str) -> None:
        """创建单个文件行：可选中文件名 + 路径小字 + 单独移除按钮。"""
        row = ctk.CTkFrame(self.list_frame, corner_radius=8)
        row.grid(row=index, column=0, sticky="ew", pady=4)
        row.grid_columnconfigure(0, weight=1)

        # 文件名按钮：点击切换选中状态（用于“移除选中”）
        name_btn = ctk.CTkButton(
            row, text=f"{index + 1}. {os.path.basename(path)}", font=config.FONT_BODY,
            fg_color="transparent", hover_color="gray30", anchor="w")
        name_btn.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=4)
        # 先创建按钮，再绑定点击命令（闭包捕获 path 与按钮自身）
        name_btn.configure(command=lambda: self._toggle_select(path, name_btn))

        # 完整路径小字提示
        ctk.CTkLabel(row, text=path, font=config.FONT_SMALL, text_color="gray60",
                     anchor="w").grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(0, 4))

        # 单独移除按钮
        ctk.CTkButton(row, text="✕", width=34, fg_color="gray35", hover_color="firebrick3",
                      command=lambda p=path: self.app.on_remove_file(p)).grid(
            row=0, column=1, rowspan=2, padx=(0, 8), pady=4)

    def _toggle_select(self, path: str, btn) -> None:
        """切换某文件行的选中状态。"""
        if path in self._selected_paths:
            self._selected_paths.discard(path)
            btn.configure(fg_color="transparent", hover_color="gray30")
        else:
            self._selected_paths.add(path)
            btn.configure(fg_color="gray30", hover_color="gray40")

    @property
    def selected_paths(self) -> list:
        """当前选中文件的路径列表。"""
        return list(self._selected_paths)


class MatchPage(ctk.CTkFrame):
    """匹配配置区：选择唯一标识项并执行左连接匹配。"""

    def __init__(self, master, app: "DataMatcherApp", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)

        # 标题
        ctk.CTkLabel(self, text="匹配配置", font=config.FONT_TITLE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 15))

        # 主键选择
        key_frame = ctk.CTkFrame(self)
        key_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        key_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(key_frame, text="唯一标识项（主键）", font=config.FONT_BODY).grid(
            row=0, column=0, sticky="w", padx=14, pady=14)
        self.key_combo = ctk.CTkComboBox(
            key_frame, values=[], state="readonly", width=340, font=config.FONT_BODY)
        self.key_combo.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=14)

        # 说明
        ctk.CTkLabel(self, text="以第一个加载的表格为基准，对其余表格按主键做左连接匹配。\n"
                               "若其他表格缺少所选列，将提示具体文件与列名。",
                     font=config.FONT_SMALL, text_color="gray60", justify="left").grid(
            row=2, column=0, sticky="w", padx=20, pady=6)

        # 执行按钮
        ctk.CTkButton(self, text="▶ 执行匹配", command=self.app.on_execute_merge,
                      font=config.FONT_BODY, height=40).grid(
            row=3, column=0, sticky="ew", padx=20, pady=(18, 6))

        # 匹配结果信息
        self.info_label = ctk.CTkLabel(self, text="", font=config.FONT_BODY,
                                       justify="left", anchor="w", wraplength=660)
        self.info_label.grid(row=4, column=0, sticky="w", padx=20, pady=6)

    def update_columns(self, columns: list) -> None:
        """刷新主键下拉框候选（表头并集）。"""
        self.key_combo.configure(values=list(columns))
        self.key_combo.set("")

    def get_key(self) -> str:
        """读取当前选中的主键。"""
        return self.key_combo.get().strip()

    def show_info(self, text: str) -> None:
        self.info_label.configure(text=text)


class FilterPage(ctk.CTkFrame):
    """过滤筛选区：输入 pandas 查询语句动态过滤。"""

    def __init__(self, master, app: "DataMatcherApp", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 标题
        ctk.CTkLabel(self, text="过滤筛选", font=config.FONT_TITLE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 语法说明
        ctk.CTkLabel(self, text="Pandas 查询语句（字段名需与表头一致，字符串值需加引号），例如：\n"
                               "销售额 > 1000 and 地区 == '华东'",
                     font=config.FONT_SMALL, text_color="gray60", justify="left").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        # 查询输入框
        self.query_box = ctk.CTkTextbox(self, height=90, font=config.FONT_BODY, wrap="word")
        self.query_box.grid(row=2, column=0, sticky="nsew", padx=20, pady=8)

        # 操作按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(8, 6))
        ctk.CTkButton(btn_frame, text="✔ 应用过滤", command=self.app.on_apply_filter,
                      font=config.FONT_BODY, width=130).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="重置过滤", command=self.app.on_reset_filter,
                      font=config.FONT_BODY, width=130, fg_color="gray35",
                      hover_color="gray45").pack(side="left")

        # 过滤结果信息
        self.info_label = ctk.CTkLabel(self, text="", font=config.FONT_BODY,
                                       justify="left", anchor="w", wraplength=660)
        self.info_label.grid(row=4, column=0, sticky="w", padx=20, pady=6)

    def get_query(self) -> str:
        """读取查询语句。"""
        return self.query_box.get("1.0", "end").strip()

    def set_query(self, text: str) -> None:
        """设置查询语句。"""
        self.query_box.delete("1.0", "end")
        self.query_box.insert("1.0", text)

    def show_info(self, text: str) -> None:
        self.info_label.configure(text=text)


class StatsExportPage(ctk.CTkFrame):
    """统计与导出区：统计占位 + 结果导出。"""

    def __init__(self, master, app: "DataMatcherApp", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)

        # 标题
        ctk.CTkLabel(self, text="统计与导出", font=config.FONT_TITLE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 15))

        # 统计占位卡片
        stats_card = ctk.CTkFrame(self)
        stats_card.grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        stats_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(stats_card, text="默认统计项", font=config.FONT_BODY, anchor="w").grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 4))
        ctk.CTkLabel(stats_card, text=config.STATS_PLACEHOLDER_TEXT, font=config.FONT_SMALL,
                     text_color="gray60", anchor="w", justify="left", wraplength=620).grid(
            row=1, column=0, sticky="w", padx=14, pady=(0, 14))

        # 导出按钮
        ctk.CTkButton(self, text="💾 导出结果", command=self.app.on_export,
                      font=config.FONT_BODY, height=40).grid(
            row=2, column=0, sticky="ew", padx=20, pady=(18, 6))

        # 导出反馈信息
        self.info_label = ctk.CTkLabel(self, text="", font=config.FONT_BODY,
                                       justify="left", anchor="w", wraplength=660)
        self.info_label.grid(row=3, column=0, sticky="w", padx=20, pady=6)

    def show_info(self, text: str) -> None:
        self.info_label.configure(text=text)
