"""Excel 导出模块。

将最终数据与统计结果写入 Excel 双 Sheet：
  - Sheet1：合并并经过用户条件过滤后的最终数据
  - Sheet2：calculate_default_stats 计算出的统计结果
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

# 统计结果为空时，Sheet2 写入的占位内容
STATS_EMPTY_LABEL = "未定义统计"


def default_export_name() -> str:
    """生成默认导出文件名：匹配结果_时间戳.xlsx。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"匹配结果_{timestamp}.xlsx"


def export_excel(data_df: pd.DataFrame, stats_df: pd.DataFrame, path: str) -> str:
    """将最终数据与统计结果导出为 Excel 双 Sheet 文件。

    若统计结果为空，则 Sheet2 写入“未定义统计”占位内容。
    返回导出文件的绝对路径。
    """
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # Sheet1：合并并经过过滤后的最终数据
        data_df.to_excel(writer, sheet_name="最终数据", index=False)

        # Sheet2：统计结果（为空则写入占位内容）
        if stats_df is None or stats_df.empty:
            placeholder = pd.DataFrame({"统计结果": [STATS_EMPTY_LABEL]})
            placeholder.to_excel(writer, sheet_name="统计结果", index=False)
        else:
            stats_df.to_excel(writer, sheet_name="统计结果", index=False)

    return os.path.abspath(path)
