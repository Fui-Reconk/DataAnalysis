"""文件读取与表头扫描模块。

负责从 Excel 文件加载指定工作表（默认第一个 Sheet），或从 DBF 文件
加载整表；列出数据源内的表名；扫描所有数据源的表头，计算列名并集
供主键选择。
"""
from __future__ import annotations

import os
from typing import Dict, List

import dbfread
import pandas as pd


def is_dbf(path: str) -> bool:
    """判断文件是否为 DBF 格式（按扩展名）。"""
    return path.lower().endswith(".dbf")


def _dbf_table_name(path: str) -> str:
    """DBF 无工作表概念，以文件名（去扩展名）作为表名。"""
    return os.path.splitext(os.path.basename(path))[0]


def read_dbf(path: str) -> pd.DataFrame:
    """读取 DBF 文件为 DataFrame（dbfread）。

    编码策略：先按文件头 codepage 自动识别；解码失败（常见于无语言驱动
    的中文 DBF，头字节 0x00 被识别为 ascii）时回退 GBK 重试。
    读取失败时向上抛出异常，由调用方捕获并提示用户。
    """
    try:
        return _read_dbf_with(path, None)
    except Exception:
        return _read_dbf_with(path, "gbk")  # 中文 DBF 常用编码兜底


def _read_dbf_with(path: str, encoding) -> pd.DataFrame:
    """以指定编码读取 DBF（encoding=None 时由文件头自动识别）。

    构造与迭代转换都可能抛编码异常（如 ascii 解码中文），
    需整体在调用方 try 中覆盖。
    """
    table = dbfread.DBF(path, encoding=encoding)
    return pd.DataFrame(table)


def list_sheets(path: str) -> List[str]:
    """列出文件内的全部表名：Excel 返回工作表名，DBF 返回文件名（去扩展名）。"""
    if is_dbf(path):
        return [_dbf_table_name(path)]
    return pd.ExcelFile(path).sheet_names


def load_excel(path: str, sheet: object = 0) -> pd.DataFrame:
    """读取指定数据源：Excel 按工作表（默认第一个），DBF 读取整表。

    sheet 可为工作表名（str）或序号（int，从 0 开始）；DBF 忽略该参数。
    读取失败时向上抛出异常，由调用方捕获并提示用户。
    """
    if is_dbf(path):
        return read_dbf(path)
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
