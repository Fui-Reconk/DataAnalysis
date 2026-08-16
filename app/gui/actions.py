"""OperationsMixin：匹配、过滤与导出业务操作。

编排 merge_engine / filter_engine / exporter / stats 各引擎模块，
统一处理进度条、状态栏与错误弹窗，保证耗时操作时界面不卡死。
"""
from __future__ import annotations

from tkinter import filedialog, messagebox

from app import config
from app.exporter import default_export_name, export_excel
from app.filter_engine import apply_query
from app.gui.base import AppBase
from app.logger import logger
from app.merge_engine import clean_redundant_columns, left_join
from app.stats import calculate_default_stats


class OperationsMixin(AppBase):
    """业务操作：执行左连接匹配、应用/重置过滤、导出结果。"""

    def on_execute_merge(self) -> None:
        """执行左连接匹配（以第一个数据源为基准表）。"""
        key = self.pages[1].get_key()
        if not key:
            messagebox.showwarning("提示", "请先选择唯一标识项。")
            return
        if len(self.state.sources) < 2:
            messagebox.showwarning("提示", "至少需要添加两个工作表才能执行匹配。")
            return

        self.state.key_column = key

        self.start_progress()
        self.set_status("正在执行左连接匹配，数据量较大时请耐心等待…")
        try:
            try:
                merged = left_join(self.state.dataframes, self.state.sources, key)
            except (ValueError, KeyError) as exc:
                logger.warning("匹配失败：%s", exc)
                messagebox.showerror("匹配失败", str(exc))
                return
            # 匹配后按配置自动清理冗余列（仅删非基准表的全空列 / 与基准表同名的重复列）
            removed_cols: list = []
            if config.MERGE_AUTO_CLEAN:
                merged, removed_cols = clean_redundant_columns(
                    merged, self.state.dataframes[self.state.sources[0]])
            self.state.merged_df = merged
            self.state.filtered_df = merged.copy()
        finally:
            self.stop_progress()

        rows, cols = merged.shape
        base_rows = len(self.state.dataframes[self.state.sources[0]])
        info_text = (
            f"✔ 匹配完成：基准表 {base_rows} 行，合并后 {rows} 行 × {cols} 列。\n"
            f"主键「{key}」；重复列名已按数据源序号加后缀区分。")
        if removed_cols:
            info_text += f"\n已自动删除 {len(removed_cols)} 个冗余列：\n{'、'.join(removed_cols)}"
        self.pages[1].show_info(info_text)
        self.pages[2].show_info(f"当前数据：{rows} 行 × {cols} 列（匹配后全量数据）")
        self.set_status("匹配完成，可进行过滤或导出。")
        # 匹配完成后按配置自动弹出结果预览，便于核对合并后的列与行数
        if config.PREVIEW_AUTO_AFTER_MERGE:
            self._open_preview("预览：匹配结果", merged)

    def on_apply_filter(self) -> None:
        """对合并结果应用用户输入的条件过滤。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行过滤。")
            return

        query = self.pages[2].get_query()
        if not query:
            messagebox.showinfo("提示", "请输入过滤条件，例如：销售额 > 1000 and 地区 == '华东'")
            return

        self.start_progress()
        self.set_status("正在应用过滤条件…")
        try:
            try:
                result = apply_query(self.state.merged_df, query)
            except Exception as exc:  # 过滤语法错误需弹窗提示，不崩溃（BLE001 见 .flake8）
                logger.error("过滤失败：%s", exc, exc_info=True)
                messagebox.showerror("过滤失败", f"过滤语句解析失败：\n{exc}\n\n请检查字段名与语法。")
                return
            self.state.filtered_df = result
        finally:
            self.stop_progress()

        total = len(self.state.merged_df)
        rows = len(result)
        self.pages[2].show_info(f"✔ 过滤完成：{total} 行 → {rows} 行，已过滤 {total - rows} 行。")
        self.set_status(f"过滤完成：{rows}/{total} 行。")

    def on_reset_filter(self) -> None:
        """重置过滤，恢复为匹配后的全量数据。"""
        if self.state.merged_df is None:
            return
        self.state.filtered_df = self.state.merged_df.copy()
        self.pages[2].set_query("")
        rows = len(self.state.merged_df)
        self.pages[2].show_info(f"已重置，当前为匹配后全量数据：{rows} 行。")
        self.set_status("已重置过滤。")

    def on_export(self) -> None:
        """导出最终结果（Sheet1 数据 / Sheet2 统计）到 Excel。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行导出。")
            return

        # 导出的数据：优先使用过滤后的结果，未过滤则用合并结果
        data_df = self.state.filtered_df if self.state.filtered_df is not None else self.state.merged_df

        # 调用预留统计模块（calculate_default_stats）
        self.start_progress()
        self.set_status("正在计算统计…")
        try:
            try:
                stats_df = calculate_default_stats(data_df)
            except Exception as exc:  # 统计逻辑由用户编写，出错需兜底（BLE001 见 .flake8）
                logger.error("统计计算失败：%s", exc, exc_info=True)
                messagebox.showerror("统计计算失败", f"calculate_default_stats 执行出错：\n{exc}")
                stats_df = None
        finally:
            self.stop_progress()

        # 选择保存路径（默认文件名：匹配结果_时间戳.xlsx）
        path = filedialog.asksaveasfilename(
            title="保存导出结果",
            defaultextension=".xlsx",
            initialfile=default_export_name(),
            filetypes=[("Excel 文件", "*.xlsx")])
        if not path:
            return

        self.start_progress()
        self.set_status("正在写入 Excel…")
        try:
            try:
                out_path = export_excel(data_df, stats_df, path)  # type: ignore
            except Exception as exc:  # 写入失败需弹窗提示（BLE001 见 .flake8）
                logger.error("导出失败：%s - %s", path, exc, exc_info=True)
                messagebox.showerror("导出失败", f"写入文件失败：\n{exc}")
                return
        finally:
            self.stop_progress()

        self.pages[3].show_info(f"✔ 已导出至：\n{out_path}")
        self.set_status("导出成功。")
        messagebox.showinfo("导出成功", f"结果已保存到：\n{out_path}")
