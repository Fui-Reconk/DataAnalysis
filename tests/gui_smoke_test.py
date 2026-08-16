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

import customtkinter as ctk
import pandas as pd

# 强制 UTF-8 输出，避免 Windows GBK 控制台编码错误
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except (AttributeError, ValueError):
    pass

# 将项目根目录加入搜索路径（测试以脚本方式运行时需手动添加）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    # app 包依赖上面的项目根目录路径引导，故延迟到函数内导入
    from app.gui import DataMatcherApp

    tmp = tempfile.mkdtemp(prefix="gui_smoke_")
    paths = _make_sample_files(tmp)

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    app = DataMatcherApp(root)

    def run_flow() -> None:
        from app import config
        from app.data_loader import list_sheets, load_excel

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

            # 1. 程序化注入文件（绕过文件对话框）；数据源 = (文件路径, 工作表名)
            for p in paths:
                sheet = list_sheets(p)[0]
                app.state.sources.append((p, sheet))
                app.state.dataframes[(p, sheet)] = load_excel(p, sheet)
                app.state.staged_files[p] = list_sheets(p)
            app._invalidate_result()
            app.pages[0].refresh()
            app._refresh_match_page()
            print("[OK] 注入文件并刷新列表")

            # 1b. 文件行选中对比：选中后整行主题色背景 + 白色文字，取消选中恢复高对比默认色
            first_src = app.state.sources[0]
            app.pages[0]._toggle_select(*first_src)
            root.update()
            row_widgets = app.pages[0]._row_widgets[first_src]
            active_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
            assert row_widgets["frame"].cget("fg_color") == active_color, \
                "选中行背景应为主题色"
            assert row_widgets["btn"].cget("text_color") == config.NAV_ACTIVE_TEXT_COLOR, \
                "选中行名称文字应为白色"
            assert row_widgets["path_label"].cget("text_color") == config.NAV_ACTIVE_TEXT_COLOR, \
                "选中行路径文字应为白色"
            app.pages[0]._toggle_select(*first_src)
            root.update()
            assert row_widgets["frame"].cget("fg_color") == "transparent", \
                "取消选中后行背景应恢复透明"
            assert row_widgets["btn"].cget("text_color") == config.FILE_ROW_TEXT_COLOR, \
                "取消选中后名称文字应恢复高对比默认色"
            print("[OK] 文件行选中：主题色背景 + 白色文字，取消后恢复默认高对比")

            # 1c. 设为基准表：单选生效（左键勾选），多选无效
            second_src = app.state.sources[1]
            file_page = app.pages[0]
            file_page._select_none()
            file_page._toggle_select(*second_src)
            app.on_set_base()
            root.update()
            assert app.state.sources[0] == second_src, "单选设为基准表应移到首位"
            # 匹配页主键下拉框应只列基准表的列（设为基准表后随之切换）
            second_cols = [str(c) for c in app.state.dataframes[second_src].columns]
            assert app.pages[1].key_combo.cget("values") == second_cols, \
                "主键下拉框应只列基准表的列（跟随基准表切换）"
            file_page._select_all()
            app.on_set_base()
            root.update()
            assert app.state.sources[0] == second_src, "多选时不应设置基准表"
            file_page._select_none()
            file_page._toggle_select(*first_src)
            app.on_set_base()
            root.update()
            assert app.state.sources[0] == first_src, "基准表应恢复为第一个数据源"
            first_cols = [str(c) for c in app.state.dataframes[first_src].columns]
            assert app.pages[1].key_combo.cget("values") == first_cols, \
                "基准表恢复后下拉框应只列其列"
            print("[OK] 设为基准表：单选生效、多选无效；主键下拉框只列基准表列")

            # 1d. 行右键菜单绑定：整行（框/名称/路径小字）均注册 Button-3
            # 注：CTk 组件 bind 为追加语义，查询需走底层 _canvas
            row_widgets = app.pages[0]._row_widgets[first_src]
            assert row_widgets["frame"]._canvas.bind("<Button-3>"), "行框应绑定右键菜单"
            assert row_widgets["btn"]._canvas.bind("<Button-3>"), "名称按钮应绑定右键菜单"
            assert row_widgets["path_label"]._canvas.bind("<Button-3>"), "路径小字应绑定右键菜单"
            print("[OK] 行右键菜单：框/名称/路径均已绑定")

            # 1e. 右键菜单功能：全选 / 取消全选 / 右键自动选中 / 批量操作 / 二次确认
            file_page = app.pages[0]
            file_page._select_all()
            root.update()
            assert len(file_page.selected_sources) == len(app.state.sources), "全选应选中全部行"
            assert all(w["frame"].cget("fg_color") ==
                       ctk.ThemeManager.theme["CTkButton"]["fg_color"]
                       for w in file_page._row_widgets.values()), "全选后各行应为主题色"
            file_page._select_none()
            root.update()
            assert not file_page.selected_sources, "取消全选后应无选中"
            assert all(w["frame"].cget("fg_color") == "transparent"
                       for w in file_page._row_widgets.values()), "取消全选后各行应恢复透明"
            print("[OK] 右键菜单：全选 / 取消全选 状态正确")

            # 右键目标策略：未选中行右键 → 独立操作；已选中行右键 → 批量
            file_page._select_none()
            assert file_page._menu_targets(*first_src) == [first_src], \
                "未选中行右键应为独立操作（仅该行）"
            file_page._toggle_select(*first_src)
            file_page._toggle_select(*second_src)
            targets = file_page._menu_targets(*first_src)
            assert set(targets) == {first_src, second_src}, "已选中行右键应为批量操作"
            # 全选开关：全部已选时再点 → 取消全选
            file_page._toggle_select_all()
            root.update()
            assert not file_page.selected_sources, "全选开关再点应取消全选"
            file_page._toggle_select_all()
            root.update()
            assert len(file_page.selected_sources) == len(app.state.sources), \
                "全选开关未全选时应全选"
            file_page._select_none()
            print("[OK] 右键目标：未选中独立 / 已选中批量；全选为开关式")

            # 无选中右键：菜单打开期间临时选中，关闭后自动取消
            file_page._select_none()
            assert file_page._begin_menu_selection(*first_src) is True, \
                "无选中时右键应临时选中该行"
            assert file_page.selected_sources == [first_src]
            file_page._end_menu_selection(*first_src, True)
            assert not file_page.selected_sources, "菜单关闭后应自动取消临时选中"
            # 已有选中时右键不临时选中、不改变选区
            file_page._toggle_select(*first_src)
            assert file_page._begin_menu_selection(*second_src) is False, \
                "有选中时不应临时选中"
            assert file_page.selected_sources == [first_src]
            file_page._end_menu_selection(*second_src, False)
            file_page._select_none()
            print("[OK] 无选中临时选中/自动取消")

            # 原生右键菜单：结构（计数/设基准禁用/勾选变量存活）
            menu = file_page._build_row_menu(*first_src)
            labels = []
            for i in range(menu.index("end") + 1):
                if menu.type(i) != "separator":
                    labels.append(menu.entrycget(i, "label"))
            assert "打开" in labels and "打开（2）" not in labels, "单选不应显示计数"
            assert "移除" in labels, "应保留移除项"
            # 勾选变量保持存活（防 GC 导致勾勾消失）
            for i in range(menu.index("end") + 1):
                if menu.type(i) == "checkbutton":
                    var_name = menu.entrycget(i, "variable")
                    assert var_name and var_name in root.tk.call("info", "globals"), \
                        f"勾选变量 {var_name} 应存活"
            # 设为基准表：单选可用
            set_base_idx = None
            for i in range(menu.index("end") + 1):
                if menu.type(i) != "separator" and menu.entrycget(i, "label") == "设为基准表":
                    set_base_idx = i
                    break
            assert set_base_idx is not None
            assert menu.entrycget(set_base_idx, "state") != "disabled", \
                "单选时设基准应可用"
            # 多选：计数显示 + 设基准禁用
            file_page._toggle_select(*first_src)
            file_page._toggle_select(*second_src)
            menu2 = file_page._build_row_menu(*first_src)
            labels2 = []
            for i in range(menu2.index("end") + 1):
                if menu2.type(i) != "separator":
                    labels2.append(menu2.entrycget(i, "label"))
            assert "打开（2）" in labels2, "多选应显示计数"
            set_base_idx2 = None
            for i in range(menu2.index("end") + 1):
                if menu2.type(i) != "separator" and menu2.entrycget(i, "label") == "设为基准表":
                    set_base_idx2 = i
                    break
            assert set_base_idx2 is not None
            assert menu2.entrycget(set_base_idx2, "state") == "disabled", \
                "多选时设基准应禁用"
            file_page._select_none()
            print("[OK] 原生右键菜单：计数/设基准禁用/勾选变量存活")

            # 批量操作：打开（按文件去重）/ 定位（每文件一次）/ 重载（结果失效）
            from app import system_utils
            file_page._select_none()
            file_page._toggle_select(*first_src)
            file_page._toggle_select(*second_src)
            open_calls = []
            system_utils.os.startfile = lambda p: open_calls.append(p)  # type: ignore
            app.on_open_sources()
            assert set(open_calls) == {first_src[0], second_src[0]}, "批量打开应按文件去重"
            open_calls.clear()
            spawn_calls = []
            system_utils.subprocess.Popen = lambda *a, **kw: spawn_calls.append(a)  # type: ignore[misc]
            app.on_show_sources_in_folder()
            assert len(spawn_calls) == 2, "批量定位应按文件逐个调用"
            app.on_reload_sources()
            root.update()
            assert first_src in app.state.dataframes and second_src in app.state.dataframes, \
                "批量重载后数据应保留"
            assert app.state.merged_df is None, "批量重载后旧结果应失效"
            print("[OK] 批量操作：打开去重 / 定位 / 重载")

            # 二次确认：超过阈值时 askyesno=False 中止、True 执行（重载刷新清空选中，需重选）
            from tkinter import messagebox
            file_page._select_none()
            file_page._toggle_select(*first_src)
            file_page._toggle_select(*second_src)
            config.MENU_CONFIRM_THRESHOLD = 1
            messagebox.askyesno = lambda *a, **k: False
            app.on_open_sources()
            assert not open_calls, "确认被拒绝时应中止批量打开"
            messagebox.askyesno = lambda *a, **k: True
            app.on_open_sources()
            assert set(open_calls) == {first_src[0], second_src[0]}, "确认通过后应执行"
            # 在文件夹中显示：按文件数独立计数确认（2 个文件 > 阈值 1）
            config.MENU_FOLDER_CONFIRM_THRESHOLD = 1
            spawn_calls.clear()
            messagebox.askyesno = lambda *a, **k: False
            app.on_show_sources_in_folder()
            assert not spawn_calls, "文件夹定位按文件数超阈值且拒绝时应中止"
            config.MENU_CONFIRM_THRESHOLD = 5
            config.MENU_FOLDER_CONFIRM_THRESHOLD = 5
            file_page._select_none()
            print("[OK] 批量二次确认：选中数/文件数阈值分别控制执行")

            # 1f. 预览：表格展示前几行数据（不含索引列，列与行内容正确）
            preview = app.on_preview_source(*first_src)
            root.update()
            assert preview is not None, "预览弹窗应创建"
            assert preview.columns == ["订单号", "地区", "销售额"], preview.columns
            assert len(preview.rows) == 4, "样例表 4 行应全部展示（少于 PREVIEW_ROWS）"
            assert preview.rows[0] == ["A01", "华东", "1200"], preview.rows[0]
            # 空白修复不变量：表格区高度与内容请求高度一致（±2px 内，无空白带）
            ok = _wait_until(
                root,
                lambda: abs(preview._table_frame.winfo_height() -
                            preview._table_frame.winfo_reqheight()) <= 2,
                timeout_ms=1000)
            assert ok, "表格区不应有多余空白"
            # 预览非模态：不劫持鼠标/键盘，主窗口与其它窗口可操作
            assert preview.grab_current() is None, "预览不应 grab（模态）"
            # 多个预览可并存：再开一个，两个都可见、无 grab 互抢
            preview2 = app.on_preview_source(*app.state.sources[1])
            root.update()
            assert preview.winfo_viewable() and preview2.winfo_viewable(), "两个预览应同时可见"
            assert preview2.grab_current() is None, "第二个预览也不应 grab"
            preview2.close()
            root.update()
            assert not preview2.winfo_exists(), "第二个预览应可独立关闭（已销毁）"
            preview.close()
            root.update()
            assert not preview.winfo_exists(), "第一个预览应可独立关闭（已销毁）"
            print("[OK] 预览：内容正确、无空白带、非模态可多开并存")

            # 2. 切换 4 个页面（验证侧边栏导航）
            for i in range(4):
                app._show_page(i)
                root.update()
            print("[OK] 4 个页面切换正常")

            # 3. 选择主键并执行匹配（匹配完成后按配置自动弹出结果预览）
            base_cols = [str(c) for c in app.state.dataframes[app.state.sources[0]].columns]
            assert "订单号" in base_cols, "基准表列应出现在主键下拉框中"
            assert set(app.pages[1].key_combo.cget("values")) == set(base_cols), \
                "主键下拉框应只含基准表的列（不含其它表独有列）"
            app.pages[1].key_combo.set("订单号")
            merge_previews = []
            orig_open_preview = app._open_preview
            app._open_preview = lambda *a, **k: merge_previews.append(a)  # type: ignore[assignment]
            try:
                app.on_execute_merge()
                assert app.state.merged_df is not None and len(app.state.merged_df) == 4
                assert merge_previews and merge_previews[0][0] == "预览：匹配结果", \
                    "匹配完成后应自动弹出结果预览"
                assert len(merge_previews[0][1]) == 4, "预览内容应为合并结果"
                # 开关关闭时不自动预览
                merge_previews.clear()
                config.PREVIEW_AUTO_AFTER_MERGE = False
                app.state.merged_df = None
                app.state.filtered_df = None
                app.on_execute_merge()
                assert app.state.merged_df is not None and len(app.state.merged_df) == 4
                assert merge_previews == [], "auto_show_after_merge=false 时不自动预览"
            finally:
                app._open_preview = orig_open_preview
                config.PREVIEW_AUTO_AFTER_MERGE = True
            print(f"[OK] 执行匹配：合并后 {len(app.state.merged_df)} 行；完成后自动预览开关可配")

            # 3b. 匹配后自动清理冗余列：全空列 / 与基准表同名的重复列（仅删非基准表列）
            p6 = os.path.join(tmp, "冗余列.xlsx")
            pd.DataFrame({"订单号": ["A01", "A02", "A03", "A04"],
                          "地区": ["华东", "华东", "华北", "华南"],
                          "空备注": [None] * 4}).to_excel(p6, index=False)
            s6 = list_sheets(p6)[0]
            src6 = (p6, s6)
            app.state.sources.append(src6)
            app.state.dataframes[src6] = load_excel(p6, s6)
            app.state.staged_files[p6] = [s6]
            app._invalidate_result()
            app.pages[0].refresh()
            app._refresh_match_page()
            app.pages[1].key_combo.set("订单号")
            orig_merge_clean = config.MERGE_AUTO_CLEAN
            app._open_preview = lambda *a, **k: merge_previews.append(a)  # type: ignore[assignment]
            try:
                config.MERGE_AUTO_CLEAN = True
                app.on_execute_merge()
                merged_cols = set(app.state.merged_df.columns)
                assert "地区_3" not in merged_cols and "空备注" not in merged_cols, \
                    "全空列与基准同名的重复列应被自动删除"
                assert {"地区", "销售额", "数量", "订单号"} <= merged_cols, \
                    "基准列与正常非基准列应保留"
                # 开关关闭时不清理
                config.MERGE_AUTO_CLEAN = False
                app.on_execute_merge()
                assert "地区_3" in app.state.merged_df.columns, \
                    "auto_clean=false 时应保留冗余列"
            finally:
                app._open_preview = orig_open_preview
                config.MERGE_AUTO_CLEAN = orig_merge_clean
            print("[OK] 匹配后自动清理：全空/同名重复列被删，开关可配")

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

            # 7b. 导入自动预览：开关与数量可配置
            p3 = os.path.join(tmp, "自动预览.xlsx")
            pd.DataFrame({"订单号": ["X1", "X2"], "值": [1, 2]}).to_excel(p3, index=False)
            s3 = list_sheets(p3)[0]
            p4 = os.path.join(tmp, "自动预览2.xlsx")
            pd.DataFrame({"订单号": ["Y1"], "值": [1]}).to_excel(p4, index=False)
            s4 = list_sheets(p4)[0]
            preview_calls = []
            orig_preview = app.on_preview_source
            app.on_preview_source = lambda *a, **k: preview_calls.append(a)  # type: ignore[assignment]
            try:
                # 默认 auto_show=true、count=1：只弹首个新数据源
                app._add_sources([(p3, s3)])
                assert preview_calls == [(p3, s3)], "默认应自动预览首个新数据源"
                app.on_remove_source(p3, s3)
                preview_calls.clear()
                # auto_show=false：不自动预览
                config.PREVIEW_AUTO_SHOW = False
                app._add_sources([(p3, s3)])
                assert preview_calls == [], "auto_show=false 时不应自动预览"
                app.on_remove_source(p3, s3)
                preview_calls.clear()
                # count=2 + 两个新数据源：弹 2 个（首个模态，其余级联）
                config.PREVIEW_AUTO_SHOW = True
                config.PREVIEW_AUTO_SHOW_COUNT = 2
                app._add_sources([(p3, s3), (p4, s4)])
                assert preview_calls == [(p3, s3), (p4, s4)], "数量可配：应弹 2 个"
                app.on_remove_source(p3, s3)
                app.on_remove_source(p4, s4)
            finally:
                app.on_preview_source = orig_preview
            root.update()
            print("[OK] 导入自动预览：开关与数量可配置")

            # 7c. 导入即自动替换列名缩写 + 手动「替换缩写」后自动预览（开关可配）
            p5 = os.path.join(tmp, "缩写.xlsx")
            pd.DataFrame({"nd": [2025], "xm": ["张三"], "other": [1]}).to_excel(p5, index=False)
            s5 = list_sheets(p5)[0]
            src5 = (p5, s5)
            orig_replace_preview = config.PREVIEW_AUTO_AFTER_REPLACE
            preview_calls.clear()
            app.on_preview_source = lambda *a, **k: preview_calls.append(a)  # type: ignore[assignment]
            try:
                # 导入即自动替换：列名直接变为全称，且自动预览新列名
                app._add_sources([src5])
                assert list(app.state.dataframes[src5].columns) == ["年度", "姓名", "other"], \
                    "导入时应自动替换列名缩写"
                assert preview_calls and preview_calls[0][0:2] == src5, "导入后应自动预览（新列名）"
                app.on_remove_source(*src5)
                preview_calls.clear()
                # 手动路径（模拟映射变更/历史数据）：替换后自动弹预览
                app.state.sources.append(src5)
                app.state.dataframes[src5] = pd.DataFrame({"nd": [2025], "xm": ["张三"],
                                                           "other": [1]})
                app.state.staged_files[p5] = [s5]
                app._invalidate_result()
                app.pages[0].refresh()
                app.on_replace_abbr([src5])
                assert preview_calls == [src5], "替换缩写后应自动弹出预览"
                assert list(app.state.dataframes[src5].columns) == ["年度", "姓名", "other"], \
                    "手动替换后列名应为中文全称"
                # 开关关闭时不自动预览
                app.state.dataframes[src5] = pd.DataFrame({"nd": [2025], "xm": ["张三"],
                                                           "other": [1]})
                preview_calls.clear()
                config.PREVIEW_AUTO_AFTER_REPLACE = False
                app.on_replace_abbr([src5])
                assert preview_calls == [], "auto_show_after_replace=false 时不自动预览"
                app.on_remove_source(*src5)
            finally:
                config.PREVIEW_AUTO_AFTER_REPLACE = orig_replace_preview
                app.on_preview_source = orig_preview
            root.update()
            print("[OK] 导入自动替换缩写 + 手动替换自动预览：均生效、开关可配")

            # 8. 工作表多选对话框：按文件分组层级 + 勾选语义 + 全选/全不选
            from app.sheet_dialog import SheetPickerDialog
            picked = []
            dlg = SheetPickerDialog(root, "测试对话框",
                                    [("文件A", ("f1", "s1"), "Sheet1"),
                                     ("文件A", ("f1", "s2"), "Sheet2"),
                                     ("文件B", ("f2", "s3"), "Sheet3")],
                                    on_confirm=lambda keys: picked.append(keys))
            root.update()
            # 分组层级：两个分组头，且组内选项可勾选
            assert set(dlg._group_headers) == {"文件A", "文件B"}, "应按文件分组显示层级"
            # 默认全选：变量与视觉勾选状态一致
            for key in (("f1", "s1"), ("f1", "s2"), ("f2", "s3")):
                assert dlg._vars[key].get() == "on" and dlg._checkboxes[key].get() == "on", \
                    "默认应全部勾选（视觉与变量一致）"
            # 模拟真实点击：勾选中的选项点一下 → 取消勾选
            dlg._checkboxes[("f1", "s1")].toggle()
            root.update()
            assert dlg._vars[("f1", "s1")].get() == "", "点击勾选中的项应取消勾选"
            # 全不选 / 全选：变量与视觉同步
            dlg._select_none()
            root.update()
            assert all(v.get() == "" for v in dlg._vars.values()), "全不选应全部取消"
            assert all(cb.get() == "" for cb in dlg._checkboxes.values()), "全不选后视觉应未勾选"
            dlg._select_all()
            root.update()
            assert all(v.get() == "on" for v in dlg._vars.values()), "全选应全部勾选"
            assert all(cb.get() == "on" for cb in dlg._checkboxes.values()), "全选后视觉应勾选"
            # 只勾选一个后确定 → 回调恰好为该选项（不反向）
            dlg._select_none()
            dlg._vars[("f2", "s3")].set("on")
            dlg._on_ok()
            root.update()
            assert picked and picked[0] == [("f2", "s3")], "确定应只回调勾选项，不得反向"
            print("[OK] 工作表多选对话框：按文件分组 + 勾选/全选/全不选语义正确")

            print("\n=== GUI 冒烟测试全部通过 ===")
        except Exception as exc:  # 测试失败时输出错误（BLE001 见 .flake8）
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
