"""系统集成工具：用操作系统默认程序打开文件。

「打开」功能：通过系统文件关联唤起 Office / WPS / 其他默认程序。

平台适配：
  - Windows：os.startfile（按 .xlsx/.xls 关联启动，适配 Office、WPS 等）
  - Linux（含银河麒麟/UOS 等 Debian 系）：xdg-open（系统标准打开命令）
  - macOS：open 命令
"""
from __future__ import annotations

import os
import subprocess
import sys


def open_with_system(path: str) -> None:
    """用系统默认程序打开指定文件；失败时抛出异常，由调用方提示。"""
    if sys.platform.startswith("win"):
        # Windows：按文件关联启动（Office / WPS 等）
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        # Linux（含银河麒麟等）：xdg-open 为桌面环境标准打开命令
        subprocess.Popen(["xdg-open", path])


def show_in_folder(path: str) -> None:
    """在系统文件管理器中定位该文件（Windows 资源管理器 / Linux 文件管理器）。"""
    if sys.platform.startswith("win"):
        # Windows：explorer /select 定位并选中文件
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        # Linux（含银河麒麟等）：打开文件所在目录，由文件管理器展示
        subprocess.Popen(["xdg-open", os.path.dirname(os.path.abspath(path))])
