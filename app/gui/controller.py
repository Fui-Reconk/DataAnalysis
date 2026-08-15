"""DataMatcherApp：应用主控制器（组合入口）。

负责创建主窗口并编排各功能模块，统一更新状态栏与进度条，
保证耗时操作时界面不卡死。各职责按 Mixin 拆分到独立模块，
本文件仅保留类的组合与初始化逻辑：

  - SidebarMixin      侧边栏构建、导航项、悬停高亮、展开/折叠
  - OverlayMixin      半透明浮层（折叠态悬停展开）
  - ContentMixin      内容区构建、页面调度、状态栏/进度条
  - FileOpsMixin      文件加载/移除
  - OperationsMixin   匹配/过滤/导出业务操作
"""
from __future__ import annotations

import customtkinter as ctk

from app import config
from app.gui.actions import OperationsMixin
from app.gui.content import ContentMixin
from app.gui.files import FileOpsMixin
from app.gui.overlay import OverlayMixin
from app.gui.sidebar import SidebarMixin
from app.state import AppState


class DataMatcherApp(SidebarMixin, OverlayMixin, ContentMixin,
                     FileOpsMixin, OperationsMixin):
    """数据匹配与统计工具主控制器。"""

    def __init__(self, root: ctk.CTk):
        self.root = root
        self.state = AppState()

        # 窗口基础设置
        self.root.title(config.APP_TITLE)
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.minsize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # 构建界面
        self._build_sidebar()
        self._build_content()

        # 默认显示第一个功能区
        self._show_page(0)
