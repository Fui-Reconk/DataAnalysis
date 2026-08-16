"""4 个功能区页面（视图层）。

每个页面只负责控件布局、取值与状态刷新，
具体的业务逻辑通过调用控制器（DataMatcherApp）的方法完成。
"""
from __future__ import annotations

import os
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from app import config
from app.filter_engine import OPS as FILTER_OPS
from app.filter_engine import VALUE_OPS

if TYPE_CHECKING:
    from app.gui import DataMatcherApp


class FilePage(ctk.CTkFrame):
    """文件加载区：添加文件/工作表、从暂存池添加、移除，展示已加载数据源。"""

    def __init__(self, master, app: "DataMatcherApp", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._selected_sources: set = set()  # 当前选中的数据源（(路径, 工作表)）
        self._row_widgets: dict = {}         # (路径, 工作表) -> 行内组件（供选中换肤）
        self._menu_temp_selected = False     # 右键菜单期间是否临时选中了行
        self._menu_vars: list = []           # 菜单勾选变量（保持引用防 GC）

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
        ctk.CTkButton(btn_frame, text="添加工作表", command=self.app.on_add_sheets,
                      font=config.FONT_BODY, width=120).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="移除选中", command=self.app.on_remove_selected,
                      font=config.FONT_BODY, width=110, fg_color="gray35",
                      hover_color="gray45").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(btn_frame, text="（点击行可选中，第一个为匹配基准表；右键更多操作）",
                     font=config.FONT_SMALL, text_color=config.FILE_ROW_SUBTEXT_COLOR).pack(
            side="left", padx=(10, 0))

        # 数据源列表（可滚动）
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.refresh()

    # ---- 列表刷新 ----
    def refresh(self) -> None:
        """根据 AppState 重新渲染数据源列表（每行 = 文件 + 工作表）。"""
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._selected_sources.clear()
        self._row_widgets.clear()

        sources = self.app.state.sources
        if not sources:
            ctk.CTkLabel(self.list_frame, text="尚未添加工作表", font=config.FONT_BODY,
                         text_color=config.FILE_ROW_SUBTEXT_COLOR).grid(
                row=0, column=0, pady=40)
            return

        for index, (path, sheet) in enumerate(sources):
            self._create_row(index, path, sheet)

    def _create_row(self, index: int, path: str, sheet: str) -> None:
        """创建单个数据源行：可选中名称按钮 + 路径小字 + 单独移除按钮。"""
        row = ctk.CTkFrame(self.list_frame, corner_radius=8)
        row.grid(row=index, column=0, sticky="ew", pady=4)
        row.grid_columnconfigure(0, weight=1)

        # 名称按钮：默认高对比文字 + 悬停背景，点击切换选中状态
        name_btn = ctk.CTkButton(
            row, text=f"{index + 1}. {os.path.basename(path)} [{sheet}]",
            font=config.FONT_BODY, fg_color="transparent",
            text_color=config.FILE_ROW_TEXT_COLOR,
            hover_color=config.FILE_ROW_HOVER_COLOR, anchor="w")
        name_btn.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=4)
        name_btn.configure(command=lambda: self._toggle_select(path, sheet))

        # 完整路径小字提示（次级信息，保证可读）
        path_label = ctk.CTkLabel(row, text=f"{path} · 工作表「{sheet}」",
                                  font=config.FONT_SMALL,
                                  text_color=config.FILE_ROW_SUBTEXT_COLOR, anchor="w")
        path_label.grid(row=1, column=0, sticky="w", padx=(10, 6), pady=(0, 4))

        # 单独移除按钮
        ctk.CTkButton(row, text="✕", width=34, fg_color="gray35", hover_color="firebrick3",
                      command=lambda p=path, s=sheet: self.app.on_remove_source(p, s)).grid(
            row=0, column=1, rowspan=2, padx=(0, 8), pady=4)

        # 右键菜单：整行（含名称、路径小字）均可触发
        for w in (row, name_btn, path_label):
            w.bind("<Button-3>", lambda e, p=path, s=sheet: self._show_row_menu(e, p, s))

        self._row_widgets[(path, sheet)] = {
            "frame": row, "btn": name_btn, "path_label": path_label,
        }

    def _show_row_menu(self, event, path: str, sheet: str) -> None:
        """弹出原生右键菜单（tk.Menu + tk_popup）。

        右键在已选中的行上 → 批量操作作用于整个选中；右键在未选中的
        行上 → 独立操作仅作用于该行。当前无任何选中时临时选中该行，
        菜单关闭（轮询监测）后自动取消。
        """
        self._menu_temp_selected = self._begin_menu_selection(path, sheet)
        menu = self._build_row_menu(path, sheet)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        self._watch_menu_close(menu, path, sheet)

    def _watch_menu_close(self, menu, path: str, sheet: str) -> None:
        """轮询监测菜单是否已关闭，关闭后取消临时选中并释放勾选变量。"""
        temp = self._menu_temp_selected

        def check() -> None:
            if not menu.winfo_exists() or not menu.winfo_ismapped():
                self._end_menu_selection(path, sheet, temp)
                self._menu_vars = []
                return
            self.app.root.after(50, check)

        self.app.root.after(50, check)

    def _build_row_menu(self, path: str, sheet: str) -> tk.Menu:
        """构建原生右键菜单：打开/定位/预览、选中管理、设为基准表、重载与移除。

        右键在已选中的行上 → 批量操作作用于整个选中；右键在未选中的
        行上 → 独立操作仅作用于该行。「全选」为开关式勾选；多选时
        「设为基准表」置灰；数量 >1 时菜单项显示计数。
        """
        targets = self._menu_targets(path, sheet)
        count = len(targets)

        def item_label(text: str) -> str:
            return f"{text}（{count}）" if count > 1 else text

        menu = tk.Menu(self, tearoff=0)

        menu.add_command(label=item_label("打开"),
                         command=lambda: self.app.on_open_sources(targets))
        menu.add_command(label=item_label("在文件夹中显示"),
                         command=lambda: self.app.on_show_sources_in_folder(targets))
        menu.add_command(label=item_label("预览"),
                         command=lambda: self.app.on_preview_sources(targets))
        menu.add_separator()

        # 选中管理：勾选变量保存在 self._menu_vars，避免局部变量被 GC
        # 导致 Tcl 变量删除、勾勾无法显示
        selected_var = tk.BooleanVar(value=(path, sheet) in self._selected_sources)
        all_selected = bool(self._row_widgets) and \
            len(self._selected_sources) == len(self._row_widgets)
        all_var = tk.BooleanVar(value=all_selected)
        self._menu_vars = [selected_var, all_var]

        menu.add_checkbutton(label="选中", variable=selected_var,
                             command=lambda: self._toggle_select(path, sheet))
        menu.add_checkbutton(label="全选", variable=all_var,
                             command=self._toggle_select_all)
        menu.add_separator()

        # 设为基准表：仅单个目标时可用，多目标置灰
        menu.add_command(label="设为基准表",
                         state="normal" if count == 1 else "disabled",
                         command=lambda: self.app.on_set_base(targets))
        menu.add_command(label=item_label("重载工作表"),
                         command=lambda: self.app.on_reload_sources(targets))
        # 列名缩写替换（映射见 config.cfg [column_map]）
        if config.COLUMN_ABBR_MAP:
            menu.add_command(label=item_label("替换缩写"),
                             command=lambda: self.app.on_replace_abbr(targets))
        menu.add_separator()

        menu.add_command(label=item_label("移除"),
                         command=lambda: self.app.on_remove_selected(targets))

        return menu

    def _begin_menu_selection(self, path: str, sheet: str) -> bool:
        """当前无任何选中时，临时选中该行（菜单显示期间提供视觉反馈）。

        返回 True 表示菜单关闭后需恢复取消选中。
        """
        key = (path, sheet)
        if self._selected_sources or key in self._selected_sources:
            return False
        self._selected_sources.add(key)
        widgets = self._row_widgets.get(key)
        if widgets is not None:
            self._apply_row_style(widgets, selected=True)
        return True

    def _end_menu_selection(self, path: str, sheet: str, was_temp: bool) -> None:
        """菜单关闭后取消临时选中（仅当曾临时选中时）。"""
        if not was_temp:
            return
        key = (path, sheet)
        self._selected_sources.discard(key)
        widgets = self._row_widgets.get(key)
        if widgets is not None:
            self._apply_row_style(widgets, selected=False)

    def _menu_targets(self, path: str, sheet: str) -> list:
        """右键菜单的操作目标：右键在已选中的行上 → 整个选中（批量）；
        右键在未选中的行上 → 仅该行（独立操作）。"""
        key = (path, sheet)
        if key in self._selected_sources:
            return list(self._selected_sources)
        return [(path, sheet)]

    def _toggle_select_all(self) -> None:
        """全选开关：全部已选时取消全选，否则全选。"""
        if self._row_widgets and len(self._selected_sources) == len(self._row_widgets):
            self._select_none()
        else:
            self._select_all()

    def _select_all(self) -> None:
        """全选：选中全部数据源行。"""
        for key, widgets in self._row_widgets.items():
            self._selected_sources.add(key)
            self._apply_row_style(widgets, selected=True)

    def _select_none(self) -> None:
        """取消全选：清空全部选中。"""
        for key, widgets in self._row_widgets.items():
            self._selected_sources.discard(key)
            self._apply_row_style(widgets, selected=False)

    def _toggle_select(self, path: str, sheet: str) -> None:
        """切换某数据源行的选中状态（选中：主题色背景 + 白字，对比明显）。"""
        key = (path, sheet)
        widgets = self._row_widgets.get(key)
        if widgets is None:
            return
        if key in self._selected_sources:
            self._selected_sources.discard(key)
            self._apply_row_style(widgets, selected=False)
        else:
            self._selected_sources.add(key)
            self._apply_row_style(widgets, selected=True)

    def _apply_row_style(self, widgets: dict, selected: bool) -> None:
        """按选中/未选中应用整行配色（背景 + 文字）。"""
        if selected:
            active = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
            widgets["frame"].configure(fg_color=active)
            widgets["btn"].configure(fg_color="transparent",
                                     text_color=config.NAV_ACTIVE_TEXT_COLOR,
                                     hover_color=active)
            widgets["path_label"].configure(text_color=config.NAV_ACTIVE_TEXT_COLOR)
        else:
            widgets["frame"].configure(fg_color="transparent")
            widgets["btn"].configure(fg_color="transparent",
                                     text_color=config.FILE_ROW_TEXT_COLOR,
                                     hover_color=config.FILE_ROW_HOVER_COLOR)
            widgets["path_label"].configure(text_color=config.FILE_ROW_SUBTEXT_COLOR)

    @property
    def selected_sources(self) -> list:
        """当前选中的数据源（(文件路径, 工作表名)）列表。"""
        return list(self._selected_sources)


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
        ctk.CTkLabel(self, text="以第一个加载的表格为基准，对其余表格按主键做左连接匹配。\n若其他表格缺少所选列，将提示具体文件与列名。",
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
        """刷新主键下拉框候选（基准表的列）。"""
        self.key_combo.configure(values=list(columns))
        self.key_combo.set("")

    def get_key(self) -> str:
        """读取当前选中的主键。"""
        return self.key_combo.get().strip()

    def show_info(self, text: str) -> None:
        self.info_label.configure(text=text)


class FilterPage(ctk.CTkFrame):
    """过滤筛选区：按「列名 + 条件 + 比较值」条件行过滤。

    每行一个条件组（三个控件同一行），可自由增删，默认一行；
    多组条件之间为「并且（AND）」关系。列名候选来自合并结果。
    """

    def __init__(self, master, app: "DataMatcherApp", **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 标题
        ctk.CTkLabel(self, text="过滤筛选", font=config.FONT_TITLE).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # 条件区（可滚动，每行一个条件组）
        self.cond_scroll = ctk.CTkScrollableFrame(self, label_text="过滤条件",
                                                  label_font=config.FONT_SMALL)
        self.cond_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        self.cond_scroll.grid_columnconfigure(0, weight=1)
        self._condition_rows: list = []
        self._columns: list = []
        self._hidden: set = set()  # 隐藏的列名集合（勾选对话框未勾选 = 隐藏）

        # 工具按钮行：添加条件 + 显示列管理
        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 6))
        ctk.CTkButton(tools, text="➕ 添加条件", command=self.add_condition_row,
                      font=config.FONT_BODY, width=130, fg_color="gray35",
                      hover_color="gray45").pack(side="left")
        self.column_btn = ctk.CTkButton(tools, text="☑ 显示列", width=150,
                                        command=self.app.on_choose_visible_columns,
                                        font=config.FONT_BODY)
        self.column_btn.pack(side="left", padx=(10, 0))

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

        self.add_condition_row()

    # ---- 隐藏列（显示列）管理 ----

    def available_columns(self) -> list:
        """全部候选列（含隐藏列，用于条件行下拉框与显示列对话框）。"""
        return list(self._columns)

    def get_hidden(self) -> set:
        """当前隐藏的列名集合。"""
        return set(self._hidden)

    def visible_columns(self) -> list:
        """可见列（全部候选列减去隐藏列），用于过滤结果预览与导出投影。"""
        return [c for c in self._columns if c not in self._hidden]

    def set_hidden(self, hidden: set) -> None:
        """设置隐藏列集合（自动裁掉不在候选列中的名字）并刷新按钮/下拉框。"""
        self._hidden = {c for c in hidden if c in self._columns}
        self._refresh_column_btn()
        self._refresh_row_columns()

    def _refresh_column_btn(self) -> None:
        """刷新「显示列」按钮文案（显示当前隐藏列数）。"""
        n = len(self._hidden)
        self.column_btn.configure(text=f"☑ 显示列（隐藏 {n}）" if n else "☑ 显示列")

    def _refresh_row_columns(self) -> None:
        """刷新条件行列名下拉框候选：只列可见列，隐藏列不出现。"""
        visible = self.visible_columns()
        for row in self._condition_rows:
            current = row["col_combo"].get()
            row["col_combo"].configure(values=list(visible))
            row["col_combo"].set(current if current in visible else "")

    # ---- 条件行管理 ----

    def add_condition_row(self) -> None:
        """新增一行过滤条件（列名 + 条件 + 比较值 + 删除按钮，同一行）。"""
        row = {}
        frame = ctk.CTkFrame(self.cond_scroll, fg_color="transparent")
        frame.grid(row=len(self._condition_rows), column=0, sticky="ew", pady=3)
        for c in range(3):
            frame.grid_columnconfigure(c, weight=1)
        row["frame"] = frame

        col_combo = ctk.CTkComboBox(frame, values=list(self._columns), state="readonly",
                                    font=config.FONT_BODY)
        col_combo.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        row["col_combo"] = col_combo

        op_combo = ctk.CTkComboBox(frame, values=list(FILTER_OPS), state="readonly",
                                   font=config.FONT_BODY,
                                   command=lambda _v, r=row: self._on_op_change(r))
        op_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        row["op_combo"] = op_combo

        value_entry = ctk.CTkEntry(frame, font=config.FONT_BODY, placeholder_text="比较值")
        value_entry.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        row["value_entry"] = value_entry

        del_btn = ctk.CTkButton(frame, text="✕", width=34, font=config.FONT_BODY,
                                fg_color="gray35", hover_color="gray55",
                                command=lambda r=row: self.remove_condition_row(r))
        del_btn.grid(row=0, column=3)
        row["del_btn"] = del_btn

        self._condition_rows.append(row)

    def remove_condition_row(self, row: dict) -> None:
        """删除一行条件（允许删到 0 行，应用时提示先添加）。"""
        if row not in self._condition_rows:
            return
        self._condition_rows.remove(row)
        row["frame"].destroy()
        self._reflow_rows()

    def _reflow_rows(self) -> None:
        """删除行后重新按顺序排列剩余行。"""
        for i, row in enumerate(self._condition_rows):
            row["frame"].grid(row=i, column=0, sticky="ew", pady=3)

    def _on_op_change(self, row: dict) -> None:
        """条件切换为 为空/不为空 时禁用数值框（无需比较值）。"""
        entry = row["value_entry"]
        if row["op_combo"].get() in ("为空", "不为空"):
            entry.configure(state="disabled")
            entry.delete(0, "end")
        else:
            entry.configure(state="normal")

    # ---- 与控制器交互的 API ----

    def update_columns(self, columns: list) -> None:
        """刷新候选列（合并结果列；失效时传空列表），并同步隐藏集与下拉框。"""
        self._columns = [str(c) for c in columns]
        self._hidden = {c for c in self._hidden if c in self._columns}
        self._refresh_column_btn()
        self._refresh_row_columns()

    def get_conditions(self) -> list:
        """读取全部条件；未选/非法时抛 ValueError 并指明行号。

        完全空行（列名与条件均未选）跳过；选 为空/不为空 时 value 置空。
        """
        conditions = []
        for i, row in enumerate(self._condition_rows, start=1):
            col = row["col_combo"].get().strip()
            op = row["op_combo"].get().strip()
            if not col and not op:
                continue  # 未使用的空行，不作为条件
            if not col:
                raise ValueError(f"第 {i} 行：未选择列名。")
            if not op:
                raise ValueError(f"第 {i} 行：未选择条件。")
            value = row["value_entry"].get().strip()
            if op in VALUE_OPS and not value:
                raise ValueError(f"第 {i} 行：条件「{op}」请输入比较值。")
            conditions.append({"column": col, "op": op, "value": value})
        return conditions

    def set_conditions(self, conditions: list) -> None:
        """程序化填充条件（清空现有行后按列表重建；供测试与复用）。"""
        for row in list(self._condition_rows):
            self.remove_condition_row(row)
        if not conditions:
            self.add_condition_row()
            return
        for cond in conditions:
            self.add_condition_row()
            row = self._condition_rows[-1]
            row["col_combo"].set(str(cond.get("column", "")))
            row["op_combo"].set(str(cond.get("op", "")))
            self._on_op_change(row)  # 为空/不为空 → 禁用数值框
            entry = row["value_entry"]
            disabled = entry.cget("state") == "disabled"
            if disabled:
                entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, str(cond.get("value", "")))
            if disabled:
                entry.configure(state="disabled")

    def reset_conditions(self) -> None:
        """清空全部条件行并恢复默认一行（重置 / 数据源失效时调用）。"""
        for row in list(self._condition_rows):
            self.remove_condition_row(row)
        self.add_condition_row()

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
