"""SheetPickerDialog：工作表多选对话框。

用于「添加文件」时选择要添加的工作表，以及从暂存池中
直接添加某文件的其它工作表。选项以复选框列表呈现，
支持全选/全不选，确定后通过回调返回选中的 key 列表。
"""
from __future__ import annotations

import customtkinter as ctk

from app import config


class SheetPickerDialog(ctk.CTkToplevel):
    """工作表多选对话框（模态）。"""

    def __init__(self, master, title: str, options: list, on_confirm,
                 default_checked: bool = True):
        """options: list[(group, key, label)]；on_confirm(keys) 在确定后回调。

        group 为分组标题（如文件名），非 None 时在组内选项上方渲染
        加粗分组头，形成「文件 → 工作表」的层级；None 则平铺不分组。
        """
        super().__init__(master)
        self._on_confirm = on_confirm
        self._vars: dict = {}
        self._checkboxes: dict = {}
        self._group_headers: dict = {}  # group -> 分组标题控件（测试用）

        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()  # 模态：阻止操作主窗口
        self.attributes("-topmost", True)

        # 居中于主窗口
        master.update_idletasks()
        mx, my = master.winfo_rootx(), master.winfo_rooty()
        mw, mh = master.winfo_width(), master.winfo_height()
        w, h = config.SHEET_PICKER_WIDTH, config.SHEET_PICKER_HEIGHT
        x = mx + (mw - w) // 2
        y = my + (mh - h) // 2
        self.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        # 提示 + 选项列表（可滚动）
        hint = ctk.CTkLabel(self, text="勾选要添加的工作表：", font=config.FONT_SMALL,
                            text_color=config.FILE_ROW_SUBTEXT_COLOR, anchor="w")
        hint.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 分组渲染：先按 group 排序去重，组头加粗，选项缩进显示
        group_font = ctk.CTkFont(family=config.FONT_BODY[0],
                                 size=config.FONT_BODY[1], weight="bold")
        groups: list = []
        for group, _key, _label in options:
            if group not in groups:
                groups.append(group)
        for group in groups:
            if group is not None:
                header = ctk.CTkLabel(scroll, text=group, font=group_font,
                                      text_color=config.FILE_ROW_TEXT_COLOR, anchor="w")
                header.pack(fill="x", padx=6, pady=(10, 2))
                self._group_headers[group] = header
            for key, label in ((k, l) for g, k, l in options if g == group):
                # 变量与勾选框的 on/off 语义必须一致（onvalue/offvalue）：
                # 否则视觉勾选状态与变量值脱节，会出现"点击选中却被反选"、
                # "全选/全不选无反应"等问题
                var = ctk.StringVar(value="on" if default_checked else "")
                self._vars[key] = var
                checkbox = ctk.CTkCheckBox(scroll, text=label, variable=var,
                                           onvalue="on", offvalue="",
                                           font=config.FONT_BODY)
                checkbox.pack(fill="x", padx=18, pady=3)
                self._checkboxes[key] = checkbox

        # 底部操作栏：全选 / 全不选 / 取消 / 确定
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 12))
        bar.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(bar, text="全选", width=64, font=config.FONT_BODY,
                      command=self._select_all).grid(row=0, column=0, padx=4)
        ctk.CTkButton(bar, text="全不选", width=64, font=config.FONT_BODY,
                      command=self._select_none).grid(row=0, column=1, padx=4)
        ctk.CTkButton(bar, text="取消", width=64, font=config.FONT_BODY,
                      fg_color="gray35", hover_color="gray45",
                      command=self._on_cancel).grid(row=0, column=2, padx=4)
        ctk.CTkButton(bar, text="确定", width=72, font=config.FONT_BODY,
                      command=self._on_ok).grid(row=0, column=4, padx=4)

    # ---- 交互 ----
    def _select_all(self) -> None:
        for var in self._vars.values():
            var.set("on")

    def _select_none(self) -> None:
        for var in self._vars.values():
            var.set("")

    def _on_ok(self) -> None:
        keys = [k for k, var in self._vars.items() if var.get() == "on"]
        self._close(keys)

    def _on_cancel(self) -> None:
        self._close(None)

    def _close(self, result) -> None:
        """关闭对话框并回调（result 为选中的 key 列表；取消为 None）。"""
        try:
            self.grab_release()
        except Exception:  # 主窗口可能已销毁
            pass
        self.destroy()
        self._on_confirm(result)
