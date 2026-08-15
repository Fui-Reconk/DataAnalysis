"""FileOpsMixin：文件加载与移除操作。

文件集合发生变化后，统一执行 重扫表头 → 使旧结果失效 → 刷新页面，
保证界面与状态始终一致。
"""
from __future__ import annotations

import os

from tkinter import filedialog, messagebox

from app import config
from app.data_loader import load_excel, scan_columns
from app.gui.base import AppBase


class FileOpsMixin(AppBase):
    """文件操作：添加/移除文件，并在变化后统一刷新界面。"""

    def on_add_files(self) -> None:
        """选择并加载多个 Excel 文件（自动去重，读取失败则跳过并提示）。"""
        paths = filedialog.askopenfilenames(title="选择 Excel 文件",
                                            filetypes=config.EXCEL_FILE_TYPES)
        if not paths:
            return

        # 过滤已存在的文件，避免重复加载
        new_paths = [p for p in paths if p not in self.state.file_paths]
        added, failed = [], []

        self.start_progress()
        try:
            for path in new_paths:
                self.set_status(f"正在读取：{os.path.basename(path)} …")
                try:
                    df = load_excel(path)
                except Exception as exc:  # noqa: BLE001 —— 读取失败需逐个提示并跳过
                    failed.append((path, str(exc)))
                    continue
                self.state.dataframes[path] = df
                self.state.file_paths.append(path)
                added.append(path)
                self.root.update_idletasks()
        finally:
            self.stop_progress()

        # 文件集合变化后：重扫表头、使旧匹配结果失效、刷新页面
        self._rescan_columns()
        self._invalidate_result()
        self.pages[0].refresh()
        self._refresh_match_page()

        if failed:
            detail = "\n".join(f"• {os.path.basename(p)}：{e}" for p, e in failed)
            messagebox.showwarning("部分文件读取失败", f"以下文件读取失败，已跳过：\n{detail}")

        if added:
            self.set_status(f"已加载 {len(added)} 个文件，当前共 {len(self.state.file_paths)} 个。")
        else:
            self.set_status(config.STATUS_READY)

    def on_remove_selected(self) -> None:
        """移除文件列表中当前选中的文件。"""
        selected = self.pages[0].selected_paths
        if not selected:
            messagebox.showinfo("提示", "请先在文件列表中点击选中要移除的文件。")
            return
        for path in selected:
            self._remove_file(path)
        self._after_files_changed(f"已移除 {len(selected)} 个文件。")

    def on_remove_file(self, path: str) -> None:
        """移除单个文件。"""
        self._remove_file(path)
        self._after_files_changed(f"已移除：{os.path.basename(path)}")

    def _remove_file(self, path: str) -> None:
        """从状态中移除指定文件。"""
        if path in self.state.file_paths:
            self.state.file_paths.remove(path)
        self.state.dataframes.pop(path, None)

    def _after_files_changed(self, status_text: str) -> None:
        """文件集合变化后的统一刷新流程。"""
        self._rescan_columns()
        self._invalidate_result()
        self.pages[0].refresh()
        self._refresh_match_page()
        self.set_status(status_text)

    def _rescan_columns(self) -> None:
        """重新扫描全部表头并集。"""
        self.state.column_union = scan_columns(self.state.file_paths, self.state.dataframes)

    def _refresh_match_page(self) -> None:
        """刷新匹配页主键下拉框。"""
        self.pages[1].update_columns(self.state.column_union)

    def _invalidate_result(self) -> None:
        """文件集合变化时，使旧的匹配/过滤结果失效并清空相关提示。"""
        self.state.merged_df = None
        self.state.filtered_df = None
        self.pages[1].show_info("")
        self.pages[2].set_query("")
        self.pages[2].show_info("")
        self.pages[3].show_info("")
