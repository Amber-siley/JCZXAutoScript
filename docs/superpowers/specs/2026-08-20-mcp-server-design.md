# TUI 内嵌 MCP 服务 — Design

## 背景与问题

TUI（`jczx/jczxCli.py` 的 `JczxTUI`）运行时可操作模拟器设备（截图/点击/滑动/拖动），但只有人工在终端操作。希望让 **agent（Claude Code 等 MCP 客户端）** 能直接控制设备——截图查看当前画面、点击坐标、滑动、拖动——实现"agent 看见并操作游戏"的闭环。

## 目标

TUI 启动时**异步加载一个内嵌 MCP 服务**（与 OCR、ADB 的初始化方式一致），暴露 4 个工具，复用现有设备实现：

| 工具 | 入参 | 实现 |
|------|------|------|
| `screenshot` | 无（默认操作 TUI 当前选中设备） | `device.screenshot()` → PNG `Image` |
| `click` | 坐标 `x, y` | `device.click(x, y)` |
| `swipe` | 起点+终点+可选时长 | `device.swipe(x1, y1, x2, y2, duration=200)` |
| `drag` | 起点+终点+可选时长 | `device.dragAndDrop(x1, y1, x2, y2, duration=200)` |

**决策（用户确认）**：
- 滑动/拖动签名 = 起点 + 终点 + 可选时长（`duration` 默认 200ms），与现有 `Device.swipe`/`dragAndDrop` 一致
- 任务执行中 agent 调用工具：**允许但记录警告**（不阻断）
- 端口：`Config.txt` 新增 `mcp.port`（默认 8765），无开关（常开）

## 设计

### 1. 架构：内嵌进程 + streamable-http

MCP 服务**必须运行在 TUI 进程内**才能访问所选设备（`self.device`），因此 transport 只能是 **streamable-http**（绑定 `127.0.0.1`），agent 通过 `http://127.0.0.1:{port}/mcp` 连接。stdio 无法访问 TUI 进程内存，弃；独立代理进程双进程 + IPC 复杂，弃。

```
agent (Claude Code)
    │  HTTP / MCP 协议
    ▼
FastMCP(uvicorn, 127.0.0.1:port, 后台 daemon 线程)
    │  调用
    ▼
工具函数（闭包捕获 JczxCli 实例引用）
    │  惰性解析 self.device
    ▼
device.screenshot() / click() / swipe() / dragAndDrop()
```

### 2. 组件：`jczx/mcp_server.py`

`JczxMcpServer(host, port, logger)`：

- 持有 `FastMCP` 实例（`name="jczx-tui"`，`streamable_http=True`，`host="127.0.0.1"`，`port=port`）
- 持有 `host` 引用（`JczxCli` / `JczxTUI` 实例），工具调用时经 `host.device` 惰性获取设备
- `run()`：`asyncio.run(self._mcp.run(transport="streamable-http"))`，由外部 daemon 线程执行
- 4 个工具用 `@mcp.tool()` 装饰器注册；工具名 ASCII snake_case（MCP 规范），docstring 中文（成为工具描述）

工具签名与返回：

```python
screenshot() -> Image          # BGR ndarray → cv2.imencode('.png') → Image(data, format="png")
click(x: int, y: int) -> str   # 返回 "已点击 (x, y)"
swipe(x1, y1, x2, y2, duration: int = 200) -> str
drag(x1, y1, x2, y2, duration: int = 200) -> str
```

### 3. 数据流与错误处理

- **设备未连接**：`host.device is None` → 抛 `McpError("设备未连接")`，agent 可见。
- **设备方法异常**（截图编码失败、adb 断开）：捕获后抛清晰错误 + `logger.error`，不崩溃。
- **任务运行中**（`host.device._exec_mgr.is_running()`）：`logger.warning` 记录"agent 在任务执行期间调用 MCP 工具"，**照常执行**。
- **端口占用 / 启动失败**：`_init_mcp` 捕获异常 `logger.error`，不影响 TUI 其余功能。

### 4. 异步加载集成

`_init_something()` 加入第三个并行任务：

```python
def _init_something(self):
    self.thread_pool_run(self._init_device, self._init_ocr, self._init_mcp)
    if self.device:
        self.device.set_ocr(self.ocr)
```

`_init_mcp()`：

```python
def _init_mcp(self):
    port = int(self.config.get_config(opt="mcp.port") or "8765")
    self._mcp_server = JczxMcpServer(self, port, self.logger)
    threading.Thread(target=self._mcp_server.run, daemon=True, name="jczx-mcp").start()
    self.logger.info(f"MCP 服务已启动: http://127.0.0.1:{port}/mcp")
```

MCP 服务启动不依赖设备就绪（工具调用时才解析设备），故可与 `_init_device`/`_init_ocr` 并行，即使设备加载中，agent 也能连接并收到"设备未连接"提示。

### 5. 配置

`Config.txt` 新增：

```ini
mcp.port : 8765
```

### 6. 线程安全说明

`_init_mcp` 的 daemon 线程与 TUI 共享 `self.device`；设备操作（ScreenshotCache/recorder）非线程安全。按用户决策"允许但警告"，接受 agent 调用与任务运行的轻微竞态风险。agent 调用通常是离散操作，风险可接受。

## 工具连接方式（agent 侧）

TUI 运行后，agent（Claude Code）在 MCP 配置中加入 streamable-http 服务器：

```
claude mcp add --transport http jczx-tui http://127.0.0.1:8765/mcp
```

即可调用 `screenshot` / `click` / `swipe` / `drag` 四个工具。

## 排除范围

- MCP 服务的**鉴权/令牌**：当前仅绑定 127.0.0.1，后续如需再补
- TUI 界面展示 MCP 连接状态：不涉及
- 真实 cv2 合成图匹配：不涉及

## 依赖

新增 `mcp[cli]` 依赖（含 FastMCP / uvicorn / starlette）。**Python 3.14.6 兼容性需安装时验证**。

## 测试

`tests/engine/test_mcp_server.py`（复用 `fake_device.py` 桩替身：`object.__new__` 绕过 ADB 构造 + FakeMatcher/FakeToken）：

1. 4 个工具已注册且命名正确
2. `click` / `swipe` / `drag` 正确调用设备方法（坐标/时长透传）
3. `screenshot` 返回 `Image`（PNG 字节可解码）
4. 设备未连接 → 抛 `McpError("设备未连接")`
5. 任务运行中 → 记录警告但照常执行
