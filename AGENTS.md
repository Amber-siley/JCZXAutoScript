# AGENTS.md

## 项目概述

交错战线手游自动化脚本，基于 ADB + cv2 模板匹配 + PaddleOCR。仅限 Windows，Python 3.11+。

## 架构：两套并行实现

| | 旧版（PyQt6 GUI） | 新版（Textual TUI） |
|---|---|---|
| **入口** | `jczx/jczx.py` | `jczx/jczxCli.py` |
| **运行** | `python jczx/jczx.py` | `python -m jczx.jczxCli` |
| **游戏逻辑** | `JCZXGame` 类（`jczx.py`） | `JCZXGaming` 基类（`jczxCli.py`） |
| **配置** | `JsonConfig`（JSON） | `TxtConfig`（`/` 注释，`[section]`，`key : value`） |
| **线程** | `WorkThread(QThread)` | `ThreadPoolExecutor` |

TUI 迁移进行中。两套应用共享 `jczx/resources/` 图片资源，但使用不兼容的配置系统。`Ui_jczx*.py` 是 PyQt6 生成的代码 —— 不要在 TUI 中使用。

## 常用命令

```powershell
# 激活虚拟环境
.\venv\Scripts\activate

# 运行旧版 PyQt6 GUI
python .\jczx\jczx.py

# 运行新版 Textual TUI
python -m jczx.jczxCli

# 构建可执行文件（交互式选择 pyinstaller 或 nuitka）
python build.py
```

虚拟环境：`uv` 管理，`pyproject.toml` 声明依赖。激活：`.\.venv\Scripts\activate`。

## 无测试套件、Linter 或格式化工具

项目中没有这些。`test/` 仅包含临时脚本。不要运行 `pytest`、`ruff` 或 `mypy` —— 均未配置。

## 配置系统注意事项

- **旧版：** 仓库根目录 `JCZXAutoScriptConfig.json` —— JSON 格式。
- **新版：** `jczx/Config/Config.txt`（全局设置）+ `jczx/Config/MainMenu.txt`（任务定义）。
- TxtConfig 语法：`/` 开头为注释，`[section]` 为节头，`key : value` 键值对（冒号分隔，**不是** `=`）。
- `JczxSectionEntity` 中的 `target`、`action`、`args` 等字符串字段自动按逗号拆分为列表。
- `SectionType` 枚举值：`task`、`func`、`click`、`option`、`settings`、`setting`。

## 共享库：CommoneBuilder

位于 `jczx/CommoneBuilder/CommonBuilder/`，导入路径注意双重 `CommonBuilder`：
```python
from .CommoneBuilder.CommonBuilder.Android.Adb import Adb, Device
from .CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import Config, TxtConfig
```

提供：
- `Android/Adb.py` — `Adb`（ADB 命令执行）、`Device`（继承 Adb，提供截图、模板匹配、点击）、`ScreenCut`、`MatchTempleteDetailInfo`
- `Ocr/Ocr.py` — PaddleOCR 的 `OCR` 封装
- `FileTools/ConfigUtils.py` — `IniConfig`、`TxtConfig`、`JsonConfig`、`Config`（工厂类）
- `FileTools/File.py` — `FileManage`、`UrlManage`

## 图像自动化

- 模板匹配：灰度截图 + `cv2.matchTemplate`（`TM_CCOEFF_NORMED`）
- 按钮图片：`jczx/resources/buttons/`（PNG）
- 位置检测：`jczx/resources/locations/`
- 数字图片：`jczx/resources/numbers/`（免 OCR 数字识别）
- 屏幕分区：`ScreenCut` 类将屏幕划分为网格，用于区域匹配

## TUI 专用说明

- Textual TUI 的 CSS：`jczx/Css/main.tcss`
- 自定义组件：`jczx/widgets.py`（ToggleButton、Collapsible、DeviceBar、TaskCard 等）
- 日志文件写入工作区根目录：`JczxCli.log`、`JczxTUI.log`
- 长时间任务当前在主 Textual 事件循环中执行（阻塞 UI），需要移至工作线程
- 任务引擎（`exec` / `exec_plan` / `exec_task` / `exec_click`）链式调用 `JczxSectionEntity` 对象，任务通过 `action` 字段引用其他 section
- 详细任务配置文档：`TASK_CONFIG_GUIDE.md`

## 奇技淫巧

- `jczx/jczx.py:44` 行 `LOG_LEVEL` 硬编码为 `logging.DEBUG`。
- `jczx/jczx.py:35-38` 行 `joinPath()` 检查 `sys._MEIPASS` 以兼容 PyInstaller 打包。
- 从仓库根目录运行时（非 `jczx/`），需创建符号链接：`mklink /J resources jczx\resources`。
- `JCZXAutoScriptConfig.json` 和 `sde/`、`.venv/` 在 `.gitignore` 中 —— 不要提交。
- 代码混合中英文（中文注释，英文代码）。`translate.py` 为 TUI 字符串提供简单的中英文切换。

## 编码四原则

### 1. 编码前思考

**不要假设。不要隐藏困惑。呈现权衡。**

LLM 经常默默选择一种解释然后执行。这个原则强制明确推理：

- **明确说明假设** — 如果不确定，询问而不是猜测
- **呈现多种解释** — 当存在歧义时，不要默默选择
- **适时提出异议** — 如果存在更简单的方法，说出来
- **困惑时停下来** — 指出不清楚的地方并要求澄清

### 2. 简洁优先

**用最少的代码解决问题。不要过度推测。**

对抗过度工程的倾向：

- 不要添加要求之外的功能
- 不要为一次性代码创建抽象
- 不要添加未要求的"灵活性"或"可配置性"
- 不要为不可能发生的场景做错误处理
- 如果 200 行代码可以写成 50 行，重写它
- git提交代码必须要用户验证功能后再提交，否则停止提交
- git commit提交格式[emoji: commit_msg], 提交信息使用中文编写

**检验标准：** 资深工程师会觉得这过于复杂吗？如果是，简化。

### 3. 精准修改

**只碰必须碰的。只清理自己造成的混乱。**

编辑现有代码时：

- 不要"改进"相邻的代码、注释或格式
- 不要重构没坏的东西
- 匹配现有风格，即使你更倾向于不同的写法
- 如果注意到无关的死代码，提一下 —— 不要删除它

当你的改动产生孤儿代码时：

- 删除因你的改动而变得无用的导入/变量/函数
- 不要删除预先存在的死代码，除非被要求

**检验标准：** 每一行修改都应该能直接追溯到用户的请求。

### 4. 目标驱动执行

**定义成功标准。循环验证直到达成。**

将指令式任务转化为可验证的目标：

| 不要这样做... | 转化为... |
|--------------|-----------------|
| "添加验证" | "为无效输入编写测试，然后让它们通过" |
| "修复 bug" | "编写重现 bug 的测试，然后让它通过" |
| "重构 X" | "确保重构前后测试都能通过" |

对于多步骤任务，说明一个简短的计划：

```
1. [步骤] → 验证: [检查]
2. [步骤] → 验证: [检查]
3. [步骤] → 验证: [检查]
```

强有力的成功标准让 LLM 能够独立循环执行。弱标准（"让它工作"）需要不断澄清。
