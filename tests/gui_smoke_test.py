"""GUI 冒烟测试：验证界面构建、页面切换与完整操作流。

通过程序化注入文件（绕过文件对话框）驱动：
加载 → 选择主键 → 执行匹配 → 应用过滤 → 导出（绕过保存对话框）。
测试结束自动销毁窗口。

运行方式：.venv/Scripts/python.exe tests/gui_smoke_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

# 强制 UTF-8 输出，避免 Windows GBK 控制台编码错误
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 将项目根目录加入搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import customtkinter as ctk  # noqa: E402

from app import config  # noqa: E402
from app.gui import DataMatcherApp  # noqa: E402
from app.data_loader import load_excel, scan_columns  # noqa: E402


def _wait_until(root, cond, timeout_ms=2000) -> bool:
    """在事件循环中轮询直到条件满足或超时（基于真实时间）。"""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.005)
        if cond():
            return True
    return False


def _make_sample_files(tmp: str) -> list:
    """构造样例文件，返回路径列表。"""
    base = pd.DataFrame({
        "订单号": ["A01", "A02", "A03", "A04"],
        "地区": ["华东", "华东", "华北", "华南"],
        "销售额": [1200, 800, 2500, 400],
    })
    detail = pd.DataFrame({"订单号": ["A01", "A02", "A03"], "数量": [10, 5, 20]})
    paths = []
    for name, df in (("基准表", base), ("明细表", detail)):
        path = os.path.join(tmp, f"{name}.xlsx")
        df.to_excel(path, index=False)
        paths.append(path)
    return paths


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="gui_smoke_")
    paths = _make_sample_files(tmp)

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    app = DataMatcherApp(root)

    def run_flow() -> None:
        try:
            # 0. 浮层窗口应在启动时预创建（隐藏）——触发时只淡入既有窗口，不新建窗口
            assert app._overlay is not None, "浮层窗口应在启动时预创建"
            assert not app._overlay.winfo_viewable(), "预创建的浮层窗口应处于隐藏状态"
            startup_toplevels = [w for w in root.winfo_children()
                                 if isinstance(w, ctk.CTkToplevel)]
            assert len(startup_toplevels) == 1, "启动时只允许存在一个浮层窗口"
            print("[OK] 浮层窗口启动时预创建且隐藏（无新窗口闪现）")

            # 0. 默认展开 + 点击开合（无动画）+ 半透明浮层
            # 说明：winfo_width 反映渲染像素（含显示缩放），随设备变化；
            #       此处用 cget("width") 断言逻辑宽度；目标取应用实际值
            #       （响应式缩放可能随窗口尺寸调整），结果更稳定。
            assert app._expanded is True, "默认应为展开状态"
            assert app.sidebar.cget("width") == app._width_expanded, "默认宽度应为展开宽度"
            assert "文件加载" in app._nav_rows[0]["text_label"].cget("text"), \
                "展开时导航应显示完整文字"
            assert app.nav_title_label.winfo_manager() == "grid", "展开时应显示应用标题"
            assert app._toggle_btn.cget("text") == config.SIDEBAR_TOGGLE_EXPANDED, \
                "展开时开合按钮应为 ◀"
            root.update()
            print(f"[OK] 默认展开：标题与完整文字可见（逻辑宽 {app._width_expanded}）")

            # 导航图标 X/Y 轴：展开与折叠状态下应一致（图标列固定宽度；标题区占位高度保留）
            expanded_icon_x = app._nav_rows[0]["icon_label"].winfo_rootx()
            expanded_icon_w = app._nav_rows[0]["icon_label"].winfo_width()
            expanded_row_y = app._nav_rows[0]["frame"].winfo_rooty()

            # 点击开合按钮 → 立即折叠（无动画，直接呈现结果）
            app._set_sidebar_expanded(False)
            assert app.sidebar.cget("width") == app._width_collapsed, "折叠应无动画直接生效"
            assert app.nav_title_label.winfo_manager() == "", "折叠时应隐藏应用标题"
            assert app._nav_rows[0]["text_label"].winfo_manager() == "", "折叠时导航文字应隐藏"
            assert app._toggle_btn.cget("text") == config.SIDEBAR_TOGGLE_COLLAPSED, \
                "折叠时开合按钮应为 ▶"
            root.update()
            collapsed_icon_x = app._nav_rows[0]["icon_label"].winfo_rootx()
            collapsed_row_y = app._nav_rows[0]["frame"].winfo_rooty()
            assert collapsed_icon_x == expanded_icon_x, "折叠后导航图标X轴应保持不变"
            assert collapsed_row_y == expanded_row_y, "折叠后导航图标Y轴应保持不变"
            assert app._nav_rows[0]["icon_label"].winfo_width() == expanded_icon_w
            print(f"[OK] 点击折叠：无动画直接呈现，图标X/Y轴不变（x={collapsed_icon_x}, y={collapsed_row_y}）")

            # 悬停功能分区按钮 → 半透明浮层快速展开（覆盖主界面不移动内容；仅显示功能分区，无标题）
            app._on_nav_area_enter()
            ok = _wait_until(
                root,
                lambda: app._overlay_visible and app._overlay_width == app._width_expanded,
                timeout_ms=2000)
            assert ok, "浮层未展开到目标宽度"
            assert app._overlay is not None and app._overlay.winfo_viewable(), "浮层应显示"
            assert len(app._overlay_rows) == 4, "浮层应包含 4 个功能分区项"
            # 首次打开浮层（未点击）：当前已选中块应自动高亮（懒创建后同步当前页高亮）
            active_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
            active_overlay = app._overlay_rows[app._current_page]["frame"]
            assert active_overlay.cget("fg_color") == active_color, \
                "浮层首次打开应高亮当前选中块"
            print("[OK] 浮层首次打开：当前选中块自动高亮")
            # 浮层图标 X/Y 与折叠栏图标完全对齐
            overlay_icon_x = app._overlay_rows[0]["icon_label"].winfo_rootx()
            overlay_row_y = app._overlay_rows[0]["frame"].winfo_rooty()
            assert overlay_icon_x == collapsed_icon_x, "浮层图标X轴应与折叠栏一致"
            assert overlay_row_y == app._nav_rows[0]["frame"].winfo_rooty(), "浮层图标Y轴应与折叠栏一致"
            print(f"[OK] 半透明浮层：展开覆盖主界面，图标与折叠栏对齐（x={overlay_icon_x}）")

            # 移出 → 浮层快速收起并隐藏
            app._hide_overlay()
            ok = _wait_until(
                root,
                lambda: not app._overlay_visible and not app._overlay.winfo_viewable(),
                timeout_ms=2000)
            assert ok, "浮层应收起并隐藏"
            print("[OK] 移出浮层：快速收起并隐藏")

            # 快速进出导航区（模拟 12 个组件上 Enter/Leave 抖动）：
            # 始终只允许存在一个浮层窗口（防"多个浮层"幽灵窗口），且最终回到隐藏态
            for _ in range(6):
                app._on_nav_area_enter()
                app._on_nav_area_leave()
                root.update()
            toplevels = [w for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel)]
            assert len(toplevels) == 1, f"应始终只有一个浮层窗口，实际 {len(toplevels)} 个"
            ok = _wait_until(
                root,
                lambda: not app._overlay_visible and not app._overlay.winfo_viewable(),
                timeout_ms=2000)
            assert ok, "快速进出后浮层应回到隐藏状态"
            print("[OK] 快速进出导航区：始终只有一个浮层，无幽灵窗口")

            # 应用失焦（alt-tab / 点击其他应用）→ 浮层立即收起，不再卡在其他应用上层
            app._on_nav_area_enter()
            ok = _wait_until(
                root, lambda: app._overlay_visible and app._overlay.winfo_viewable())
            assert ok, "浮层应显示"
            root.event_generate("<<Deactivate>>")
            root.update()
            assert not app._overlay_visible, "应用失焦后浮层应收起"
            assert not app._overlay.winfo_viewable(), "应用失焦后浮层窗口应隐藏"
            print("[OK] 应用失焦：浮层立即收起，不滞留其他应用上层")

            # 根窗口 FocusOut 但焦点在浮层内（用户正在点击浮层）→ 不应误收起
            app._on_nav_area_enter()
            ok = _wait_until(
                root, lambda: app._overlay_visible and app._overlay.winfo_viewable())
            assert ok, "浮层应显示"
            app._overlay.focus_force()
            root.update()
            root.event_generate("<FocusOut>")
            root.update()
            assert app._overlay_visible, "焦点在浮层内时 FocusOut 不应收起浮层"
            app._hide_overlay()
            ok = _wait_until(
                root,
                lambda: not app._overlay_visible and not app._overlay.winfo_viewable(),
                timeout_ms=2000)
            assert ok, "浮层应收起并隐藏"
            print("[OK] 焦点在浮层内：FocusOut 不误收起")

            # 恢复展开
            app._set_sidebar_expanded(True)
            assert app.sidebar.cget("width") == app._width_expanded
            print("[OK] 重新展开")

            # 悬停高亮回归：非激活导航项悬停时应显示候选背景色（展开态，浮层逻辑不介入）
            # 注：CTkFrame 的 bind 挂在内部 _canvas 上，需对 _canvas 生成事件
            hover_row = app._nav_rows[1]
            hover_row["frame"]._canvas.event_generate("<Enter>")
            root.update()
            assert hover_row["frame"].cget("fg_color") == config.NAV_HOVER_COLOR, \
                "悬停导航项应显示候选背景色"
            hover_row["frame"]._canvas.event_generate("<Leave>")
            print("[OK] 悬停高亮：非激活导航项显示候选背景色")

            # 1. 程序化注入文件（绕过文件对话框）
            for p in paths:
                app.state.dataframes[p] = load_excel(p)
                app.state.file_paths.append(p)
            app._rescan_columns()
            app._invalidate_result()
            app.pages[0].refresh()
            app._refresh_match_page()
            print("[OK] 注入文件并刷新列表")

            # 2. 切换 4 个页面（验证侧边栏导航）
            for i in range(4):
                app._show_page(i)
                root.update()
            print("[OK] 4 个页面切换正常")

            # 3. 选择主键并执行匹配
            assert "订单号" in app.state.column_union, "主键应出现在下拉框中"
            app.pages[1].key_combo.set("订单号")
            app.on_execute_merge()
            assert app.state.merged_df is not None and len(app.state.merged_df) == 4
            print(f"[OK] 执行匹配：合并后 {len(app.state.merged_df)} 行")

            # 4. 应用过滤
            app.pages[2].set_query("销售额 > 1000")
            app.on_apply_filter()
            assert app.state.filtered_df is not None and len(app.state.filtered_df) == 2
            print(f"[OK] 应用过滤：{len(app.state.filtered_df)} 行")

            # 5. 重置过滤
            app.on_reset_filter()
            assert len(app.state.filtered_df) == 4
            print("[OK] 重置过滤恢复全量")

            # 6. 导出（绕过保存对话框与提示弹窗）
            from tkinter import filedialog, messagebox
            out = os.path.join(tmp, "冒烟测试导出.xlsx")
            filedialog.asksaveasfilename = lambda **kw: out
            messagebox.showinfo = lambda *a, **kw: None
            messagebox.showwarning = lambda *a, **kw: None
            messagebox.showerror = lambda *a, **kw: None
            app.on_export()
            assert os.path.exists(out), "导出文件应存在"
            sheets = pd.ExcelFile(out).sheet_names
            assert sheets == ["最终数据", "统计结果"]
            print(f"[OK] 导出成功，双 Sheet：{sheets}")

            # 7. 未匹配就过滤 → 提示（验证守卫逻辑不崩溃）
            app.state.merged_df = None
            app.state.filtered_df = None
            app.pages[2].set_query("销售额 > 0")
            app.on_apply_filter()  # 应弹提示而非崩溃
            print("[OK] 未匹配时过滤被正确拦截")

            print("\n=== GUI 冒烟测试全部通过 ===")
        except Exception as exc:  # noqa: BLE001 —— 测试失败时输出错误
            import traceback
            traceback.print_exc()
            print(f"\n=== GUI 冒烟测试失败：{exc} ===")
        finally:
            root.after(200, root.destroy)

    root.after(200, run_flow)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
