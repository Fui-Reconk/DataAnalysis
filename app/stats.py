"""默认统计模块（预留区域）。

这是工具提供的“专门的计算模块区域”，供用户自行编写统计逻辑。
GUI 界面会显示“默认统计项：预留”，并在导出时调用本函数生成 Sheet2。
"""
from __future__ import annotations

import pandas as pd


def calculate_default_stats(df: pd.DataFrame) -> pd.DataFrame:
    """计算默认统计项。

    入参为导出时的最终数据表（合并且过滤后的结果）。

    【预留】请在此处自定义统计逻辑，例如：
        - 分组计数：
            return df.groupby("地区").size().reset_index(name="数量")
        - 求和 / 平均值：
            return df.groupby("地区")["销售额"].sum().reset_index()

    当前返回空 DataFrame，表示“未定义统计”。
    """
    # TODO: 在此处添加默认统计逻辑（例如：分组计数、求和、平均值等）
    return pd.DataFrame()
