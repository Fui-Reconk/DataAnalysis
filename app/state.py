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
    # 已添加数据源列表（元素为 (文件路径, 工作表名)，顺序即加载顺序，
    # 第一个数据源作为匹配基准表；同一文件可添加多个工作表）
    sources: list = field(default_factory=list)
    # (文件路径, 工作表名) -> 已读取的 DataFrame
    dataframes: dict = field(default_factory=dict)
    # 暂存池：文件路径 -> 该文件全部工作表名。
    # 文件只要添加过任意工作表即进入暂存池，之后可随时直接添加其
    # 其它工作表，无需再次选择文件。
    staged_files: dict = field(default_factory=dict)
    # 用户选择的唯一标识项（匹配主键）
    key_column: Optional[str] = None
    # 左连接合并后的结果表
    merged_df: Optional[pd.DataFrame] = None
    # 经用户条件过滤后的最终数据表（未过滤时与 merged_df 相同）
    filtered_df: Optional[pd.DataFrame] = None
