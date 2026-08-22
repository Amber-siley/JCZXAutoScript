# TUI 内嵌 MCP 服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TUI 启动时异步加载一个内嵌 MCP 服务，向 agent 暴露 4 个设备工具（截图/点击/滑动/拖动），复用现有 `Device` 实现。

**Architecture:** 服务运行在 TUI 进程内（才能访问 `self.device`），streamable-http 传输绑定 `127.0.0.1`，agent 经 `http://127.0.0.1:{port}/mcp` 连接。`JczxMcpServer` 类包装官方 `MCPServer`（mcp SDK v2），在 `_init_something` 中与 `_init_device`/`_init_ocr` 并行启动（后台 daemon 线程）。

**Tech Stack:** Python 3.14 + `mcp[cli]>=2.0.0`（已装）、Textual TUI、uv。SDK v2 API：`MCPServer`（`mcp.server`）、`Image`（`mcp.server.mcpserver.utilities.types`）、`@server.tool()` 装饰器、`server.run(transport="streamable-http", host, port)`。

**Spec:** [2026-08-20-mcp-server-design.md](../specs/2026-08-20-mcp-server-design.md)

## Global Constraints

- 依赖已用 `uv add "mcp[cli]"` 加入 pyproject（`"mcp[cli]>=2.0.0"`），**无需再装**。
- SDK v2 导入路径（已实测验证）：
  - `from mcp.server import MCPServer`
  - `from mcp.server.mcpserver.utilities.types import Image`
  - `@server.tool()`（**带括号**）注册工具
  - `server.run(transport="streamable-http", host="127.0.0.1", port=N)` 在后台线程运行
  - 工具内 `raise RuntimeError(...)` → 客户端收到 `is_error=True` + 消息文本
  - `list_tools()` 是 **async**，返回 `list[MCPTool]`
- 工具名固定 ASCII snake_case：`screenshot` / `click` / `swipe` / `drag`；docstring 中文（成为工具描述）。
- 手势签名：`swipe(x1, y1, x2, y2, duration=200)`、`drag(...)` 同，`duration` 毫秒。
- 并发：任务运行中 `logger.warning` 记录，**照常执行**。
- 提交格式 `[emoji: 中文信息]`；代码须经用户验证后再提交。

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `jczx/mcp_server.py` | 新建 | `JczxMcpServer`：包装 MCPServer + 4 个工具（`_do_*` 方法可单测） |
| `tests/engine/test_mcp_server.py` | 新建 | 引擎级测试：工具注册/行为/错误/忙时警告/`_init_mcp` 接线 |
| `jczx/jczxCli.py` | 修改 | 新增 `_init_mcp()`，`_init_something()` 加入第三个并行任务 |
| `jczx/Config/Config.txt` | 修改 | 新增 `mcp.port : 8765` |
| `tests/regression/test_config_loading.py` | 修改 | 新增 Config.txt 含 `mcp.port` 的回归断言 |

---

### Task 1: `jczx/mcp_server.py` — JczxMcpServer 与 4 个工具

**Files:**
- Create: `jczx/mcp_server.py`
- Test: `tests/engine/test_mcp_server.py`

**Interfaces:**
- Consumes: `host` 需提供 `.device`（JCZXGaming 或 None）与 `.logger`；`host.device` 提供 `screenshot()`（BGR ndarray）、`click(x,y)`、`swipe(x1,y1,x2,y2,duration)`、`dragAndDrop(x1,y1,x2,y2,duration)`、`_exec_mgr.is_running()`。
- Produces: `JczxMcpServer(host, port, logger)`，方法 `run()`、`_do_screenshot()->Image`、`_do_click(x,y)->str`、`_do_swipe(x1,y1,x2,y2,duration)->str`、`_do_drag(...)->str`、`_device()`、`_warn_if_busy(action)`，属性 `_mcp`（MCPServer）、`_port`。

- [ ] **Step 1: Write the failing test**

`tests/engine/test_mcp_server.py`：

```python
"""方案 2（引擎级）：JczxMcpServer — 4 个设备工具注册与行为。

host 桩替身：SimpleNamespace(device=make_gaming(...), logger=...)。
复用 fake_device 的 make_gaming（object.__new__ 绕过 ADB）。
"""
import asyncio
import logging
from types import SimpleNamespace

from jczx.mcp_server import JczxMcpServer


def make_host(gaming):
    return SimpleNamespace(device=gaming, logger=logging.getLogger("mcp-test"))


class TestToolRegistration:
    def test_four_tools_registered(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        names = {t.name for t in asyncio.run(server._mcp.list_tools())}
        assert names == {"screenshot", "click", "swipe", "drag"}


class TestDeviceOps:
    def test_click_calls_device(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_click(10, 20) == "已点击 (10, 20)"
        assert gaming.clicks == [(10, 20)]

    def test_swipe_calls_device(self, gaming):
        gaming.swipes = []
        gaming.swipe = lambda x1, y1, x2, y2, duration: gaming.swipes.append((x1, y1, x2, y2, duration))
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_swipe(0, 0, 100, 200) == "已滑动 (0,0) -> (100,200)"
        assert gaming.swipes == [(0, 0, 100, 200, 200)]

    def test_drag_calls_device(self, gaming):
        gaming.drags = []
        gaming.dragAndDrop = lambda x1, y1, x2, y2, duration: gaming.drags.append((x1, y1, x2, y2, duration))
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_drag(1, 2, 3, 4, 500) == "已拖动 (1,2) -> (3,4)"
        assert gaming.drags == [(1, 2, 3, 4, 500)]

    def test_screenshot_returns_png_image(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        img = server._do_screenshot()
        assert img.data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数
        assert img.format == "png"


class TestErrors:
    def test_device_not_connected_raises(self):
        host = SimpleNamespace(device=None, logger=logging.getLogger("mcp-test"))
        server = JczxMcpServer(host, 8765, logging.getLogger("mcp-test"))
        try:
            server._do_click(1, 1)
            assert False, "应抛设备未连接"
        except RuntimeError as e:
            assert "设备未连接" in str(e)


class TestBusyWarning:
    def test_busy_warns_but_executes(self, gaming, caplog):
        gaming._exec_mgr = SimpleNamespace(is_running=lambda: True, token=gaming.token)
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.WARNING, logger="mcp-test"):
            server._do_click(5, 5)
        assert gaming.clicks == [(5, 5)], "应照常执行"
        assert any("任务执行期间" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/engine/test_mcp_server.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'jczx.mcp_server'`

- [ ] **Step 3: Write the implementation**

`jczx/mcp_server.py`：

```python
"""TUI 内嵌 MCP 服务：向 agent 暴露设备控制工具（截图/点击/滑动/拖动）。

服务随 TUI 启动在后台 daemon 线程运行，streamable-http 传输，
agent 经 http://127.0.0.1:{port}/mcp 连接。
"""
import logging

import cv2
from mcp.server import MCPServer
from mcp.server.mcpserver.utilities.types import Image


class JczxMcpServer:
    """包装 MCPServer，注册 4 个设备操作工具，复用 JczxCli/设备现有实现。

    host 需提供: ``host.device``（JCZXGaming 或 None）、``host.logger``。
    """

    def __init__(self, host, port: int, logger: logging.Logger):
        self._host = host
        self._logger = logger
        self._port = port
        self._mcp = MCPServer(
            "jczx-tui",
            instructions="TUI 控制的游戏设备。截图/点击/滑动/拖动，默认操作 TUI 当前选中设备。",
        )
        self._register_tools()

    # ── 工具注册（薄包装委托 _do_*，便于单测）──

    def _register_tools(self):
        @self._mcp.tool()
        def screenshot() -> Image:
            """截取当前设备屏幕并返回 PNG 图片。"""
            return self._do_screenshot()

        @self._mcp.tool()
        def click(x: int, y: int) -> str:
            """在设备屏幕坐标 (x, y) 处点击。"""
            return self._do_click(x, y)

        @self._mcp.tool()
        def swipe(x1: int, y1: int, x2: int, y2: int, duration: int = 200) -> str:
            """从 (x1,y1) 滑动到 (x2,y2)，duration 毫秒。"""
            return self._do_swipe(x1, y1, x2, y2, duration)

        @self._mcp.tool()
        def drag(x1: int, y1: int, x2: int, y2: int, duration: int = 200) -> str:
            """从 (x1,y1) 拖拽到 (x2,y2)，duration 毫秒。"""
            return self._do_drag(x1, y1, x2, y2, duration)

    # ── 工具实现（可直接单测）──

    def _do_screenshot(self) -> Image:
        device = self._device()
        ok, buf = cv2.imencode(".png", device.screenshot())
        if not ok:
            raise RuntimeError("截图 PNG 编码失败")
        return Image(data=buf.tobytes(), format="png")

    def _do_click(self, x: int, y: int) -> str:
        device = self._device()
        self._warn_if_busy("点击")
        device.click(x, y)
        return f"已点击 ({x}, {y})"

    def _do_swipe(self, x1, y1, x2, y2, duration=200) -> str:
        device = self._device()
        self._warn_if_busy("滑动")
        device.swipe(x1, y1, x2, y2, duration)
        return f"已滑动 ({x1},{y1}) -> ({x2},{y2})"

    def _do_drag(self, x1, y1, x2, y2, duration=200) -> str:
        device = self._device()
        self._warn_if_busy("拖动")
        device.dragAndDrop(x1, y1, x2, y2, duration)
        return f"已拖动 ({x1},{y1}) -> ({x2},{y2})"

    # ── 辅助 ──

    def _device(self):
        device = getattr(self._host, "device", None)
        if device is None:
            raise RuntimeError("设备未连接")
        return device

    def _warn_if_busy(self, action: str) -> None:
        mgr = getattr(self._device(), "_exec_mgr", None)
        if mgr is not None and getattr(mgr, "is_running", lambda: False)():
            self._logger.warning(f"agent 在任务执行期间调用 MCP 工具[{action}]，可能干扰自动化")

    # ── 生命周期 ──

    def run(self) -> None:
        """在 daemon 线程中运行 streamable-http 服务（阻塞直到进程退出）。"""
        import asyncio
        asyncio.run(self._mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=self._port,
        ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/engine/test_mcp_server.py -v`
Expected: PASS（7 个用例：注册 1 + 操作 4 + 错误 1 + 忙时警告 1）

- [ ] **Step 5: Commit**

```bash
git add jczx/mcp_server.py tests/engine/test_mcp_server.py
git commit -m ":sparkles: TUI 内嵌 MCP 服务：4 个设备工具（截图/点击/滑动/拖动）"
```

---

### Task 2: `jczx/jczxCli.py` — 异步加载集成（`_init_mcp`）

**Files:**
- Modify: `jczx/jczxCli.py`（`_init_something` 约 1166 行、`__init__` 约 1141 行、新增 `_init_mcp` 方法在 `_init_ocr` 之后约 1302 行）
- Test: `tests/engine/test_mcp_server.py`（追加 `TestInitMcp` 类）

**Interfaces:**
- Consumes: `JczxMcpServer(host, port, logger)`（Task 1）、`self.config.get_config(opt="mcp.port")`、模块级 `threading`。
- Produces: `JczxCli._init_mcp()` 方法；`_init_something()` 现调 `thread_pool_run(self._init_device, self._init_ocr, self._init_mcp)`；`self._mcp_server` 属性。

- [ ] **Step 1: Write the failing test**

`tests/engine/test_mcp_server.py` 追加：

```python
from jczx.jczxCli import JczxCli


class TestInitMcp:
    def test_init_mcp_starts_daemon_thread(self, monkeypatch):
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: "8765")
        cli.logger = logging.getLogger("mcp-init-test")
        started = []

        class FakeThread:
            def __init__(self, target, daemon=False, name=None):
                self.target, self.daemon, self.name = target, daemon, name

            def start(self):
                started.append(self)

        monkeypatch.setattr("jczx.jczxCli.threading.Thread", FakeThread)
        monkeypatch.setattr("jczx.mcp_server.JczxMcpServer",
                            lambda host, port, logger: SimpleNamespace(host=host, port=port))
        cli._init_mcp()
        assert len(started) == 1
        assert started[0].daemon is True
        assert started[0].name == "jczx-mcp"
        assert cli._mcp_server.port == 8765

    def test_init_mcp_port_fallback(self, monkeypatch):
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: "abc")  # 非法端口
        cli.logger = logging.getLogger("mcp-init-test")
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name: SimpleNamespace(start=lambda: None))
        monkeypatch.setattr("jczx.mcp_server.JczxMcpServer",
                            lambda host, port, logger: SimpleNamespace(host=host, port=port))
        cli._init_mcp()
        assert cli._mcp_server.port == 8765

    def test_init_mcp_failure_logs_error(self, monkeypatch, caplog):
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: "8765")
        cli.logger = logging.getLogger("mcp-init-test")

        def boom(host, port, logger):
            raise RuntimeError("端口占用")

        monkeypatch.setattr("jczx.mcp_server.JczxMcpServer", boom)
        with caplog.at_level(logging.ERROR, logger="mcp-init-test"):
            cli._init_mcp()
        assert any("MCP 服务启动失败" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/engine/test_mcp_server.py::TestInitMcp -v`
Expected: FAIL，`AttributeError: 'JczxCli' object has no attribute '_init_mcp'`

- [ ] **Step 3: Write the implementation**

`jczx/jczxCli.py` 三处改动：

(1) `__init__` 中 `self.ocr = None`（约 1141 行）后加：

```python
        self._mcp_server = None
```

(2) `_init_something`（约 1166-1169 行）改为：

```python
    @error_exception
    def _init_something(self):
        self.thread_pool_run(self._init_device, self._init_ocr, self._init_mcp)
        if self.device:
            self.device.set_ocr(self.ocr)
```

(3) `_init_ocr` 方法（约 1302 行结束）后新增：

```python
    def _init_mcp(self):
        try:
            port = int(self.config.get_config(opt="mcp.port") or "8765")
        except (TypeError, ValueError):
            port = 8765
        try:
            from .mcp_server import JczxMcpServer
            self._mcp_server = JczxMcpServer(self, port, self.logger)
            threading.Thread(target=self._mcp_server.run, daemon=True, name="jczx-mcp").start()
            self.logger.info(f"MCP 服务已启动: http://127.0.0.1:{port}/mcp")
        except Exception as e:
            self.logger.error(f"MCP 服务启动失败: {e}")
```

> `threading` 已在 `jczx/jczxCli.py` 顶部 import（第 3 行）。`_init_mcp` 在 executor 线程中执行，`JczxMcpServer.run` 在**新起的 daemon 线程**中阻塞运行，故 `_init_mcp` 立即返回，`thread_pool_run` 可正常汇合。

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/engine/test_mcp_server.py -v`
Expected: PASS（10 个用例）

- [ ] **Step 5: Commit**

```bash
git add jczx/jczxCli.py tests/engine/test_mcp_server.py
git commit -m ":sparkles: MCP 服务随 TUI 启动异步加载（与 OCR/ADB 并行）"
```

---

### Task 3: `jczx/Config/Config.txt` — `mcp.port` 配置

**Files:**
- Modify: `jczx/Config/Config.txt`（`adb.port` 之后，约 18 行）
- Test: `tests/regression/test_config_loading.py`

**Interfaces:**
- Consumes: `real_config_dir` fixture（拷贝整个 `jczx/Config`）。
- Produces: `Config.txt` 含 `mcp.port : 8765`，Task 2 的 `_init_mcp` 读取它。

- [ ] **Step 1: Write the failing test**

`tests/regression/test_config_loading.py` 文件顶部导入区（当前 `import cv2` / `import numpy as np` / `from jczx.taskManage import TaskManage`）追加两行：

```python
from os.path import join

from jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig
```

类内追加用例：

```python
    def test_config_has_mcp_port(self, real_config_dir):
        cfg = TxtConfig(join(real_config_dir, "Config.txt"))
        assert cfg.get_config(opt="mcp.port") == "8765"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/regression/test_config_loading.py::TestConfigLoading::test_config_has_mcp_port -v`
Expected: FAIL，`KeyError`（无 mcp.port）

- [ ] **Step 3: Write the implementation**

`jczx/Config/Config.txt` 在 `adb.port : 7555` 之后新增两行：

```ini
/ MCP 服务端口（agent 连接 http://127.0.0.1:端口/mcp）
mcp.port : 8765
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/regression/test_config_loading.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add jczx/Config/Config.txt tests/regression/test_config_loading.py
git commit -m ":wrench: Config.txt 新增 mcp.port（MCP 服务端口）"
```

---

### Task 4: 全量回归与手动验证

**Files:** 无代码改动。

- [ ] **Step 1: 全量测试**

Run: `uv run pytest`
Expected: 全部 PASS（96 既有 + 10 MCP + 1 配置 = 107 左右）

- [ ] **Step 2: 手动端到端验证 TUI**

启动 TUI，确认日志出现 MCP 服务 URL：

```bash
uv run python -m jczx.jczxCli
```

Expected: 日志出现 `MCP 服务已启动: http://127.0.0.1:8765/mcp`，TUI 正常响应，无启动报错。

- [ ] **Step 3: 手动验证 agent 连接（可选）**

TUI 运行中，另开终端用 mcp 客户端连接并列出工具：

```bash
cat > /tmp/mcp_verify.py <<'PY'
import asyncio
from mcp.client import Client

async def main():
    async with Client("http://127.0.0.1:8765/mcp") as c:
        print([t.name for t in (await c.list_tools()).tools])

asyncio.run(main())
PY
uv run python -X utf8 /tmp/mcp_verify.py
```

Expected: 输出 `['screenshot', 'click', 'swipe', 'drag']`

- [ ] **Step 4: 提交状态确认**

Run: `git status`
Expected: 工作区干净（Task 1-3 已分别提交）
