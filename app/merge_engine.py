"""左连接匹配引擎。

以第一个加载的数据源（文件+工作表）为基准表（左表），将其余 n-1 个
数据源通过 pandas.merge 依次左连接，完成多表数据匹配。
"""
from __future__ import annotations

import os
import re
from typing import Dict, List

import pandas as pd

# 空值哨兵值：将 NaN 统一替换为该字符串，保证跨表匹配键可比较
NAN_SENTINEL = "<NaN>"

# 重复列后缀：pandas.merge suffixes 生成（如 “姓名_2”），用于识别与基准表同名的列
_TWIN_SUFFIX = re.compile(r"_\d+$")


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


def clean_redundant_columns(merged: pd.DataFrame, base: pd.DataFrame) -> tuple[pd.DataFrame, List[str]]:
    """删除合并结果中非基准表的冗余列，返回 (清理后, 被删列名列表)。

    删除规则（仅作用于非基准表列，基准表自身列永不删除）：
      - 全空列：全部为 NaN / None / 空字符串（含纯空白）；
      - 与基准表同名列（去 _N 后缀，如 姓名_2 ↔ 姓名）且未提供任何新值的列：
        非基准列**有值的每一行**都与基准列相同（左连接未匹配行的 NaN 无信息量，
        不计为差异——否则未覆盖全量行的同名列会全部残留）；基准列为空而非基准
        列有值则保留（该列含额外数据）；含基准表有数据而该列全空的情形（被全空
        规则覆盖）。

    效率：按列名配对，比较次数 O(非基准列数)；数值列只做 isna 布尔扫描，
    不做字符串转换，大数据量下与合并本身同量级。
    """
    base_cols = set(base.columns)
    drop: List[str] = []
    for col in merged.columns:
        if col in base_cols:
            continue  # 基准表列永不删除
        if _is_all_empty(merged[col]):
            drop.append(col)
            continue
        stem = _TWIN_SUFFIX.sub("", col)
        if stem in base_cols and _redundant_vs_base(merged[col], merged[stem]):
            drop.append(col)
    if drop:
        merged = merged.drop(columns=drop)
    return merged, drop


def _is_all_empty(s: pd.Series) -> bool:
    """全空列：全部为 NaN / None / 空字符串（含纯空白）。

    数值类 dtype 直接布尔扫描 isna；仅 object / string 列才检查空串，
    避免对数值列做昂贵的 astype(str) 全量字符串转换。
    注意必须先 fillna("") 再 astype(str)：否则 NaN 会被转成 "nan" 字符串，
    导致「NaN 与空串混合」的全空列漏判（真实 Excel 数据常见）。
    """
    if s.isna().all():
        return True
    if s.dtype == object or isinstance(s.dtype, pd.StringDtype):
        return bool(s.fillna("").astype(str).str.strip().eq("").all())
    return False


def _redundant_vs_base(a: pd.Series, b: pd.Series) -> bool:
    """非基准列 a 相对基准列 b 是否冗余（a 未提供任何 b 没有的新值）。

    a 有值的每一行都必须与 b 相同；a 的 NaN（左连接未匹配行）不计为差异。
    若 b 为空而 a 有值 → 不相等，保留（a 含额外数据）。
    """
    x = a.to_numpy()
    y = b.to_numpy()
    return bool(((x == y) | pd.isna(x)).all())
