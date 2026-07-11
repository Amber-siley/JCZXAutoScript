# 模拟器启动系统设计

## 概述

策略模式实现模拟器启动，先支持 MuMu 模拟器。通过 MainMenu.txt 的 settings/setting 配置 MuMuManager.exe 路径，func 驱动 `launch_emulator` / `shutdown_emulator`，自动检测策略。

## 架构

```
jczx/emu/
├── __init__.py
├── base.py            ← EmulatorStrategy (ABC): launch(shutdown, win_startupinfo)
└── mumu.py            ← MuMuStrategy: MuMuManager.exe control -v <index> launch/shutdown
```

## 配置

### MainMenu.txt

```ini
[emu]
type: task
view: off
name: 模拟器设置
settings: emu-settings

[emu-settings]
type: settings
fields: emu-manager-path

[emu-manager-path]
type: setting
setting_type: input
label: MuMuManager.exe路径
desc: 如 C:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe
default:
```

用户通过 TUI 设置面板配置路径，保存至 `[emu-values]`。

## 策略初始化

`JCZXGaming.__init__` 中：

```python
self._emu_strategy = None
```

`JCZXGaming` 新增 `_init_emu_strategy` 方法，由 `JczxCli._init_device` 调用（放在 `set_ocr` 之后）：

```python
def _init_emu_strategy(self):
    if self._emu_strategy:
        return
    values = self.task_manage.get_task_values("emu")
    path = values.get("emu-manager-path", "")
    if path and os.path.isfile(path):
        from .emu import MuMuStrategy
        self._emu_strategy = MuMuStrategy(path, self.startupinfo)
        self.log.debug(f"MuMu 模拟器策略已激活: {path}")
```

## Func 接口

```python
def launch_emulator(self, index: str = "0"):
    if self._emu_strategy:
        self._emu_strategy.launch(str(index))

def shutdown_emulator(self, index: str = "0"):
    if self._emu_strategy:
        self._emu_strategy.shutdown(str(index))
```

## EmulatorStrategy (ABC)

```python
class EmulatorStrategy(ABC):
    @abstractmethod
    def launch(self, index: str) -> bool: ...
    @abstractmethod
    def shutdown(self, index: str) -> bool: ...
```

## MuMuStrategy

```python
class MuMuStrategy(EmulatorStrategy):
    def __init__(self, path: str, startupinfo):
        self._path = path

    def _run(self, *args):
        cmd = [self._path] + list(args)
        subprocess.run(cmd, startupinfo=self._startupinfo, check=True)

    def launch(self, index: str):
        self._run("control", "-v", index, "launch")

    def shutdown(self, index: str):
        self._run("control", "-v", index, "shutdown")
```

## 文件变更

| 文件 | 变更 |
|------|------|
| `jczx/emu/__init__.py` | **新建** |
| `jczx/emu/base.py` | **新建**，EmulatorStrategy ABC |
| `jczx/emu/mumu.py` | **新建**，MuMuStrategy |
| `jczx/Config/MainMenu.txt` | 新增 emu 设置段 |
| `jczx/jczxCli.py` | `_init_emu_strategy`、`launch_emulator`、`shutdown_emulator` |

## 使用示例

```ini
[launch-emu]
type: func
func: launch_emulator
args: 0

[task-start-emulator]
type: task
view: on
name: 启动模拟器
action: launch-emu, wait-10, launch-game
```
