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

    非模态设计（不使用 grab_set）：多个预览可同时打开、各自独立
    关闭/置前，主窗口始终可操作；shift 为相对居中的级联偏移（多
    预览不重叠）；scale 为显示缩放倍率（由调用方从侧边栏读取，
    1.25 = 125% 显示）。
    """

    def __init__(self, master, title: str, columns: list, rows: list,
                 info_text: str = "", shift: tuple = (0, 0),
                 scale: float = 1.0):
        super().__init__(master)
        self.columns = list(columns)
        self.rows = list(rows)
        self._scale = max(scale, 0.5)

        self.title(title)
        self.resizable(False, False)
        # 普通无主窗口（不设 transient/-toolwindow/-topmost）：
        #  - transient/toolwindow 在 Windows 上无法被激活，focus_force
        #    失效 → 预览刚出现就被主窗口抢回前台（表现为"出现后消失"），
        #    且 toolwindow 标题栏是老式小叉；
        #  - 普通窗口可正常置前：打开时 lift+focus_force 到最前，点主窗口
        #    时主窗口置前、预览躲到后面，点预览时预览置前；
        #  - 代价：预览会出现在任务栏/Alt-Tab（可用任务栏管理多个预览）。
        # 非模态：不 grab_set，避免多预览互相劫持点击、主窗口被锁死

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
        # 纵向滚动条跨两行（盖住右下角）：横向滚动条只占树的宽度，
        # 避免 columnspan 跨列在列边界产生渲染接缝（看起来像两条
        # 横向滚动条中间隔空白）
        vsb.grid(row=0, column=1, rowspan=2, sticky="ns")
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

        # 精确收窗（wm geometry 物理像素）：直接按"全部内容的请求高度"
        # 设定初始尺寸——winfo_reqheight 不依赖窗口映射即可精确计算，
        # 首帧即正确大小，不会出现"先小一圈再恢复"的跳动。
        self._w_phys = w_phys
        self._fit_x = x
        self._center_y = my + mh // 2
        self._shift_y = shift[1]
        self.update_idletasks()
        natural_phys = self.winfo_reqheight()
        target_phys = min(max(natural_phys, 160), round(config.PREVIEW_HEIGHT * self._scale))
        if target_phys < h_phys - 1:
            new_y = max(self._center_y - target_phys // 2 + self._shift_y, 0)
            self.wm_geometry(f"{w_phys}x{target_phys}+{self._fit_x}+{new_y}")
        # 映射后再校正一次：请求尺寸在极端布局时序下可能略有偏差，
        # 实测偏差 >2px 再修正（此时窗口已映射，测量可靠）
        self.after(10, self._correct_height)

    def _correct_height(self) -> None:
        """映射后校正：若布局稳定后高度仍有偏差则再次收窗，避免错位。"""
        if not self.winfo_exists():
            return
        self.update_idletasks()
        chrome_phys = self.winfo_height() - self._table_frame.winfo_height()
        target_phys = chrome_phys + self._table_frame.winfo_reqheight()
        if abs(target_phys - self.winfo_height()) > 2:
            new_y = max(self._center_y - target_phys // 2 + self._shift_y, 0)
            self.wm_geometry(f"{self._w_phys}x{max(target_phys, 160)}+{self._fit_x}+{new_y}")

        # 置前并聚焦 + 瞬时置顶保险：Windows 上前台锁定或父窗口销毁时的
        # 激活竞争会盖掉 focus_force（表现为预览"出现即跑到后面"），短暂
        # 置顶可强制越过竞争；释放后恢复普通 z-order，点主窗口仍可把
        # 预览顶到后面
        self.lift()
        self.focus_force()
        self.after(30, self._ensure_on_top)

    def _ensure_on_top(self) -> None:
        """瞬时置顶 150ms 强制预览越过前台竞争，随后释放恢复普通层级。"""
        if not self.winfo_exists():
            return
        self.lift()
        self.attributes("-topmost", True)
        self.after(150, self._release_topmost)

    def _release_topmost(self) -> None:
        if self.winfo_exists():
            self.attributes("-topmost", False)

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
