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
from app.data_loader import list_sheets, load_excel, rename_columns_abbr, scan_columns
from app.gui.base import AppBase
from app.logger import logger
from app.preview_dialog import PreviewDialog, format_cell
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
                logger.warning("读取文件失败：%s - %s", path, exc)
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

    def on_preview_source(self, path: str, sheet: str, shift: tuple = (0, 0)):
        """预览工作表前几行数据（直接使用已加载的内存数据）。

        预览为非模态：可同时打开多个、主窗口保持可操作；shift 为级联偏移。
        """
        df = self.state.dataframes.get((path, sheet))
        if df is None:
            messagebox.showwarning("提示", "该数据源尚未加载，无法预览。")
            return None
        head = df.head(config.PREVIEW_ROWS)
        columns = [str(c) for c in head.columns]
        rows = [
            [format_cell(v) for v in row]
            for row in head.itertuples(index=False, name=None)
        ]
        info = f"共 {len(df)} 行 × {len(df.columns)} 列，显示前 {min(config.PREVIEW_ROWS, len(df))} 行"
        # 显示缩放倍率：与浮层同源（侧边栏物理/逻辑宽度比），已验证可靠
        scale = float(self.sidebar._apply_widget_scaling(1.0))
        return PreviewDialog(self.root, f"预览：{os.path.basename(path)} [{sheet}]",
                             columns, rows, info, shift=shift, scale=scale)

    def on_open_source(self, path: str) -> None:
        """用系统默认程序（Office / WPS 等）打开指定文件。"""
        try:
            open_with_system(path)
        except Exception as exc:  # 打开失败需提示（BLE001 见 .flake8）
            logger.error("打开文件失败：%s - %s", path, exc, exc_info=True)
            messagebox.showerror(
                "打开失败", f"无法用系统默认程序打开文件：\n{path}\n\n{exc}")

    def on_show_in_folder(self, path: str) -> None:
        """在系统文件管理器中定位指定文件。"""
        try:
            show_in_folder(path)
        except Exception as exc:  # 定位失败需提示（BLE001 见 .flake8）
            logger.error("定位文件失败：%s - %s", path, exc, exc_info=True)
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
            logger.error("重载数据源失败：%s[%s]", path, sheet, exc_info=True)
            messagebox.showerror(
                "重新读取失败",
                f"文件「{os.path.basename(path)}」工作表「{sheet}」读取失败：\n{exc}")
            return
        self.state.dataframes[src] = df
        self._after_files_changed(f"已重载：{os.path.basename(path)} [{sheet}]")

    def on_set_base(self, targets: list | None = None) -> None:
        """将目标设为匹配基准表（仅单个目标时生效）。"""
        selected = self.pages[0].selected_sources if targets is None else targets
        if len(selected) != 1:
            return
        path, sheet = selected[0]
        src = (path, sheet)
        if src not in self.state.sources:
            return
        if self.state.sources[0] == src:
            self.set_status("该工作表已是匹配基准表。")
            return
        self.state.sources.remove(src)
        self.state.sources.insert(0, src)
        self._after_files_changed(f"已设为匹配基准表：{os.path.basename(path)} [{sheet}]")

    # ---- 批量操作（右键菜单：对全部选中执行，超过阈值需二次确认） ----

    def _confirm_batch(self, action: str, count: int, unit: str = "工作表",
                       threshold: int | None = None) -> bool:
        """批量操作二次确认：数量超过阈值时弹窗询问（阈值缺省用全局值）。"""
        if threshold is None:
            threshold = config.MENU_CONFIRM_THRESHOLD
        if count <= threshold:
            return True
        return messagebox.askyesno(
            "确认操作", f"将对 {count} 个{unit}执行「{action}」，确认继续？")

    def on_open_sources(self, targets: list | None = None) -> None:
        """打开目标工作表所在文件（同一文件只打开一次）。

        targets 缺省时使用当前选中；右键菜单显式传入操作目标。
        """
        selected = self.pages[0].selected_sources if targets is None else targets
        if not selected:
            messagebox.showinfo("提示", "请先选择要打开的工作表。")
            return
        if not self._confirm_batch("打开文件", len(selected)):
            return
        for path in dict.fromkeys(p for p, _ in selected):
            self.on_open_source(path)

    def on_show_sources_in_folder(self, targets: list | None = None) -> None:
        """在文件管理器中定位目标工作表所在文件（按文件去重）。

        二次确认按「文件数」独立计数（阈值见 folder_confirm_threshold）。
        """
        selected = self.pages[0].selected_sources if targets is None else targets
        if not selected:
            messagebox.showinfo("提示", "请先选择要定位的工作表。")
            return
        files = list(dict.fromkeys(p for p, _ in selected))
        if not self._confirm_batch("在文件夹中显示", len(files), unit="文件",
                                   threshold=config.MENU_FOLDER_CONFIRM_THRESHOLD):
            return
        for path in files:
            self.on_show_in_folder(path)

    def on_preview_sources(self, targets: list | None = None) -> None:
        """预览目标工作表（级联排列，首个在前）。"""
        selected = self.pages[0].selected_sources if targets is None else targets
        if not selected:
            messagebox.showinfo("提示", "请先选择要预览的工作表。")
            return
        if not self._confirm_batch("预览", len(selected)):
            return
        for i, (path, sheet) in enumerate(selected):
            self.on_preview_source(path, sheet, shift=(i * 24, i * 24))

    def on_reload_sources(self, targets: list | None = None) -> None:
        """重载目标工作表。"""
        selected = self.pages[0].selected_sources if targets is None else targets
        if not selected:
            messagebox.showinfo("提示", "请先选择要重载的工作表。")
            return
        if not self._confirm_batch("重载", len(selected)):
            return
        for path, sheet in selected:
            self.on_reload_source(path, sheet)

    def on_replace_abbr(self, targets: list | None = None) -> None:
        """将目标工作表列名中的拼音缩写替换为中文全称（映射见 config.cfg [column_map]）。

        替换完成后按配置（[preview] auto_show_after_replace）自动弹出预览，
        便于确认新列名；数量与导入后自动预览一致（auto_show_count），级联排列。
        """
        if not config.COLUMN_ABBR_MAP:
            messagebox.showinfo("提示", "config.cfg 中未配置 [column_map] 缩写映射。")
            return
        selected = self.pages[0].selected_sources if targets is None else targets
        if not selected:
            messagebox.showinfo("提示", "请先选择要替换列名的工作表。")
            return
        replaced_sources = []
        for path, sheet in selected:
            df = self.state.dataframes.get((path, sheet))
            if df is None:
                continue
            new_df = rename_columns_abbr(df, config.COLUMN_ABBR_MAP)
            if list(new_df.columns) != list(df.columns):
                self.state.dataframes[(path, sheet)] = new_df
                replaced_sources.append((path, sheet))
        if replaced_sources:
            self._after_files_changed(f"已替换 {len(replaced_sources)} 个工作表的列名缩写。")
            # 替换后自动弹出预览（全部非模态、级联排列），方便确认新列名
            if config.PREVIEW_AUTO_AFTER_REPLACE:
                count = max(1, min(config.PREVIEW_AUTO_SHOW_COUNT, len(replaced_sources)))
                for i, src in enumerate(replaced_sources[:count]):
                    self.on_preview_source(*src, shift=(i * 24, i * 24))
        else:
            self.set_status("未发现可替换的缩写列名。")

    def _add_sources(self, selected) -> None:
        """加载选中的 (文件路径, 工作表名) 列表；None（取消）不处理。

        添加成功后自动弹出首个新数据源的预览。
        """
        if not selected:
            self.set_status("未添加任何工作表。")
            return

        added_sources = []
        self.start_progress()
        try:
            for path, sheet in selected:
                src = (path, sheet)
                if src in self.state.sources:
                    continue
                try:
                    df = load_excel(path, sheet)
                except Exception as exc:  # 单个工作表读取失败不影响其它表（BLE001 见 .flake8）
                    logger.error("读取数据源失败：%s[%s]", path, sheet, exc_info=True)
                    messagebox.showerror(
                        "读取失败",
                        f"文件「{os.path.basename(path)}」工作表「{sheet}」读取失败：\n{exc}")
                    continue
                self.state.sources.append(src)
                self.state.dataframes[src] = df
                added_sources.append(src)
                self.root.update_idletasks()
        finally:
            self.stop_progress()

        if added_sources:
            self._after_files_changed(
                f"已添加 {len(added_sources)} 个工作表，当前共 {len(self.state.sources)} 个。")
            # 导入后按配置自动弹出预览（数量可配，全部非模态、级联排列）
            if config.PREVIEW_AUTO_SHOW:
                count = max(1, min(config.PREVIEW_AUTO_SHOW_COUNT, len(added_sources)))
                for i, src in enumerate(added_sources[:count]):
                    self.on_preview_source(*src, shift=(i * 24, i * 24))
        else:
            self.set_status(config.STATUS_READY)

    def on_remove_selected(self, targets: list | None = None) -> None:
        """移除目标工作表（超过阈值时二次确认）。"""
        selected = self.pages[0].selected_sources if targets is None else targets
        if not selected:
            messagebox.showinfo("提示", "请先在工作表列表中点击选中要移除的数据源。")
            return
        if not self._confirm_batch("删除", len(selected)):
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
