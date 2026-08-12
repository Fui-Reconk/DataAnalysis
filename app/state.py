"""AppState：整个应用共享的运行时数据。

页面与控制器通过同一个 AppState 实例读写数据，
保证状态单一来源，避免在各页面间重复传递。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class AppState:
    # 已添加文件的完整路径列表（顺序即加载顺序，第一个文件作为匹配基准表）
    file_paths: list = field(default_factory=list)
    # 文件路径 -> 已读取的 DataFrame（仅包含读取成功的文件）
    dataframes: dict = field(default_factory=dict)
    # 全部表头的列名并集（按首次出现顺序）
    column_union: list = field(default_factory=list)
    # 用户选择的唯一标识项（匹配主键）
    key_column: Optional[str] = None
    # 左连接合并后的结果表
    merged_df: Optional[pd.DataFrame] = None
    # 经用户条件过滤后的最终数据表（未过滤时与 merged_df 相同）
    filtered_df: Optional[pd.DataFrame] = None
