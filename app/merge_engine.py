"""左连接匹配引擎。

以第一个加载的表格为基准表（左表），将其余 n-1 个表格
通过 pandas.merge 依次左连接，完成多表数据匹配。
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

# 空值哨兵值：将 NaN 统一替换为该字符串，保证跨表匹配键可比较
NAN_SENTINEL = "<NaN>"


def left_join(dataframes: Dict[str, pd.DataFrame], paths: List[str], key: str) -> pd.DataFrame:
    """以 paths[0] 为基准表，对其余表格依次左连接。

    处理规则：
      - 若某表缺少所选匹配键列，抛出 KeyError 并指明文件与列名。
      - 匹配键列统一转字符串并填充空值，保证数据类型一致。

    重复列名（非主键）通过文件序号后缀区分，避免合并冲突。
    """
    if len(paths) < 2:
        raise ValueError("至少需要两个表格才能执行匹配，请先添加多个文件。")

    base_path = paths[0]
    base = dataframes[base_path].copy()
    _validate_key(base, base_path, key)

    # 基准表匹配键标准化
    base[key] = _normalize_key(base[key])

    result = base
    # 依次左连接其余 n-1 个表格
    for idx, path in enumerate(paths[1:], start=2):
        df = dataframes[path].copy()
        _validate_key(df, path, key)
        df[key] = _normalize_key(df[key])
        # suffixes 以文件序号命名重复列（如 “销售额_2”），避免多次合并冲突
        result = pd.merge(result, df, on=key, how="left", suffixes=("", f"_{idx}"))

    return result


def _normalize_key(series: pd.Series) -> pd.Series:
    """匹配键标准化：空值填充哨兵值，统一转字符串并去除首尾空格。"""
    return series.fillna(NAN_SENTINEL).astype(str).str.strip() # type: ignore


def _validate_key(df: pd.DataFrame, path: str, key: str) -> None:
    """校验表中是否包含所选匹配键列，缺失则报错并指明文件。"""
    if key not in df.columns:
        raise KeyError(f"文件「{path}」中不存在所选匹配键列「{key}」，请检查该文件表头。")
