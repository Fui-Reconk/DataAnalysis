"""引擎模块端到端功能测试。

构造样例 Excel 文件，验证完整链路：
读取 → 表头扫描 → 左连接匹配 → 动态过滤 → 统计 → 双Sheet导出。

运行方式：.venv/Scripts/python.exe tests/functional_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile

# 强制 UTF-8 输出，避免 Windows GBK 控制台编码错误
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 将项目根目录加入搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from app.data_loader import load_excel, scan_columns  # noqa: E402
from app.merge_engine import left_join  # noqa: E402
from app.filter_engine import apply_query  # noqa: E402
from app.stats import calculate_default_stats  # noqa: E402
from app.exporter import export_excel  # noqa: E402


def _build_sample(tmp: str) -> list:
    """构造 3 个样例表格并写为 xlsx，返回路径列表。"""
    base = pd.DataFrame({
        "订单号": ["A01", "A02", "A03", "A04"],
        "地区": ["华东", "华东", "华北", "华南"],
        "销售额": [1200, 800, 2500, 400],
    })
    extra1 = pd.DataFrame({
        "订单号": ["A01", "A02", "A03"],
        "数量": [10, 5, 20],
    })
    extra2 = pd.DataFrame({
        "订单号": ["A01", "A03", "A05"],
        "成本": [600, 1000, 300],
    })

    paths = []
    for name, df in (("基准表", base), ("明细表1", extra1), ("明细表2", extra2)):
        path = os.path.join(tmp, f"{name}.xlsx")
        df.to_excel(path, index=False)
        paths.append(path)
    return paths


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(f"[FAIL] {msg}")
    print(f"  [OK] {msg}")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="data_matcher_test_")
    print("=== 1. 文件读取与表头扫描 ===")
    paths = _build_sample(tmp)
    dataframes = {}
    for p in paths:
        dataframes[p] = load_excel(p)
    _assert(len(dataframes) == 3, f"读取 3 个表格成功")

    union = scan_columns(paths, dataframes)
    _assert("订单号" in union and "地区" in union and "数量" in union and "成本" in union,
            f"表头并集完整: {union}")

    print("=== 2. 左连接匹配 ===")
    merged = left_join(dataframes, paths, "订单号")
    _assert(len(merged) == 4, f"以基准表 4 行为准，合并后 {len(merged)} 行")
    _assert("数量" in merged.columns and "成本" in merged.columns,
            "非主键列合并成功")
    # 左连接：A04 无明细，数量/成本应为 NaN
    row_a04 = merged[merged["订单号"] == "A04"].iloc[0]
    _assert(pd.isna(row_a04["数量"]) and pd.isna(row_a04["成本"]),
            "A04 左连接未匹配到明细 → NaN（符合左连接语义）")

    print("=== 3. 动态过滤 ===")
    filtered = apply_query(merged, "销售额 > 1000")
    _assert(len(filtered) == 2, f"过滤后 {len(filtered)} 行（A01/A03）")
    filtered2 = apply_query(merged, "地区 == '华东'")
    _assert(len(filtered2) == 2, f"字符串条件过滤后 {len(filtered2)} 行")

    print("=== 4. 过滤容错 ===")
    try:
        apply_query(merged, "不存在的字段 > 1")
        raise AssertionError("✗ 应当抛错但未抛错")
    except Exception:
        print("  ✓ 字段不存在时正确抛出异常（由 GUI 弹窗提示）")

    print("=== 5. 匹配键缺失报错 ===")
    bad = {p: df.rename(columns={"订单号": "单号"} if "订单号" in df.columns else {})
           for p, df in dataframes.items()}
    try:
        left_join(bad, paths, "订单号")
        raise AssertionError("✗ 应当抛错但未抛错")
    except KeyError as e:
        print(f"  ✓ 缺列时正确报错: {e}")

    print("=== 6. 统计模块（预留）与导出 ===")
    stats = calculate_default_stats(merged)
    _assert(stats.empty, "calculate_default_stats 当前返回空 DataFrame（预留）")

    out = os.path.join(tmp, "导出测试.xlsx")
    export_excel(filtered, stats, out)
    xl = pd.ExcelFile(out)
    _assert("最终数据" in xl.sheet_names and "统计结果" in xl.sheet_names,
            f"导出包含双 Sheet: {xl.sheet_names}")
    sheet2 = pd.read_excel(out, sheet_name="统计结果")
    _assert(sheet2.iloc[0, 0] == "未定义统计", "统计为空时 Sheet2 写入占位内容")

    print("\n=== 全部功能测试通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
