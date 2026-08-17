"""Excel 导出模块。

export_excel 将最终数据与「写入统计结果」累积在内存中的统计表
一并写入 Excel：Sheet1 为「最终数据」，其后按追加顺序写入各统计
工作表（统计结果、统计结果_2、…）。
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd


def default_export_name() -> str:
    """生成默认导出文件名：匹配结果_时间戳.xlsx。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"匹配结果_{timestamp}.xlsx"


def next_stats_sheet_name(existing: list, base: str = "统计结果") -> str:
    """生成下一个不重名的统计 sheet 名（统计结果, 统计结果_2, …）。"""
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def export_excel(data_df: pd.DataFrame, path: str,
                 stats_sheets: list | None = None) -> str:
    """将最终数据与统计结果导出为 Excel 文件。

    Sheet1 为「最终数据」；stats_sheets 为 [(sheet名, DataFrame), ...]，
    每个元素按顺序导出为一个额外的工作表（「写入统计结果」累积的统计）。
    返回绝对路径。
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        data_df.to_excel(writer, sheet_name="最终数据", index=False)
        for sheet_name, sdf in (stats_sheets or []):
            sdf.to_excel(writer, sheet_name=sheet_name, index=False)
    return os.path.abspath(path)
