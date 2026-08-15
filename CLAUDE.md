# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

交错战线手游自动化脚本，基于 ADB + cv2 模板匹配 + PaddleOCR。**仅限 Windows**，Python 3.14（`.python-version` / `pyproject.toml`）。虚拟环境由 `uv` 管理（`.venv/`）。

## 常用命令

```powershell
# 激活虚拟环境
.\.venv\Scripts\activate

# 运行新版 Textual TUI（推荐，主入口）
python -m jczx.jczxCli

# 运行旧版 PyQt6 GUI（不再维护）
python jczx\jczx.py

# 安装依赖
uv pip install -e .

# 构建可执行文件（交互式选择 pyinstaller 或 nuitka）
python build.py

# 运行单元测试（pytest，dev 依赖）
uv run pytest                # 全部
uv run pytest tests/pure     # 方案1：纯逻辑单测（配置/占位符/缓存/变换）
uv run pytest tests/regression  # 方案3：真实 jczx/Config 只读副本回归
uv run pytest tests/engine   # 方案2：引擎级测试（FakeDevice 桩替身，不连 ADB）
```

**单元测试（pytest）**：
- `tests/pure/` 纯逻辑单测，不依赖设备与真实配置
- `tests/regression/` 基于真实配置**只读副本**的回归测试（锁住配置解析/保存行为）
- `tests/engine/` 引擎级测试：`object.__new__` 绕过 ADB 构造 `JCZXGaming`，`FakeMatcher`/`FakeToken` 桩替身，测 `_exec_entity` 模板与 exec 系列

三者独立可跑。Linter/格式化工具未配置。真实 cv2 合成图匹配与 Textual TUI 测试尚未搭建。

## 架构：两套并行实现

| | 旧版（PyQt6 GUI） | 新版（Textual TUI） |
|---|---|---|
| **入口** | `jczx/jczx.py` | `jczx/jczxCli.py` |
| **游戏逻辑** | `JCZXGame` 类 | `JCZXGaming` 类（`jczxCli.py`） |
| **配置** | `JsonConfig`（JSON） | `TxtConfig`（`/` 注释、`[section]`、`key : value`） |
| **线程** | `WorkThread(QThread)` | `ThreadPoolExecutor` |

`Ui_jczx*.py` 是 PyQt6 生成的代码，不要在 TUI 中使用。两套应用共享 `jczx/resources/` 图片资源。

### 关键类（`jczx/jczxCli.py`）

- `JCZXGaming(Device)` — 任务执行引擎核心，继承 CommonBuilder 的 `Device`。含 `exec*` 系列方法（`exec_task` / `exec_click` / `exec_match` / `exec_ocr` / `exec_condition` / `exec_context` / `exec_dynamic` / `exec_func`）。
- `PlaceholderResolver` — 占位符统一解析引擎。
- `JczxCli` — 非 UI 逻辑（设备、OCR、线程池、日志初始化）。
- `JczxTUI(App, JczxCli)` — Textual TUI 应用，接事件回调。
- `TaskExecutionManager` / `CancellationToken` / `TaskCancelledError` — 任务启停与取消。
- `ScreenshotCache` — 截图缓存（默认 TTL 200ms，click/swipe/drag 后失效）。

支持模块：`taskManage.py`（`TaskManage`：实体池/图片池/队列加载）、`configEntity.py`（`JczxSectionEntity` 等 dataclass）、`widgets.py`（TUI 组件）、`debug/`（`ScreenAnnotator` 标注、`DebugRecorder` 截图录制）、`emu/`（`EmulatorStrategy` 抽象 + `MuMuStrategy` 模拟器启停）。

## CommonBuilder 子模块（双重嵌套导入）

`jczx/CommonBuilder/` 是 git 子模块（`.gitmodules`），导入路径带**双重** `CommonBuilder`：

```python
from .CommonBuilder.CommonBuilder.Android.Adb import Adb, Device
from .CommonBuilder.CommonBuilder.FileTools.ConfigUtils import Config, TxtConfig
```

- `Android/Adb.py` — `Adb`（ADB 命令）、`Device`（截图/模板匹配/点击）、`ScreenCut`（屏幕网格分区）、`MatchTemplete`（匹配结果，支持 `transform`）
- `Ocr/Ocr.py` — PaddleOCR 封装
- `FileTools/ConfigUtils.py` — `IniConfig`/`TxtConfig`/`JsonConfig`/`Config`（工厂），`trans_entity_dict` 解析配置为实体
- `FileTools/File.py` — `FileManage`、`UrlManage`

## 配置系统

新版配置全部为 TxtConfig 格式，**冒号分隔（`key : value`，不是 `=`）**，`/` 开头为注释。

| 文件 | 用途 |
|------|------|
| `jczx/Config/Config.txt` | 全局设置（日志、线程数、ADB 路径、`debug.screenshot.mode`） |
| `jczx/Config/MainMenu.txt` | 公共实体（`in_location`、`click-center`、`goto-home` 等）+ `type: file` 子文件入口 |
| `jczx/Config/tasks/*.txt` | 各模块任务（jjc、inllusion、Favor 等），经 `type: file` 合并进同一实体池 |
| `jczx/Config/Queues.txt` | 任务队列（`[queue-xxx]` 内 `tasks:` 逗号列表，顺序执行） |

要点：
- `type: file` 引入子文件；**同名 section 冲突抛 `ValueError`**，子文件中不能再嵌套 `file`。
- `JczxSectionEntity` 中 `action`/`args`/`target` 等 str 字段按逗号自动拆为列表（`configEntity.py` 的 `__setattr__`），故**逗号后不能加空格**。
- `SectionType` 枚举含 `task`/`func`/`click`/`dynamic`/`match`/`ocr`/`context`/`condition`/`settings`/`setting`/`file`。
- 实体通过 `extend` 继承同文件其他实体；`condition` 引用实体 key 或 `&{...}` 表达式。

### 任务引擎执行模型

所有实体经 `_exec_entity(entity, on_exec)` 模板方法统一管控：

```
testFor_before 门控 → pre_sleep → on_exec(类型特有逻辑) → sleep
→ wait_target 等待 → log 输出 → action 链（get_next() 递归 exec）→ testFor_after 复检
```

- 四类占位符由 `PlaceholderResolver` 统一解析，顺序固定：`${section:option}`（配置值）→ `@{entity_key}`（执行实体取返回值）→ `%{context_key}`（上下文变量）→ `&{...}`（条件表达式）。
- `context` 类型通过 `context_set`/`context_get` 存取上下文变量；`exec_task_raw()` 前后清空上下文实现任务间隔离。
- 完整语法与字段参考见 **`TASK_CONFIG_GUIDE.md`**（权威文档，改任务配置前必读）。

## 图像与调试

- 模板匹配：灰度截图 + `cv2.matchTemplate`（`TM_CCOEFF_NORMED`），图片路径相对 `jczx/resources/`（如 `buttons\login.png`）。
- `debug.screenshot.mode`（Config.txt）：`off` / `simple`（连续截图）/ `annotated`（标注匹配/点击/OCR 位置），输出至 `screenHistory/`。
- 从仓库根目录运行需软链接：`mklink /J resources jczx\resources`。

## 编码规范（必读 AGENTS.md）

详细编码四原则在 **`AGENTS.md`**：编码前思考、简洁优先、精准修改（只碰必须碰的）、目标驱动执行。

**Git 提交规则**（`AGENTS.md` 明确要求）：
- 代码必须**经用户验证功能实现后再提交**，否则禁止提交；未验证的提交必须回退。
- 提交格式：`[emoji: commit_msg]`，提交信息用中文。

## 其他注意

- 日志文件写在工作区根目录：`JczxCli.log`、`JczxTUI.log`。
- 代码混合中英文（中文注释、英文代码）；`translate.py` 为 TUI 字符串提供中英切换。
- `JCZXAutoScriptConfig.json`、`platform-tools/`、`screenHistory/`、`template/`、`.superpowers/` 在 `.gitignore` 中，不要提交。
- 设计文档在 `docs/superpowers/`（specs + plans），涉及架构改动时参考。
