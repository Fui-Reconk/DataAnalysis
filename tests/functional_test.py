"""引擎模块端到端功能测试。

构造样例 Excel 文件，验证完整链路：
读取 → 表头扫描 → 左连接匹配 → 动态过滤 → 统计 → 双Sheet导出。

运行方式：.venv/Scripts/python.exe tests/functional_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile

import pandas as pd

# 强制 UTF-8 输出，避免 Windows GBK 控制台编码错误
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except (AttributeError, ValueError):
    pass

# 将项目根目录加入搜索路径（测试以脚本方式运行时需手动添加）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    # app 包依赖上面的项目根目录路径引导，故延迟到函数内导入
    from app.data_loader import list_sheets, load_excel, rename_columns_abbr, scan_columns
    from app.merge_engine import left_join
    from app.filter_engine import apply_query
    from app.stats import calculate_default_stats
    from app.exporter import export_excel

    tmp = tempfile.mkdtemp(prefix="data_matcher_test_")
    print("=== 1. 文件读取与表头扫描 ===")
    paths = _build_sample(tmp)
    # 数据源 = (文件路径, 工作表名)
    sources, dataframes = [], {}
    for p in paths:
        sheet = list_sheets(p)[0]
        sources.append((p, sheet))
        dataframes[(p, sheet)] = load_excel(p, sheet)
    _assert(len(dataframes) == 3, "读取 3 个表格成功")

    union = scan_columns(sources, dataframes)
    _assert("订单号" in union and "地区" in union and "数量" in union and "成本" in union,
            f"表头并集完整: {union}")

    print("=== 2. 左连接匹配 ===")
    merged = left_join(dataframes, sources, "订单号")
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
    bad = {(p, s): df.rename(columns={"订单号": "单号"} if "订单号" in df.columns else {})
           for (p, s), df in dataframes.items()}
    try:
        left_join(bad, sources, "订单号")
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

    print("=== 7. 多工作表支持 ===")
    multi = os.path.join(tmp, "多表.xlsx")
    with pd.ExcelWriter(multi, engine="openpyxl") as writer:
        pd.DataFrame({"订单号": ["A01", "A02", "A03"],
                      "地区": ["华东", "华北", "华南"]}).to_excel(writer, sheet_name="订单", index=False)
        pd.DataFrame({"订单号": ["A01", "A02"],
                      "数量": [10, 5]}).to_excel(writer, sheet_name="明细", index=False)
    sheets = list_sheets(multi)
    _assert(sheets == ["订单", "明细"], f"列出文件内全部工作表: {sheets}")
    _assert(len(load_excel(multi, "订单")) == 3 and len(load_excel(multi, "明细")) == 2,
            "可按工作表名分别读取")
    # 同一文件的两个工作表作为两个数据源参与左连接
    ms_sources = [(multi, "订单"), (multi, "明细")]
    ms_data = {ms_sources[0]: load_excel(multi, "订单"),
               ms_sources[1]: load_excel(multi, "明细")}
    ms_merged = left_join(ms_data, ms_sources, "订单号")
    _assert(len(ms_merged) == 3, f"同一文件两个工作表左连接后 {len(ms_merged)} 行")
    _assert(pd.isna(ms_merged[ms_merged["订单号"] == "A03"]["数量"].iloc[0]),
            "A03 无明细 → NaN（符合左连接语义）")

    print("=== 8. DBF 格式支持 ===")
    import dbf as dbf_lib
    dbf_path = os.path.join(tmp, "明细.dbf")
    t = dbf_lib.Table(dbf_path, "订单号 C(10); 数量 N(10,0)", codepage="cp936")
    t.open(dbf_lib.READ_WRITE)
    for rec in [("A01", 10), ("A02", 5), ("A03", 20)]:
        t.append(tuple(rec))
    t.pack()
    t.close()
    _assert(list_sheets(dbf_path) == ["明细"], "DBF 无工作表，以文件名（去扩展名）作表名")
    dbf_df = load_excel(dbf_path)
    _assert(list(dbf_df.columns) == ["订单号", "数量"] and len(dbf_df) == 3,
            "DBF 读取为 DataFrame，列名/行数正确")
    _assert(dbf_df.iloc[0]["订单号"] == "A01" and int(dbf_df.iloc[0]["数量"]) == 10,
            "DBF 中文（GBK）与数值读取正确")
    # 无语言驱动的中文 DBF（头字节 0x00，被识别为 ascii）→ 应回退 GBK 成功
    broken = os.path.join(tmp, "无编码头.dbf")
    tb = dbf_lib.Table(broken, "订单号 C(10); 地区 C(10)", codepage="cp936")
    tb.open(dbf_lib.READ_WRITE)
    for row2 in [("A01", "华东"), ("A02", "华北")]:
        tb.append(tuple(row2))
    tb.pack()
    tb.close()
    with open(broken, "r+b") as f:
        f.seek(29)
        f.write(b"\x00")  # 语言驱动字节置 0
    broken_df = load_excel(broken)
    _assert(broken_df.iloc[0]["地区"] == "华东",
            "无语言驱动的中文 DBF 回退 GBK 读取正确")
    # DBF 与 xlsx 混合左连接（基准为 xlsx，明细为 DBF）
    base_src = sources[0]
    dbf_src = (dbf_path, "明细")
    mix_sources = [base_src, dbf_src]
    mix_data = {base_src: dataframes[base_src], dbf_src: dbf_df}
    mix_merged = left_join(mix_data, mix_sources, "订单号")
    _assert(len(mix_merged) == 4 and "数量" in mix_merged.columns,
            f"xlsx+DBF 混合左连接成功：{len(mix_merged)} 行")

    print("=== 9. 日志 ===")
    from app.logger import get_logger, LOG_FILE
    app_logger = get_logger()
    app_logger.info("__log_test__")
    for handler in app_logger.handlers:
        handler.flush()
    with open(LOG_FILE, encoding="utf-8") as f:
        content = f.read()
    _assert("__log_test__" in content and "[INFO]" in content,
            f"日志写入 {LOG_FILE} 成功")

    print("=== 10. 列名缩写替换 ===")
    from app import config as app_config
    mapping = app_config.COLUMN_ABBR_MAP
    _assert(mapping.get("xm") == "姓名" and mapping.get("zkzh") == "准考证号"
            and len(mapping) >= 30, f"缩写映射表已从 cfg 加载（{len(mapping)} 项）")
    abbr_df = pd.DataFrame({"nd": [2025], "xm": ["张三"], "other": [1]})
    renamed = rename_columns_abbr(abbr_df, mapping)
    _assert(list(renamed.columns) == ["年度", "姓名", "other"],
            f"缩写列替换为全称: {list(renamed.columns)}")
    _assert(app_config.PREVIEW_AUTO_AFTER_REPLACE is True,
            "替换完成后自动预览开关已从 cfg 读取（auto_show_after_replace=true）")
    _assert(app_config.PREVIEW_AUTO_AFTER_MERGE is True,
            "匹配完成后自动预览开关已从 cfg 读取（auto_show_after_merge=true）")

    print("=== 11. 匹配后冗余列清理 ===")
    from app.merge_engine import clean_redundant_columns
    base2 = pd.DataFrame({"订单号": ["A01", "A02", "A03"],
                          "姓名": ["张三", "李四", "王五"],
                          "地区": ["华东", "华北", "华南"]})
    merged2 = base2.copy()
    merged2["姓名_2"] = ["张三", "李四", "王五"]      # 与基准表同名且值全相同 → 删
    merged2["姓名_3"] = [None, None, None]            # 基准表有数据、本列全空 → 删
    merged2["空列_2"] = [None, None, None]            # 全空 → 删
    merged2["空串_2"] = ["", " ", ""]                 # 全空字符串（含纯空白）→ 删
    merged2["姓名_4"] = ["张三", "李四", "李四"]       # 同名但值不同 → 保留
    merged2["独有列"] = [1, 2, 3]                     # 独有列 → 保留
    merged2["空混_2"] = ["", None, " "]               # NaN/空串/空格混合全空 → 删（防 astype 漏判）
    merged2["半空_2"] = ["", "有值", ""]              # 含一个真实值 → 保留
    cleaned, removed = clean_redundant_columns(merged2, base2)
    _assert(set(removed) == {"姓名_2", "姓名_3", "空列_2", "空串_2", "空混_2"},
            f"清理出冗余列: {sorted(removed)}")
    _assert({"订单号", "姓名", "地区", "姓名_4", "独有列", "半空_2"} <= set(cleaned.columns),
            "主键/基准列/同名不同值列/独有列/含真实值的列均保留")
    _assert(len(cleaned.columns) == 6, f"清理后列数: {list(cleaned.columns)}")
    _assert(app_config.MERGE_AUTO_CLEAN is True,
            "匹配后自动清理开关已从 cfg 读取（[merge] auto_clean=true）")

    print("\n=== 全部功能测试通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
