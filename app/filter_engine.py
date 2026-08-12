"""动态过滤引擎。

利用 pandas 的 query() 方法，对合并后的结果表执行
用户自定义的条件过滤，并对错误进行容错处理。
"""
from __future__ import annotations

import pandas as pd


def apply_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """对 DataFrame 执行 pandas query 过滤。

    查询语句为空时原样返回数据副本；
    语法错误或字段不存在时抛出异常，由上层弹窗提示，不崩溃。
    """
    query = (query or "").strip()
    if not query:
        return df.copy()
    return df.query(query)
