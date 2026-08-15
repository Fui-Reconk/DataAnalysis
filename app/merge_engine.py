"""左连接匹配引擎。

以第一个加载的数据源（文件+工作表）为基准表（左表），将其余 n-1 个
数据源通过 pandas.merge 依次左连接，完成多表数据匹配。
"""
from __future__ import annotations

import os
from typing import Dict, List

import pandas as pd

# 空值哨兵值：将 NaN 统一替换为该字符串，保证跨表匹配键可比较
NAN_SENTINEL = "<NaN>"


def left_join(dataframes: Dict[tuple, pd.DataFrame], sources: List[tuple], key: str) -> pd.DataFrame:
    """以 sources[0] 为基准表，对其余数据源依次左连接。

    sources 元素为 (文件路径, 工作表名)。处理规则：
      - 若某表缺少所选匹配键列，抛出 KeyError 并指明文件、工作表与列名。
      - 匹配键列统一转字符串并填充空值，保证数据类型一致。

    重复列名（非主键）通过数据源序号后缀区分，避免合并冲突。
    """
    if len(sources) < 2:
        raise ValueError("至少需要两个工作表才能执行匹配，请先添加多个工作表。")

    base_src = sources[0]
    base = dataframes[base_src].copy()
    _validate_key(base, base_src, key)

    # 基准表匹配键标准化
    base[key] = _normalize_key(base[key])

    result = base
    # 依次左连接其余 n-1 个数据源
    for idx, src in enumerate(sources[1:], start=2):
        df = dataframes[src].copy()
        _validate_key(df, src, key)
        df[key] = _normalize_key(df[key])
        # suffixes 以数据源序号命名重复列（如 “销售额_2”），避免多次合并冲突
        result = pd.merge(result, df, on=key, how="left", suffixes=("", f"_{idx}"))

    return result


def _source_label(src: tuple) -> str:
    """数据源的可读名称：文件名[工作表名]。"""
    path, sheet = src
    return f"{os.path.basename(path)}[{sheet}]"


def _normalize_key(series: pd.Series) -> pd.Series:
    """匹配键标准化：空值填充哨兵值，统一转字符串并去除首尾空格。"""
    return series.fillna(NAN_SENTINEL).astype(str).str.strip()  # type: ignore


def _validate_key(df: pd.DataFrame, src: tuple, key: str) -> None:
    """校验表中是否包含所选匹配键列，缺失则报错并指明数据源。"""
    if key not in df.columns:
        raise KeyError(f"文件「{_source_label(src)}」中不存在所选匹配键列「{key}」，请检查该文件表头。")
