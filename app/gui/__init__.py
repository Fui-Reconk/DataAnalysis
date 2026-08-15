"""GUI 控制器包：DataMatcherApp 主控制器及其按职责拆分的模块。

DataMatcherApp 由多个 Mixin 组合而成，各职责独立成模块：
  - sidebar.py   侧边栏（构建、导航项、悬停高亮、展开/折叠）
  - overlay.py   半透明浮层（折叠态悬停展开）
  - content.py   内容区、页面调度与状态栏/进度条
  - files.py     文件加载/移除
  - actions.py   匹配/过滤/导出业务操作

组合入口见 controller.py；对外仍以 ``from app.gui import DataMatcherApp`` 使用。
"""
from app.gui.controller import DataMatcherApp

__all__ = ["DataMatcherApp"]
