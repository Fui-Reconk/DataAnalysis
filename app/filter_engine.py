"""结构化条件过滤引擎。

对合并后的结果表执行「列名 + 操作符 + 比较值」组成的条件列表过滤，
替代旧的自由文本 pandas query 输入。多组条件之间为「并且（AND）」关系。

掩码语义（显式、可预测）：
  - 数值比较（等于/不等于/大于/大于等于/小于/小于等于）：
      * 比较值能解析为数字时，列先 to_numeric 再与数值比较，NaN 行一律排除
        （不等于同样排除 NaN，避免「无数据」行被误判为满足条件）；
      * 比较值不能解析为数字时：列为数值 dtype → 报错提示输入数字；
        否则按字符串比较（先排除 NaN）。
  - 包含/不包含：区分大小写的子串匹配（先排除 NaN）。
  - 为空/不为空：匹配 NaN / None / 空字符串（含纯空白），不需要比较值。
"""
from __future__ import annotations

import pandas as pd

# 条件操作符（页面下拉框与引擎共用）
OPS = ["等于", "不等于", "大于", "大于等于", "小于", "小于等于",
       "包含", "不包含", "为空", "不为空"]

# 需要比较值的操作符（为空/不为空之外）
VALUE_OPS = frozenset(OPS[:8])


def apply_conditions(df: pd.DataFrame, conditions: list) -> pd.DataFrame:
    """按条件列表过滤（全部为「并且」关系），返回过滤后的 DataFrame。

    conditions 元素：{"column": 列名, "op": OPS 之一, "value": 比较值字符串}。
    条件为空时返回数据副本；列不存在 / 值不合法时抛出 ValueError，由上层提示。
    """
    if not conditions:
        return df.copy()

    result = df
    for cond in conditions:
        col = (cond.get("column") or "").strip()
        op = (cond.get("op") or "").strip()
        value = cond.get("value")
        value = "" if value is None else str(value).strip()
        if not col:
            raise ValueError("未选择列名。")
        if not op:
            raise ValueError(f"「{col}」未选择条件。")
        if op not in OPS:
            raise ValueError(f"「{col}」条件「{op}」不受支持。")
        if col not in df.columns:
            raise ValueError(f"所选列「{col}」不在匹配结果中。")
        result = result[_mask(result[col], op, value)]
    return result


def _mask(s: pd.Series, op: str, value: str) -> pd.Series:
    """生成单列过滤掩码（布尔 Series，索引与 s 对齐）。"""
    if op == "为空":
        return s.isna() | (s.astype(str).str.strip() == "")
    if op == "不为空":
        return ~(s.isna() | (s.astype(str).str.strip() == ""))

    if not value:
        raise ValueError(f"条件「{op}」请输入比较值。")
    if op in ("包含", "不包含"):
        contains = s.notna() & s.astype(str).str.contains(value, regex=False)
        return ~contains if op == "不包含" else contains

    # 数值比较：比较值可解析为数字 → 列转数值比较；否则字符串比较
    try:
        num_value = float(value)
    except ValueError:
        if pd.api.types.is_numeric_dtype(s):
            raise ValueError(f"列「{s.name}」为数值列，请输入数字。")
        return _string_compare(s, op, value)

    num = pd.to_numeric(s, errors="coerce")
    if op == "等于":
        return num == num_value
    if op == "不等于":
        return num.notna() & (num != num_value)
    if op == "大于":
        return num.notna() & (num > num_value)
    if op == "大于等于":
        return num.notna() & (num >= num_value)
    if op == "小于":
        return num.notna() & (num < num_value)
    # op == "小于等于"
    return num.notna() & (num <= num_value)


def _string_compare(s: pd.Series, op: str, value: str) -> pd.Series:
    """字符串比较（先排除 NaN；value 无法解析为数字时使用）。"""
    s = s.astype(str)
    if op == "等于":
        return s == value
    if op == "不等于":
        return s != value
    if op == "大于":
        return s > value
    if op == "大于等于":
        return s >= value
    if op == "小于":
        return s < value
    return s <= value  # op == "小于等于"
