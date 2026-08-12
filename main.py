"""数据匹配与统计工具 - 启动入口。

运行方式（在项目根目录）：
    Windows：.venv\\Scripts\\python.exe main.py
    macOS/Linux：.venv/bin/python main.py
"""
import os
import sys

# 确保将项目根目录加入模块搜索路径，兼容双击或不同工作目录启动
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk  # noqa: E402 —— 需在路径修正之后导入

from app import config  # noqa: E402
from app.gui import DataMatcherApp  # noqa: E402


def main() -> None:
    """设置外观主题并启动主界面。"""
    # 外观模式：跟随系统；主题色：蓝色
    ctk.set_appearance_mode(config.APPEARANCE_MODE)
    ctk.set_default_color_theme(config.COLOR_THEME)

    root = ctk.CTk()
    DataMatcherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
