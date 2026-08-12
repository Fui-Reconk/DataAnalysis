"""文件读取与表头扫描模块。

负责从 Excel 文件加载数据（默认第一个 Sheet），
并扫描所有表格的表头，计算列名并集供主键选择。
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def load_excel(path: str) -> pd.DataFrame:
    """读取 Excel 文件的第一个 Sheet（sheet_name=0）。

    读取失败时向上抛出异常，由调用方捕获并提示用户。
    """
    # 自动检测并统一读取默认第一个 Sheet
    return pd.read_excel(path, sheet_name=0)


def scan_columns(paths: List[str], dataframes: Dict[str, pd.DataFrame]) -> List[str]:
    """扫描所有已加载表格的表头，返回列名并集。

    列名按“首次出现的文件顺序”排列，去重后作为下拉框候选项。
    """
    union: List[str] = []
    seen: set = set()
    for path in paths:
        df = dataframes.get(path)
        if df is None:
            continue
        for col in df.columns:
            if col not in seen:
                seen.add(col)
                union.append(col)
    return union
