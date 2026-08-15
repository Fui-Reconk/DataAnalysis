"""文件读取与表头扫描模块。

负责从 Excel 文件加载指定工作表（默认第一个 Sheet），
列出文件内全部工作表名，并扫描所有数据源的表头，
计算列名并集供主键选择。
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def list_sheets(path: str) -> List[str]:
    """列出 Excel 文件内的全部工作表名（供选择/暂存池使用）。"""
    return pd.ExcelFile(path).sheet_names


def load_excel(path: str, sheet: object = 0) -> pd.DataFrame:
    """读取 Excel 文件的指定工作表（默认第一个 Sheet）。

    sheet 可为工作表名（str）或序号（int，从 0 开始）。
    读取失败时向上抛出异常，由调用方捕获并提示用户。
    """
    return pd.read_excel(path, sheet_name=sheet)


def scan_columns(sources: List[tuple], dataframes: Dict[tuple, pd.DataFrame]) -> List[str]:
    """扫描所有已加载数据源的表头，返回列名并集。

    sources 元素为 (文件路径, 工作表名)；列名按“首次出现的数据源顺序”
    排列，去重后作为下拉框候选项。
    """
    union: List[str] = []
    seen: set = set()
    for src in sources:
        df = dataframes.get(src)
        if df is None:
            continue
        for col in df.columns:
            if col not in seen:
                seen.add(col)
                union.append(col)
    return union
