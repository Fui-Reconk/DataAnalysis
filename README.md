# 数据匹配与统计工具

基于 Python + CustomTkinter + Pandas 的可视化数据匹配与统计桌面应用。
加载 n 个 Excel（xls/xlsx）表格，以第一个文件为基准做左连接匹配，
支持动态条件过滤、预留统计模块，并导出双 Sheet 的 Excel 结果。

## 功能

- 📂 **文件加载**：多选加载 xls/xlsx/**DBF**（DBF 自动识别编码、中文 GBK 兼容，可与其他格式混合匹配）；支持**多工作表**——Excel 含多个 Sheet 时可自由勾选要添加的表；文件添加过任意表后即进入**暂存池**，之后可随时直接添加其其它表，无需重新选择文件；列表行**右键菜单**支持预览前几行、打开文件、设为基准表、重载、删除等
- 🔗 **匹配配置**：自动扫描全部表头并集，选择唯一标识项后执行左连接
- 🔍 **过滤筛选**：输入 pandas 查询语句（如 `销售额 > 1000 and 地区 == '华东'`）动态过滤
- 📈 **统计与导出**：预留统计模块，导出 Excel 双 Sheet（最终数据 / 统计结果）
- ⚙️ **配置文件**：所有可调参数集中在根目录 `config.cfg`（INI 格式），修改后重启生效，无需改代码

## 环境要求

- Python 3.10+
- 依赖见 [requirements.txt](requirements.txt)

## 快速开始

```bash
# 1. 创建独立虚拟环境（一次即可）
python -m venv .venv

# 2. 激活环境
#    Windows (PowerShell)
.venv\Scripts\Activate.ps1
#    Windows (CMD / Git Bash)
.venv\Scripts\activate.bat
#    macOS / Linux
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python main.py
```

> 提示：也可不激活环境，直接使用虚拟环境内的解释器运行，例如
> `.venv/Scripts/python.exe main.py`

## 使用流程

1. **文件加载** → 「添加文件」选择 Excel 文件
   - 文件只有一个 Sheet 时直接添加；含多个 Sheet 时弹出勾选框，自由选择要添加的表
   - 同一文件的其他表：点「添加工作表」从暂存池直接添加（无需再次选择文件）
   - 每个已添加的数据源显示为「文件名 [工作表名]」，第一个为匹配基准表；点行可选中，✕ 或「移除选中」可移除
2. **匹配配置** → 从下拉框选择唯一标识项（主键）→ 点击「执行匹配」
   - 若某数据源缺少所选列，会提示具体文件、工作表与列名
   - 匹配键自动转字符串并处理空值，保证跨表一致比较
3. **过滤筛选** → 输入 pandas 查询语句 → 「应用过滤」（可选步骤）
   - 语句语法错误或字段不存在时弹窗提示，程序不会崩溃
4. **统计与导出** → 点击「导出结果」
   - Sheet1：合并且过滤后的最终数据
   - Sheet2：`calculate_default_stats` 的统计结果（默认写入"未定义统计"）

## 配置文件

所有可调参数集中在根目录 [config.cfg](config.cfg)（INI 格式，含中文注释）：
外观模式/主题色、窗口尺寸、侧边栏宽度与动画、颜色对比度、字体、提示文案、
文件类型、对话框尺寸等。修改后重启应用生效；删除该文件会回退到内置默认值。

## 自定义统计逻辑

编辑 [app/stats.py](app/stats.py) 中的 `calculate_default_stats(df)`，
在预留的 `# TODO` 区域编写统计逻辑即可，例如：

```python
def calculate_default_stats(df):
    # 示例：按地区分组统计销售额
    return df.groupby("地区")["销售额"].sum().reset_index()
```

## 项目结构

```
DataAnalysis/
├── main.py                  # 启动入口
├── requirements.txt         # 依赖清单
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py            # 常量：主题/字号/窗口/文案
│   ├── state.py             # AppState：运行时共享数据
│   ├── gui.py               # 控制器：窗口 + 侧边栏 + 页面调度 + 业务编排
│   ├── pages.py             # 视图：4 个功能区页面
│   ├── data_loader.py       # 读取 Excel / 扫描表头并集
│   ├── merge_engine.py      # 左连接匹配
│   ├── filter_engine.py     # 动态过滤
│   ├── stats.py             # 默认统计模块（预留）
│   └── exporter.py          # Excel 双 Sheet 导出
└── docs/specs/              # 设计文档
```

## 常见问题

- **界面卡住**：匹配大文件时请耐心等待，界面底部进度条与状态栏会实时刷新。
- **读取 .xls 失败**：确认已安装 `xlrd`（见 requirements.txt）。
- **更换主题**：修改 [app/config.py](app/config.py) 中的 `APPEARANCE_MODE`（system/light/dark）与 `COLOR_THEME`（blue/green/dark-blue）。
