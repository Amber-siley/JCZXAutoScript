# TUI 记录窗口（Record Window）设计

## 目标

为 TUI 新增【记录】功能：一个独立 GUI 窗口同步显示设备画面，用户在窗口中对游戏进行点击/滑动/拖动操作（自动手势识别），每次操作真实作用于设备，并记录操作坐标、时间与对应的**标注坐标截图**到 `screenHistory/`。一次记录会话汇总为一个 JSON 文件。

## 背景与约束

- 仅 Windows，Textual TUI 主入口 `python -m jczx.jczxCli`（实际 `main.py`）。
- **Textual 无法显示设备画面**：Textual 8.2.7 无 `Image` widget，Windows 终端不支持 sixel/kitty 图形协议。新窗口必须用 **tkinter**（Python 内置，零新增依赖）。
- tkinter 必须在创建它的线程中 `mainloop()`，故记录窗口运行于**独立子线程**，与 Textual 主线程并存。
- 设备操作复用现有 `JCZXGaming`（`jczx/jczxCli.py`）的 `click` / `swipe` / `dragAndDrop`，以及 `device.screenshot()`。
- 标注截图复用现有 `ScreenAnnotator`（`jczx/debug/annotator.py`），**需扩展为标注坐标**。
- 输出目录固定为 `<程序根>/screenHistory/`（`JczxCli._program_dir()`）。
- 不新增任何第三方依赖。

## 配置项（`jczx/Config/Config.txt`）

在 `debug.screenshot.mode` 之后新增：

```
/ 记录窗口：手势判定阈值与画面刷新间隔
record.click_move_threshold : 15
record.hold_threshold : 300
record.refresh_interval : 200
```

| 配置 | 默认 | 含义 |
|---|---|---|
| `record.click_move_threshold` | 15 | 位移阈值（设备像素）。位移小于此值 → 点击 |
| `record.hold_threshold` | 300 | 停留阈值（毫秒）。移动前按住不动达到此值 → 拖动 |
| `record.refresh_interval` | 200 | 记录窗口画面刷新间隔（毫秒） |

读取方式：`config.get_config(opt=...)`；缺键/非法值时回退默认（`KeyError`/`ValueError`/`TypeError` 均回退，参考 `_init_mcp` 的写法）。

## 组件与文件

| 组件 | 文件 | 动作 |
|---|---|---|
| 标注坐标扩展 | `jczx/debug/annotator.py` | 修改 |
| 记录窗口（tkinter） | `jczx/debug/recordWindow.py` | 新建 |
| 手势判定纯函数 | 同上 | 新建（顶层函数，可单测） |
| DeviceBar "记录" 按钮 | `jczx/widgets.py` | 修改 |
| DebugRecorder 记录最近截图 | `jczx/debug/recorder.py` | 修改 |
| TUI 接线 | `jczx/jczxCli.py`（`JczxTUI`） | 修改 |
| 配置项 | `jczx/Config/Config.txt` | 修改 |

## 1. 标注坐标扩展（`annotator.py`）

`ScreenAnnotator` 两个方法改为输出坐标文本（**全局生效**：任务执行 DebugRecorder、MCP 工具的标注截图都会带坐标）：

- `draw_click(img, x, y)`：十字不变，标签改为 `点击 (x, y)`。
- `draw_swipe(img, x1, y1, x2, y2, label)`：箭头不变，标签改为 `{label} (x1,y1)->(x2,y2)`，其中 `label` 由调用方传入（现有调用传 `"滑动"` / `"拖动"`，无需改）。

坐标文本用现有 `_draw_label` 机制（PIL 中文渲染）绘制。

## 2. 手势判定纯函数（`recordWindow.py` 顶层）

```python
def classify_gesture(
    press_t: float, press_x: float, press_y: float,
    release_t: float, release_x: float, release_y: float,
    move_start_t: float | None,
    click_move_threshold: float = 15,
    hold_threshold: float = 300,
) -> str:
    """按位移与移动前停留时长判定手势类型。

    - 位移 < click_move_threshold → "click"
    - 位移 ≥ click_move_threshold 且移动前停留 ≥ hold_threshold ms → "drag"
    - 其余 → "swipe"
    """
```

时间单位为 `time.time()` 秒；`move_start_t` 为第一次移动（Motion）的时间戳，从未移动则为 `None`。

判定逻辑：

```python
import math
dist = math.hypot(release_x - press_x, release_y - press_y)
if dist < click_move_threshold:
    return "click"
if move_start_t is not None and (move_start_t - press_t) * 1000 >= hold_threshold:
    return "drag"
return "swipe"
```

要点：**拖动 = 刚开始有停留**（按住不动达到 `hold_threshold` 才移动）；**滑动 = 无停留直接移动**；**点击 = 位移小**（不按时长）。

## 3. 记录窗口（`recordWindow.py`）

```python
class RecordWindow:
    """tkinter 记录窗口：实时画面 + 手势捕获 + JSON 记录。"""

    def __init__(self, device, config, output_dir: str, log):
        # device: JCZXGaming；config: TxtConfig；output_dir: screenHistory 绝对路径
        ...

    def run(self) -> None:
        """创建 Tk 窗口并 mainloop()（阻塞直到窗口关闭）。"""

    def _refresh(self) -> None:
        """after(refresh_interval) 拉取 device.screenshot()，等比缩放显示到 Canvas。"""

    def _on_press(self, event): ...    # 记录起点 + 时间戳
    def _on_motion(self, event): ...   # 记录首次移动时间、当前点
    def _on_release(self, event): ...  # classify_gesture → _apply_gesture
    def _apply_gesture(self, gesture: str, ...) -> None:
        """设备操作（复用 DebugRecorder 标注截图）+ 记录条目。"""
    def _close(self) -> None:
        """会话结束，写 JSON。"""
```

### 窗口 UI

- `Canvas`：主区域，等比缩放显示设备画面（`PIL.Image` → `ImageTk.PhotoImage`，注意保留引用防 GC）。
- 缩放系数：`scale = min(canvas_w / img_w, canvas_h / img_h)`，按设备当前分辨率计算后固定。鼠标像素 → 设备坐标：`round(px / scale)`。
- 底部状态栏 `Label`：设备分辨率、缩放比例、操作计数、最近一次操作类型。

### 手势捕获

Canvas 绑定事件：

- `<ButtonPress-1>`：记录 `press_t = time.time()`、起点像素。
- `<B1-Motion>`：首次移动时记录 `move_start_t`；持续更新当前点（供释放时使用）。
- `<ButtonRelease-1>`：读终点像素，换算设备坐标，调用 `classify_gesture` 得到类型。

### 每次操作（`_apply_gesture`）

1. 换算设备坐标：`x = round(px_x / scale)`，`y = round(px_y / scale)`。
2. **复用 cli 的点击/滑动/拖动**：直接调用 `JCZXGaming` 方法，annotated 模式下 `DebugRecorder` 自动截取画面、标注坐标并保存到 `screenHistory/N.png`：
   - `click`：`device.click(x, y)`
   - `swipe`：`device.swipe(x1, y1, x2, y2, duration=200)`
   - `drag`：`device.dragAndDrop(x1, y1, x2, y2, duration=200)`
3. 读取 DebugRecorder 最近保存的标注截图文件名：`device._recorder.last_saved`（如 `"12.png"`）。
4. 追加记录条目（内存列表），`screenshot` 字段引用该文件名。

> **不单独保存截图**：标注截图完全复用 `DebugRecorder`（annotated 模式下 `on_click`/`on_swipe` 必然保存）。记录窗口不再自行截图/标注/保存。

### 会话与 JSON

- `sessionId = time.strftime("%Y%m%d_%H%M%S")`。
- 窗口关闭（WM_DELETE_WINDOW → `_close`）：若 `actions` 非空则写 `<output_dir>/record_<sessionId>.json`；为空则日志提示"无操作，未生成记录"。
- 窗口关闭后线程自然结束；再次点击"记录"可开新会话。

### JSON 格式

```json
{
  "session": "20260823_153000",
  "device": "127.0.0.1:7555",
  "resolution": [2400, 1080],
  "started_at": "2026-08-23 15:30:00",
  "actions": [
    {
      "seq": 1,
      "type": "click",
      "x": 100, "y": 200,
      "x2": null, "y2": null,
      "duration": null,
      "time": "15:30:01",
      "screenshot": "12.png"
    }
  ]
}
```

- `type`：`"click"` | `"swipe"` | `"drag"`。
- `click`：仅 `x`/`y`，`x2`/`y2`/`duration` 为 `null`。
- `swipe`/`drag`：`x`/`y` 起点、`x2`/`y2` 终点、`duration`（毫秒，默认 200）。
- `time`：操作时间 `%H:%M:%S`。
- `screenshot`：该操作对应的标注截图文件名（DebugRecorder 数字命名，如 `"12.png"`，位于 `screenHistory/` 目录）。

## 4. TUI 按钮（`widgets.py` DeviceBar）

- `DeviceBar.__init__` 增加参数 `show_record: bool = False`。
- `compose()`：在 `config-reload-btn` 之后：

  ```python
  if self._show_record:
      yield LabelButton("记录", id="record-btn")
  ```

- `on_label_button_pressed` 增加分支：

  ```python
  elif event.sender_id == "record-btn":
      self.post_message(self.RecordPressed())
  ```

- 新增消息类 `class RecordPressed(Message)`。

## 5. DebugRecorder 记录最近截图（`jczx/debug/recorder.py`）

`JCZXGaming.click/swipe/dragAndDrop` 操作前已触发 `DebugRecorder.on_click/on_swipe`（annotated 模式保存 `screenHistory/N.png`）。记录窗口**复用**这一机制作为"操作时标注的截图"，不单独保存截图。

方案：给 `DebugRecorder` 增加属性 `last_saved: str | None = None`，在 `_save()` 中更新为刚保存的文件名：

```python
def _save(self, img):
    path = os.path.join(self._output_dir, f"{self._index}.png")
    cv2.imwrite(path, img)
    self.last_saved = f"{self._index}.png"   # 新增：记录最近保存的截图文件名
    self._log.debug(f"调试截图 #{self._index} 已保存")
    self._index += 1
```

记录窗口每次操作后读取 `device._recorder.last_saved` 关联到 JSON 的 `screenshot` 字段。

**并发注意**：记录窗口操作与任务执行并存时，DebugRecorder 序号会被任务操作占用，`last_saved` 可能指向任务刚保存的截图。记录窗口操作是同步短操作（点击 → 立即读 `last_saved`），且场景为用户手动操作，通常不与任务并发；若并发，标注截图归属可能错位（可接受，日志提示）。

## 6. TUI 接线（`jczx/jczxCli.py` JczxTUI）

- `compose()` 中 DeviceBar 传入：

  ```python
  show_record=(self.config.get_config(opt="debug.screenshot.mode") == "annotated")
  ```

- 新增 handler：

  ```python
  def on_device_bar_record_pressed(self, event: DeviceBar.RecordPressed) -> None:
      if not self.device:
          self.logger.warning("设备未连接，无法打开记录窗口")
          return
      self.logger.info("打开记录窗口...")
      threading.Thread(target=self._run_record_window, daemon=True).start()

  def _run_record_window(self) -> None:
      from .debug.recordWindow import RecordWindow
      window = RecordWindow(self.device, self.config, os.path.join(self._program_dir(), "screenHistory"), self.logger)
      window.run()
  ```

- 并发注意：记录窗口操作与任务执行并存时可能互相干扰（`_warn_if_busy` 同款提示）。记录窗口打开前若 `device._exec_mgr.is_running()` 则 `logger.warning` 提示，但仍允许打开。

## 7. 生命周期与线程

- 点击"记录" → 子线程 `threading.Thread(target=..., daemon=True)`。
- 子线程内创建 `Tk()` + `mainloop()`，阻塞直至窗口关闭。
- 窗口关闭 → 写 JSON → `mainloop` 返回 → 线程结束。
- TUI 退出时 daemon 线程随之终止（若记录窗口还开着，未写完的会话丢弃，可接受）。

## 测试计划

**pure（`tests/pure/`）**
- `classify_gesture`：点击（位移小）、滑动（位移大 + 无停留移动）、拖动（位移大 + 移动前停留 ≥ hold_threshold）三态；边界：位移恰等于阈值、停留恰等于阈值。
- 记录 JSON 条目序列化：`click`/`swipe`/`drag` 三类型字段正确（`x2`/`y2`/`duration` 的 null 与非 null）。

**engine（`tests/engine/`）**
- `ScreenAnnotator.draw_click` / `draw_swipe`：调用后输出图像与输入相比产生像素变化（标注生效），且不抛异常。
- `classify_gesture` 经记录窗口调用路径（`_apply_gesture` 用 FakeDevice 桩验证 click/swipe/drag 依次收到正确参数）。
- `DebugRecorder.last_saved`：`_save` 后更新为刚保存的文件名；`JCZXGaming.click` 触发 `on_click` 后 `_recorder.last_saved` 指向该截图。
- `RecordWindow` 设备操作：FakeDevice 桩验证 click/swipe/drag 依次收到正确参数，且 JSON 条目的 `screenshot` 字段取自 `_recorder.last_saved`。

**widgets**
- `DeviceBar` `show_record=True` 时含 `record-btn`，`False` 时不含。

**jczxCli**
- `on_device_bar_record_pressed`：设备未连接 → 警告不启动；设备已连接 → monkeypatch `threading.Thread` 断言启动。

## 全局约束

- 不新增第三方依赖（tkinter/PIL 均为现有可用）。
- 文件命名保持项目 camelCase 风格：`jczx/debug/recordWindow.py`。
- 中文注释、英文代码（项目风格）。
- `screenHistory/` 输出不随 CWD 变化（固定 `_program_dir()`）。
- DebugRecorder 现有行为不变（数字命名截图逻辑不删改，仅新增 `last_saved` 属性 + 标注文本扩展）。
