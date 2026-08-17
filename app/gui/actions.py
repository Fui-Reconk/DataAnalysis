"""OperationsMixin：匹配、过滤与导出业务操作。

编排 merge_engine / filter_engine / exporter / stats 各引擎模块，
统一处理进度条、状态栏与错误弹窗，保证耗时操作时界面不卡死。
"""
from __future__ import annotations

import os
import re
from tkinter import filedialog, messagebox

import pandas as pd

from app import config
from app.exporter import default_export_name, export_excel, next_stats_sheet_name
from app.filter_engine import apply_conditions
from app.gui.base import AppBase
from app.logger import logger
from app.merge_engine import clean_redundant_columns, left_join
from app.sheet_dialog import SheetPickerDialog
from app.stats import count_column_name, group_count


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
            self.state.stats_df = None
            self.state.stats_sheets = []  # 数据变化，累积的统计失效
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
        self.pages[2].update_columns(list(merged.columns))
        self.pages[2].show_info(f"当前数据：{rows} 行 × {cols} 列（匹配后全量数据）")
        # 统计页候选列跟随过滤页可见列（隐藏列不出现）
        self.pages[3].update_columns(self.pages[2].visible_columns())
        self.set_status("匹配完成，可进行过滤或导出。")
        # 匹配完成后按配置自动弹出结果预览，便于核对合并后的列与行数
        if config.PREVIEW_AUTO_AFTER_MERGE:
            self._open_preview("预览：匹配结果", merged)

    def on_apply_filter(self) -> None:
        """按条件行（列名 + 条件 + 比较值）对合并结果应用过滤。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行过滤。")
            return

        try:
            conditions = self.pages[2].get_conditions()
        except ValueError as exc:
            messagebox.showwarning("过滤条件有误", str(exc))
            return
        if not conditions:
            messagebox.showinfo("提示", "请至少添加一个过滤条件（可点「添加条件」增加）。")
            return

        self.start_progress()
        self.set_status("正在应用过滤条件…")
        try:
            try:
                result = apply_conditions(self.state.merged_df, conditions)
            except Exception as exc:  # 条件/数值不合法需弹窗提示，不崩溃（BLE001 见 .flake8）
                logger.error("过滤失败：%s", exc, exc_info=True)
                messagebox.showerror("过滤失败", f"过滤条件执行失败：\n{exc}")
                return
            self.state.filtered_df = result
            self.state.stats_df = None  # 数据变化，旧统计结果失效
            self.state.stats_sheets = []
        finally:
            self.stop_progress()

        total = len(self.state.merged_df)
        rows = len(result)
        self.pages[2].show_info(f"✔ 过滤完成：{total} 行 → {rows} 行，已过滤 {total - rows} 行。")
        self.set_status(f"过滤完成：{rows}/{total} 行。")
        # 过滤完成后按配置自动弹出结果预览，便于核对过滤后的数据（按显示列投影）
        if config.PREVIEW_AUTO_AFTER_FILTER:
            self._open_preview("预览：过滤结果", self._project_visible(result))

    def on_reset_filter(self) -> None:
        """重置过滤，恢复为匹配后的全量数据（条件清回默认一行）。"""
        if self.state.merged_df is None:
            return
        self.state.filtered_df = self.state.merged_df.copy()
        self.state.stats_df = None  # 数据变化，旧统计结果失效
        self.state.stats_sheets = []
        self.pages[2].reset_conditions()
        rows = len(self.state.merged_df)
        self.pages[2].show_info(f"已重置，当前为匹配后全量数据：{rows} 行。")
        self.set_status("已重置过滤。")

    # ---- 显示列（隐藏列）管理 ----

    def _base_column_names(self) -> set:
        """基准表（第一个数据源）的列名集合——基准表列不可隐藏。"""
        if not self.state.sources:
            return set()
        df = self.state.dataframes.get(self.state.sources[0])
        return set(df.columns) if df is not None else set()

    def _hideable_columns(self) -> list:
        """可隐藏的列（全部候选列中除基准表列之外）。"""
        base_cols = self._base_column_names()
        return [c for c in self.pages[2].available_columns() if c not in base_cols]

    def _column_sources(self) -> dict:
        """合并结果列 → 来源数据源 (文件路径, 工作表名) 的映射。

        与 merge_engine 的后缀命名对应：
          - 列名在某数据源中精确存在 → 归该数据源（按 sources 顺序，首个匹配）；
          - 否则形如「列名_N」（N≥2）→ 归 sources[N-1]（N 即合并时的
            数据源序号后缀），且该数据源存在去掉后缀的同名列。
        """
        mapping: dict = {}
        for src in self.state.sources:
            df = self.state.dataframes.get(src)
            if df is None:
                continue
            for col in df.columns:
                if str(col) not in mapping:
                    mapping[str(col)] = src
        for col in self.pages[2].available_columns():
            if col in mapping:
                continue
            m = re.match(r"^(.*)_(\d+)$", col)
            if not m:
                continue
            stem, idx = m.group(1), int(m.group(2))
            if 2 <= idx <= len(self.state.sources):
                src = self.state.sources[idx - 1]
                df = self.state.dataframes.get(src)
                if df is not None and stem in df.columns:
                    mapping[col] = src
        return mapping

    def _visible_column_options(self) -> list:
        """「选择显示列」对话框选项：按「文件名[表名]」分组，显示名去掉 _idx 后缀。

        返回 [(分组标题, 列名key, 显示名), ...]，分组标题为来源数据源的
        「文件名[工作表名]」（参考添加工作表对话框）；显示名取该列在来源
        表中的原始列名（合并时加的 _2/_3… 后缀只在显示层去掉，数据不变）。
        """
        mapping = self._column_sources()
        options = []
        for col in self._hideable_columns():
            src = mapping.get(col) or self.state.sources[0]  # 兜底归基准表
            df = self.state.dataframes.get(src)
            display = col
            if df is not None and col not in df.columns:
                m = re.match(r"^(.*)_\d+$", col)
                if m:
                    display = m.group(1)
            path, sheet = src
            options.append((f"{os.path.basename(path)}[{sheet}]", col, display))
        return options

    def on_choose_visible_columns(self) -> None:
        """打开「选择显示列」勾选对话框：勾选 = 显示，未勾选 = 隐藏。

        列按来源数据源「文件名[工作表名]」分组显示，显示名去掉合并加的
        _2/_3… 后缀（数据列名不变）；基准表列不可隐藏（不出现在列表中）。
        """
        columns = self._hideable_columns()
        if not columns:
            messagebox.showinfo("提示", "当前没有可隐藏的列（基准表列不可隐藏）。")
            return
        hidden = {c for c in self.pages[2].get_hidden() if c in columns}
        SheetPickerDialog(
            self.root, "选择显示列",
            self._visible_column_options(),
            on_confirm=self._apply_visible_columns,
            checked_keys=hidden,
            hint_text="勾选要显示的列（未勾选 = 隐藏；按来源文件分组，列名已去除后缀：")

    def _apply_visible_columns(self, keys) -> None:
        """应用显示列选择（keys 为勾选显示的列；取消为 None）。"""
        if keys is None:
            return
        hidden = {c for c in self._hideable_columns() if c not in keys}
        self.pages[2].set_hidden(hidden)
        # 统计页下拉框同步：隐藏列不再出现
        self.pages[3].update_columns(self.pages[2].visible_columns())
        if hidden:
            self.set_status(f"已更新显示列：隐藏 {len(hidden)} 列。")
        else:
            self.set_status("已显示全部列。")
        # 显示列调整后按配置自动弹出当前数据预览（按新显示列投影）
        if config.PREVIEW_AUTO_AFTER_COLUMNS:
            data = (self.state.filtered_df if self.state.filtered_df is not None
                    else self.state.merged_df)
            if data is not None:
                self._open_preview("预览：显示列调整", self._project_visible(data))

    def _project_visible(self, df) -> pd.DataFrame:
        """按过滤页「显示列」设置隐藏列，返回仅含可见列的 DataFrame。

        基准表列受保护：即使隐藏集合误含基准表列也不投影掉。
        """
        base_cols = self._base_column_names()
        hidden = [c for c in self.pages[2].get_hidden()
                  if c in df.columns and c not in base_cols]
        return df.drop(columns=hidden) if hidden else df

    # ---- 分组统计 ----

    def on_compute_stats(self) -> None:
        """按分组列 + 条件行统计符合条件的数据数量，弹预览展示结果。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行统计。")
            return
        try:
            conditions = self.pages[3].get_conditions()
            group_by = self.pages[3].get_group_by()
        except ValueError as exc:
            messagebox.showwarning("统计条件有误", str(exc))
            return

        self.start_progress()
        self.set_status("正在计算统计…")
        try:
            try:
                stats = group_count(
                    self.state.filtered_df if self.state.filtered_df is not None
                    else self.state.merged_df,
                    group_by=group_by, conditions=conditions)
            except Exception as exc:  # 条件/数值不合法需弹窗提示，不崩溃（BLE001 见 .flake8）
                logger.error("统计失败：%s", exc, exc_info=True)
                messagebox.showerror("统计失败", f"统计执行失败：\n{exc}")
                return
            self.state.stats_df = stats
        finally:
            self.stop_progress()

        matched = int(stats[count_column_name(group_by)].sum()) if group_by \
            else int(stats.iloc[0, 0])
        if group_by:
            text = f"✔ 统计完成：{matched} 条符合条件，按「{group_by}」分为 {len(stats)} 组。"
        else:
            text = f"✔ 统计完成：共 {matched} 条符合条件。"
        self.pages[3].show_info(text)
        self.set_status("统计完成，可点「写入统计结果」保存。")
        # 弹出统计结果预览（非模态，便于核对各分组数量）
        self._open_preview("预览：统计结果", stats)

    def on_export(self) -> None:
        """导出最终数据（仅 Sheet「最终数据」；统计结果由「写入统计结果」单独追加）。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行导出。")
            return

        # 导出的数据：优先使用过滤后的结果，未过滤则用合并结果；
        # 按「显示列」设置隐藏不需要的列
        data_df = self.state.filtered_df if self.state.filtered_df is not None else self.state.merged_df
        data_df = self._project_visible(data_df)

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
                out_path = export_excel(data_df, path,
                                        stats_sheets=self.state.stats_sheets)
            except Exception as exc:  # 写入失败需弹窗提示（BLE001 见 .flake8）
                logger.error("导出失败：%s - %s", path, exc, exc_info=True)
                messagebox.showerror("导出失败", f"写入文件失败：\n{exc}")
                return
        finally:
            self.stop_progress()

        self.pages[3].show_info(f"✔ 已导出至：\n{out_path}")
        self.set_status("导出成功。")
        messagebox.showinfo("导出成功", f"结果已保存到：\n{out_path}")

    def on_write_stats(self) -> None:
        """将当前统计结果追加到导出内存（不写文件），导出时一并写入。"""
        if self.state.merged_df is None:
            messagebox.showwarning("提示", "请先执行匹配，再进行统计。")
            return
        if self.state.stats_df is None:
            messagebox.showinfo("提示", "请先点击「计算统计」生成统计结果。")
            return
        # 二级确认：防止误追加
        if not messagebox.askyesno(
                "确认追加",
                "将当前统计结果追加到导出文件（先在内存中累积，点「导出结果」时\n"
                "一并写入；同一份统计可多次追加），确认继续？"):
            return
        names = [n for n, _ in self.state.stats_sheets]
        sheet_name = next_stats_sheet_name(names)
        self.state.stats_sheets.append((sheet_name, self.state.stats_df.copy()))
        self.pages[3].show_info(
            f"✔ 已追加统计结果（工作表：{sheet_name}），"
            f"当前共 {len(self.state.stats_sheets)} 份统计，导出时一并写入。")
        self.set_status(f"统计已加入导出（{sheet_name}）。")
