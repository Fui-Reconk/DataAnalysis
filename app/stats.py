"""分组统计引擎。

按统计页配置对当前数据执行分组计数：先应用统计条件（复用过滤引擎的
结构化条件），再按分组列分类，统计每组符合条件的数据数量。
"""
from __future__ import annotations

import pandas as pd

from app.filter_engine import apply_conditions


def count_column_name(group_by: str | None) -> str:
    """分组计数结果中「数量」列的名字；分组列恰为「数量」时自动避让重名。"""
    return "数量" if group_by != "数量" else "数量（计数）"


def group_count(df: pd.DataFrame, group_by: str | None = None,
                conditions: list | None = None) -> pd.DataFrame:
    """统计符合条件的数据数量，可按列分组。

    参数：
      - df：待统计数据（当前过滤结果或合并结果）
      - group_by：分组列名；None 表示不分组，只返回总数量
      - conditions：统计条件（与过滤页同格式的 [{"column","op","value"}]），
        全部为「并且」关系；None/空表示统计全部数据

    返回：
      - 不分组：[数量] 单行表
      - 分组：[分组列, 数量]（分组列恰为「数量」时计数列名为「数量（计数）」），
        按分组列出现顺序；分组列中的空值（NaN）自成一组（dropna=False），
        不丢失数据
    """
    if conditions:
        df = apply_conditions(df, conditions)
    count_col = count_column_name(group_by)
    if not group_by:
        return pd.DataFrame({count_col: [len(df)]})
    return df.groupby(group_by, dropna=False).size().reset_index(name=count_col)
