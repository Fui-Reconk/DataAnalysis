"""FileOpsMixin：文件加载与移除操作。

支持多工作表：添加文件时可自由勾选要加入的工作表；文件添加过任意
工作表后即进入「暂存池」，之后可随时直接添加其其它工作表，无需
再次选择文件。数据源集合变化后，统一执行 重扫表头 → 使旧结果失效
→ 刷新页面，保证界面与状态始终一致。
"""
from __future__ import annotations

import os

from tkinter import filedialog, messagebox

from app import config
from app.data_loader import list_sheets, load_excel, scan_columns
from app.gui.base import AppBase
from app.sheet_dialog import SheetPickerDialog
from app.system_utils import open_with_system, show_in_folder


class FileOpsMixin(AppBase):
    """文件操作：添加文件/工作表、从暂存池添加、移除，并在变化后统一刷新界面。"""

    def on_add_files(self) -> None:
        """选择并加载多个 Excel 文件（可勾选工作表；读取失败则跳过并提示）。"""
        paths = filedialog.askopenfilenames(title="选择 Excel 文件",
                                            filetypes=config.EXCEL_FILE_TYPES)
        if not paths:
            return

        # 新文件入暂存池并记录全部工作表名；已在池中的文件无需重复读取
        failed = []
        for path in paths:
            if path in self.state.staged_files:
                continue
            try:
                self.state.staged_files[path] = list_sheets(path)
            except Exception as exc:  # 读取失败需逐个提示并跳过（BLE001 见 .flake8）
                failed.append((path, str(exc)))

        # 本次选择文件的所有未添加工作表（含单工作表文件，统一下一步处理）
        candidates = [
            (path, sheet)
            for path in paths if path in self.state.staged_files
            for sheet in self.state.staged_files[path]
            if (path, sheet) not in self.state.sources
        ]

        if failed:
            detail = "\n".join(f"• {os.path.basename(p)}：{e}" for p, e in failed)
            messagebox.showwarning("部分文件读取失败", f"以下文件读取失败，已跳过：\n{detail}")

        if not candidates:
            self.set_status("所选文件的工作表均已添加过。")
            return

        # 全部单工作表文件 → 直接添加；存在多工作表文件 → 弹窗勾选（按文件分组）
        multi = any(len(self.state.staged_files[p]) > 1 for p, _ in candidates)
        if multi:
            options = [(os.path.basename(p), (p, s), s) for p, s in candidates]
            SheetPickerDialog(self.root, "选择要添加的工作表", options,
                              on_confirm=self._add_sources)
        else:
            self._add_sources(candidates)

    def on_add_sheets(self) -> None:
        """从暂存池直接添加其它工作表（无需重新选择文件）。"""
        candidates = [
            (path, sheet)
            for path, sheets in self.state.staged_files.items()
            for sheet in sheets
            if (path, sheet) not in self.state.sources
        ]
        if not candidates:
            messagebox.showinfo(
                "提示", "暂存池中没有可添加的工作表。\n\n"
                "先通过「添加文件」选择文件，之后即可随时直接添加其其它工作表。")
            return
        options = [(os.path.basename(p), (p, s), s) for p, s in candidates]
        SheetPickerDialog(self.root, "添加工作表（暂存池）", options,
                          on_confirm=self._add_sources)

    def on_open_source(self, path: str, sheet: str) -> None:
        """用系统默认程序（Office / WPS 等）打开数据源所在文件。"""
        try:
            open_with_system(path)
        except Exception as exc:  # 打开失败需提示（BLE001 见 .flake8）
            messagebox.showerror(
                "打开失败", f"无法用系统默认程序打开文件：\n{path}\n\n{exc}")

    def on_show_in_folder(self, path: str, sheet: str) -> None:
        """在系统文件管理器中定位数据源所在文件。"""
        try:
            show_in_folder(path)
        except Exception as exc:  # 定位失败需提示（BLE001 见 .flake8）
            messagebox.showerror(
                "定位失败", f"无法在文件管理器中定位文件：\n{path}\n\n{exc}")

    def on_reload_source(self, path: str, sheet: str) -> None:
        """重新读取该工作表（文件被外部修改后刷新内存数据）。"""
        src = (path, sheet)
        if src not in self.state.sources:
            return
        try:
            df = load_excel(path, sheet)
        except Exception as exc:  # 重读失败需提示（BLE001 见 .flake8）
            messagebox.showerror(
                "重新读取失败",
                f"文件「{os.path.basename(path)}」工作表「{sheet}」读取失败：\n{exc}")
            return
        self.state.dataframes[src] = df
        self._after_files_changed(f"已重载：{os.path.basename(path)} [{sheet}]")

    def on_set_base(self, path: str, sheet: str) -> None:
        """将指定数据源设为匹配基准表（移到列表首位）。"""
        src = (path, sheet)
        if src not in self.state.sources:
            return
        if self.state.sources[0] == src:
            self.set_status("该工作表已是匹配基准表。")
            return
        self.state.sources.remove(src)
        self.state.sources.insert(0, src)
        self._after_files_changed(f"已设为匹配基准表：{os.path.basename(path)} [{sheet}]")

    def _add_sources(self, selected) -> None:
        """加载选中的 (文件路径, 工作表名) 列表；None（取消）不处理。"""
        if not selected:
            self.set_status("未添加任何工作表。")
            return

        added = 0
        self.start_progress()
        try:
            for path, sheet in selected:
                if (path, sheet) in self.state.sources:
                    continue
                try:
                    df = load_excel(path, sheet)
                except Exception as exc:  # 单个工作表读取失败不影响其它表（BLE001 见 .flake8）
                    messagebox.showerror(
                        "读取失败",
                        f"文件「{os.path.basename(path)}」工作表「{sheet}」读取失败：\n{exc}")
                    continue
                self.state.sources.append((path, sheet))
                self.state.dataframes[(path, sheet)] = df
                added += 1
                self.root.update_idletasks()
        finally:
            self.stop_progress()

        if added:
            self._after_files_changed(f"已添加 {added} 个工作表，当前共 {len(self.state.sources)} 个。")
        else:
            self.set_status(config.STATUS_READY)

    def on_remove_selected(self) -> None:
        """移除文件列表中当前选中的数据源（文件+工作表）。"""
        selected = self.pages[0].selected_sources
        if not selected:
            messagebox.showinfo("提示", "请先在工作表列表中点击选中要移除的数据源。")
            return
        for path, sheet in selected:
            self._remove_source(path, sheet)
        self._after_files_changed(f"已移除 {len(selected)} 个工作表。")

    def on_remove_source(self, path: str, sheet: str) -> None:
        """移除单个数据源。"""
        self._remove_source(path, sheet)
        self._after_files_changed(f"已移除：{os.path.basename(path)} [{sheet}]")

    def _remove_source(self, path: str, sheet: str) -> None:
        """从状态中移除指定数据源；文件仍保留在暂存池，可随时添加其其它工作表。"""
        src = (path, sheet)
        if src in self.state.sources:
            self.state.sources.remove(src)
        self.state.dataframes.pop(src, None)

    def _after_files_changed(self, status_text: str) -> None:
        """数据源集合变化后的统一刷新流程。"""
        self._rescan_columns()
        self._invalidate_result()
        self.pages[0].refresh()
        self._refresh_match_page()
        self.set_status(status_text)

    def _rescan_columns(self) -> None:
        """重新扫描全部数据源的表头并集。"""
        self.state.column_union = scan_columns(self.state.sources, self.state.dataframes)

    def _refresh_match_page(self) -> None:
        """刷新匹配页主键下拉框。"""
        self.pages[1].update_columns(self.state.column_union)

    def _invalidate_result(self) -> None:
        """数据源集合变化时，使旧的匹配/过滤结果失效并清空相关提示。"""
        self.state.merged_df = None
        self.state.filtered_df = None
        self.pages[1].show_info("")
        self.pages[2].set_query("")
        self.pages[2].show_info("")
        self.pages[3].show_info("")
