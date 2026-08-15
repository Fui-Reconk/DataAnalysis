"""PreviewDialog：工作表数据预览弹窗。

以表格形式展示数据源（文件+工作表）的前 N 行数据，
支持横向/纵向滚动，表头加粗、列宽按内容自适应。

显示缩放注意点（125% 显示等）：
  - CTk 组件宽高存在"逻辑值/物理值"双轨，CTkToplevel.geometry 会
    对 W/H 再乘一次窗口缩放倍率——因此本弹窗统一使用 Tk 原生
    wm geometry（物理像素直设），彻底绕开双重缩放。
  - ttk.Treeview 是原生控件，行高不随 CTk 缩放自动放大，需按
    显示倍率显式设置 rowheight。
  - 窗口高度按内容请求高度收缩（wm geometry 物理像素），使最后
    一行数据与横向滚动条严丝合缝，消除空白带；与缩放推断无关，
    任何缩放/机器下均精确。
"""
from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk
import pandas as pd

from app import config


def format_cell(value) -> str:
    """单元格显示文本：空值显示为空串，其余转字符串。"""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _text_width(text: str) -> int:
    """估算文本显示宽度（中文按 2 个字符宽计）。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


class PreviewDialog(ctk.CTkToplevel):
    """数据预览弹窗：columns 为表头，rows 为数据行（不含表头）。

    modal=False 时非模态（多表自动预览的后续弹窗）；shift 为相对
    居中的偏移量（级联排列，避免多弹窗完全重叠）；scale 为显示
    缩放倍率（由调用方从侧边栏读取，1.25 = 125% 显示）。
    """

    def __init__(self, master, title: str, columns: list, rows: list,
                 info_text: str = "", modal: bool = True, shift: tuple = (0, 0),
                 scale: float = 1.0):
        super().__init__(master)
        self.columns = list(columns)
        self.rows = list(rows)
        self._scale = max(scale, 0.5)

        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        if modal:
            self.grab_set()  # 模态
        self.attributes("-topmost", True)

        # 居中于主窗口（可带级联偏移）；用 Tk 原生 wm geometry 直接设
        # 物理像素，绕开 CTkToplevel.geometry 对 W/H 的双重缩放
        master.update_idletasks()
        mx, my = master.winfo_rootx(), master.winfo_rooty()
        mw, mh = master.winfo_width(), master.winfo_height()
        w_phys = round(config.PREVIEW_WIDTH * self._scale)
        h_phys = round(config.PREVIEW_HEIGHT * self._scale)
        x = max(mx + (mw - w_phys) // 2 + shift[0], 0)
        y = max(my + (mh - h_phys) // 2 + shift[1], 0)
        self.wm_geometry(f"{w_phys}x{h_phys}+{x}+{y}")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 顶部信息行
        if info_text:
            ctk.CTkLabel(self, text=info_text, font=config.FONT_SMALL,
                         text_color=config.FILE_ROW_SUBTEXT_COLOR, anchor="w").grid(
                row=0, column=0, sticky="ew", padx=14, pady=(12, 4))

        # 表格（ttk.Treeview + 双向滚动条）
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # 可见行数：小表按内容，大表最多占满配置高度内的整行数
        # 行高按显示倍率放大（ttk 原生控件不随 CTk 缩放，需显式设置）
        row_h = max(20, round(26 * self._scale))
        max_visible = max(1, (config.PREVIEW_HEIGHT - 170) // 26)
        visible_rows = max(1, min(len(rows), max_visible))

        tree = ttk.Treeview(table_frame, columns=self.columns, show="headings",
                            height=visible_rows)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._apply_tree_style(tree, row_h)

        # 列宽自适应（按表头与数据内容的估算宽度）
        for col in self.columns:
            max_len = _text_width(str(col))
            col_idx = self.columns.index(col)
            for row in self.rows:
                if col_idx < len(row):
                    max_len = max(max_len, _text_width(format_cell(row[col_idx])))
            tree.column(col, width=min(max(60, max_len * 8 + 18), 320), stretch=True)
            tree.heading(col, text=str(col))

        for row in self.rows:
            tree.insert("", "end", values=[format_cell(v) for v in row])

        self._tree = tree
        self._table_frame = table_frame

        # 底部关闭按钮
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text="关闭", width=88, font=config.FONT_BODY,
                      command=self.close).grid(row=0, column=1, sticky="e")

        # 精确收窗（wm geometry 物理像素）：chrome 为非表格区高度（全尺寸
        # 下测量，物理），目标 = chrome + 表格内容请求高度（物理），一次性
        # 设置后最后一行与横向滚动条严丝合缝，无空白带；与缩放推断无关
        self.update_idletasks()
        chrome_phys = self.winfo_height() - table_frame.winfo_height()
        target_phys = chrome_phys + table_frame.winfo_reqheight()
        if target_phys < self.winfo_height() - 1:
            new_y = max(my + (mh - target_phys) // 2 + shift[1], 0)
            self.wm_geometry(f"{w_phys}x{max(target_phys, 160)}+{x}+{new_y}")
            self.update_idletasks()

    def _apply_tree_style(self, tree: ttk.Treeview, row_h: int) -> None:
        """按当前外观模式配置 Treeview 配色；row_h 为物理行高。"""
        style = ttk.Style(self)
        style.theme_use("clam")  # clam 主题允许自定义配色
        if ctk.get_appearance_mode() == "Dark":
            style.configure("Treeview", background="#2B2B2B", fieldbackground="#2B2B2B",
                            foreground="#E8EAF0", rowheight=row_h, borderwidth=0)
            style.configure("Treeview.Heading", background="#3E4754",
                            foreground="#FFFFFF", borderwidth=0)
            style.map("Treeview", background=[("selected", "#3B8ED0")])
        else:
            style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                            foreground="#1A1A1A", rowheight=row_h, borderwidth=0)
            style.configure("Treeview.Heading", background="#D5DCE4",
                            foreground="#1A1A1A", borderwidth=0)
            style.map("Treeview", background=[("selected", "#3B8ED0")])

    def close(self) -> None:
        """关闭预览弹窗。"""
        try:
            self.grab_release()
        except Exception:  # 主窗口可能已销毁
            pass
        self.destroy()
