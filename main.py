"""数据匹配与统计工具 - 启动入口。

运行方式（在项目根目录）：
    Windows：.venv\\Scripts\\python.exe main.py
    macOS/Linux：.venv/bin/python main.py

以脚本方式运行时，Python 会自动将本文件所在目录（项目根目录）加入
模块搜索路径，因此可以直接导入 app 包，无需手动修改 sys.path。
"""
import customtkinter as ctk

from app import config
from app.gui import DataMatcherApp


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
