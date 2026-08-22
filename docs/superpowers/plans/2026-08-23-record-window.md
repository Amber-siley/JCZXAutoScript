# TUI 记录窗口（Record Window）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **提交规则（用户明确指示）：禁止 Claude 提交 git，git 统一由用户提交。** 每个任务完成后**不执行 commit**，改动留在工作区累积，待用户验证后统一提交。

**Goal:** 为 TUI 新增【记录】功能：tkinter 独立窗口实时显示设备画面，自动手势识别点击/滑动/拖动，操作真实作用于设备并复用 DebugRecorder 标注截图，一次会话汇总为 JSON 保存到 screenHistory/。

**Architecture:** tkinter 记录窗口运行于独立子线程（Textual 主线程并存）；手势判定抽为纯函数 `classify_gesture` 可单测；设备操作复用 `JCZXGaming.click/swipe/dragAndDrop`（annotated 模式下 DebugRecorder 自动保存标注坐标截图），窗口只读取 `_recorder.last_saved` 关联 JSON。标注扩展为带坐标，全局生效。

**Tech Stack:** Python 3.14、tkinter（内置）、PIL（已有依赖）、cv2（已有）、Textual（已有）。

**Spec:** `docs/superpowers/specs/2026-08-23-record-window-design.md`（本 plan 实现此 spec，executor 需同时阅读 spec 与本 plan）

## Global Constraints

- 不新增第三方依赖（tkinter/PIL/cv2 均为现有可用）。
- 文件命名保持项目 camelCase 风格：`jczx/debug/recordWindow.py`。
- 中文注释、英文代码（项目风格）。
- `screenHistory/` 输出不随 CWD 变化（固定 `JczxCli._program_dir()`）。
- DebugRecorder 现有行为不变（数字命名截图逻辑不删改，仅新增 `last_saved` 属性 + 标注文本扩展）。
- 配置缺键/非法值回退默认：`get_config(opt=...)` 抛 `KeyError`/`TypeError`/`ValueError` 均回退（参考 `JczxCli._init_mcp` 写法）。
- **禁止提交 git**：所有任务完成后不 commit，由用户统一提交。

---

### Task 1: 标注坐标扩展（annotator.py）

**Files:**
- Modify: `jczx/debug/annotator.py`（`draw_click` / `draw_swipe`）
- Test: `tests/pure/test_annotator.py`（新建）

**Interfaces:**
- Produces: `ScreenAnnotator.draw_click(img, x, y)` 标签改为 `点击 (x, y)`；`draw_swipe(img, x1, y1, x2, y2, label)` 标签改为 `{label} (x1,y1)->(x2,y2)`。签名不变，调用方（DebugRecorder、MCP、记录窗口）无需改动。

- [ ] **Step 1: 写失败测试** `tests/pure/test_annotator.py`

```python
"""ScreenAnnotator 标注坐标扩展：点击/滑动标注应产生像素变化（标注生效）。"""
import numpy as np

from jczx.debug.annotator import ScreenAnnotator


class TestAnnotatorCoordinates:
    def test_draw_click_marks_image(self):
        img = np.zeros((100, 100, 3), np.uint8)
        out = img.copy()
        ScreenAnnotator.draw_click(out, 30, 40)
        assert not (out == img).all(), "点击标注应产生像素变化"

    def test_draw_swipe_marks_image(self):
        img = np.zeros((100, 100, 3), np.uint8)
        out = img.copy()
        ScreenAnnotator.draw_swipe(out, 10, 20, 80, 90, "滑动")
        assert not (out == img).all(), "滑动标注应产生像素变化"
```

- [ ] **Step 2: 运行确认通过**

Run: `uv run python -m pytest tests/pure/test_annotator.py -q`
Expected: 2 passed

> 注：现有 `draw_click` 已画十字/`draw_swipe` 已画箭头，本身会产生像素变化，故该断言在改动前即通过——本测试兜底"标注不抛异常且有视觉标注"，坐标文字内容由实现代码（Step 3）保证，可在全量回归通过后人工抽检标注图确认文字。

- [ ] **Step 3: 实现标注坐标**（`jczx/debug/annotator.py`）

```python
@classmethod
def draw_click(cls, img, x, y):
    cv2.drawMarker(img, (x, y), cls.COLOR,
                   cv2.MARKER_CROSS, cls.CROSS_SIZE, cls.THICKNESS)
    cls._draw_label(img, x, y, f"点击 ({x}, {y})")


@classmethod
def draw_swipe(cls, img, x1, y1, x2, y2, label):
    cv2.arrowedLine(img, (x1, y1), (x2, y2), cls.COLOR,
                    cls.THICKNESS, tipLength=0.1)
    cls._draw_label(img, x1, y1, f"{label} ({x1},{y1})->({x2},{y2})")
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/pure/test_annotator.py -q`
Expected: 2 passed

- [ ] **Step 5: 不提交**（用户统一提交，工作区累积）

---

### Task 2: DebugRecorder 记录最近截图（recorder.py）

**Files:**
- Modify: `jczx/debug/recorder.py`（`__init__` 加 `last_saved`；`_save` 更新）
- Test: `tests/engine/test_record_window.py`（新建）

**Interfaces:**
- Produces: `DebugRecorder.last_saved: str | None = None`，每次 `_save()` 后更新为刚保存的文件名（如 `"1.png"`）。Task 5 的 RecordWindow 通过 `device._recorder.last_saved` 读取。

- [ ] **Step 1: 写失败测试**（`tests/engine/test_record_window.py`，先建空文件再追加本类）

```python
import logging
import numpy as np

from jczx.debug.recorder import DebugRecorder


class TestRecorderLastSaved:
    def test_last_saved_updates_after_save(self, tmp_path):
        rec = DebugRecorder("annotated", str(tmp_path), logging.getLogger("record-test"))
        rec.on_click(np.zeros((10, 10, 3), np.uint8), 5, 5)
        assert rec.last_saved == "1.png", "on_click 保存后 last_saved 应为 1.png"
        rec.on_swipe(np.zeros((10, 10, 3), np.uint8), 0, 0, 5, 5, "滑动")
        assert rec.last_saved == "2.png", "on_swipe 保存后 last_saved 应为 2.png"

    def test_last_saved_default_none(self, tmp_path):
        rec = DebugRecorder("annotated", str(tmp_path), logging.getLogger("record-test"))
        assert rec.last_saved is None
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m pytest tests/engine/test_record_window.py::TestRecorderLastSaved -q`
Expected: FAIL（`AttributeError: 'DebugRecorder' object has no attribute 'last_saved'`）

- [ ] **Step 3: 实现**（`jczx/debug/recorder.py`）

`__init__` 末尾加：

```python
        self.last_saved: str | None = None   # 最近一次保存的截图文件名（记录窗口复用）
```

`_save` 改为：

```python
    def _save(self, img):
        path = os.path.join(self._output_dir, f"{self._index}.png")
        cv2.imwrite(path, img)
        self.last_saved = f"{self._index}.png"
        self._log.debug(f"调试截图 #{self._index} 已保存")
        self._index += 1
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/engine/test_record_window.py::TestRecorderLastSaved -q`
Expected: 2 passed

- [ ] **Step 5: 不提交**

---

### Task 3: 手势判定纯函数 + JSON 条目构造（recordWindow.py 顶层）

**Files:**
- Create: `jczx/debug/recordWindow.py`（本任务先写顶层函数 + docstring + import，Task 5 补 `RecordWindow` 类）
- Test: `tests/pure/test_gesture.py`（新建）

**Interfaces:**
- Produces:
  - `classify_gesture(press_t, press_x, press_y, release_t, release_x, release_y, move_start_t, click_move_threshold=15, hold_threshold=300) -> str`（`"click"` | `"swipe"` | `"drag"`）。时间单位为秒；`move_start_t` 为首次移动时间戳，从未移动为 `None`。
  - `build_action_entry(seq, gesture, x, y, x2, y2, duration, time_str, screenshot) -> dict`（构造单条操作记录，click 时 `x2`/`y2`/`duration` 为 `None`）。
- Consumes: 无。

- [ ] **Step 1: 写失败测试** `tests/pure/test_gesture.py`

```python
"""classify_gesture 三态判定 + build_action_entry 条目构造。"""
from jczx.debug.recordWindow import build_action_entry, classify_gesture


class TestClassifyGesture:
    def test_small_move_is_click(self):
        assert classify_gesture(0, 10, 10, 0.1, 12, 12, 0.02, 15, 300) == "click"

    def test_move_without_hold_is_swipe(self):
        assert classify_gesture(0, 10, 10, 0.4, 200, 200, 0.01, 15, 300) == "swipe"

    def test_move_with_hold_is_drag(self):
        assert classify_gesture(0, 10, 10, 0.8, 200, 200, 0.5, 15, 300) == "drag"

    def test_move_distance_equal_threshold_is_not_click(self):
        assert classify_gesture(0, 0, 0, 0.1, 15, 0, 0.05, 15, 300) == "swipe"

    def test_hold_equal_threshold_is_drag(self):
        assert classify_gesture(0, 0, 0, 0.8, 200, 0, 0.3, 15, 300) == "drag"


class TestBuildActionEntry:
    def test_click_entry(self):
        e = build_action_entry(1, "click", 100, 200, None, None, None, "15:30:01", "12.png")
        assert e == {
            "seq": 1, "type": "click", "x": 100, "y": 200,
            "x2": None, "y2": None, "duration": None,
            "time": "15:30:01", "screenshot": "12.png",
        }

    def test_swipe_entry_has_end_and_duration(self):
        e = build_action_entry(2, "swipe", 10, 20, 30, 40, 200, "15:30:02", "13.png")
        assert e["type"] == "swipe"
        assert e["x2"] == 30 and e["y2"] == 40 and e["duration"] == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m pytest tests/pure/test_gesture.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'jczx.debug.recordWindow'`）

- [ ] **Step 3: 实现** `jczx/debug/recordWindow.py`（先写顶层，类注释留给 Task 5）

```python
"""TUI 记录窗口：tkinter 实时画面 + 手势识别 + JSON 记录。

运行于独立子线程（tkinter mainloop 阻塞），复用 JCZXGaming 的设备操作
与 DebugRecorder 的标注截图（annotated 模式）。手势判定抽为顶层纯函数。
"""
import json
import math
import os
import time
import tkinter as tk

import cv2
from PIL import Image as PILImage, ImageTk


def classify_gesture(press_t, press_x, press_y, release_t, release_x, release_y,
                     move_start_t, click_move_threshold=15, hold_threshold=300):
    """按位移与移动前停留时长判定手势类型。

    - 位移 < click_move_threshold → "click"
    - 位移 ≥ click_move_threshold 且移动前停留 ≥ hold_threshold ms → "drag"
    - 其余 → "swipe"
    """
    dist = math.hypot(release_x - press_x, release_y - press_y)
    if dist < click_move_threshold:
        return "click"
    if move_start_t is not None and (move_start_t - press_t) * 1000 >= hold_threshold:
        return "drag"
    return "swipe"


def build_action_entry(seq, gesture, x, y, x2, y2, duration, time_str, screenshot):
    """构造单条操作记录。click 时 x2/y2/duration 为 None。"""
    return {
        "seq": seq,
        "type": gesture,
        "x": x, "y": y,
        "x2": x2, "y2": y2,
        "duration": duration,
        "time": time_str,
        "screenshot": screenshot,
    }
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/pure/test_gesture.py -q`
Expected: 7 passed

- [ ] **Step 5: 不提交**

---

### Task 4: 记录窗口配置项（Config.txt）

**Files:**
- Modify: `jczx/Config/Config.txt`（`debug.screenshot.mode` 之后追加）
- Test: `tests/regression/test_config_loading.py`（追加用例）

**Interfaces:**
- Produces: `record.click_move_threshold=15`、`record.hold_threshold=300`、`record.refresh_interval=200`。Task 5 的 RecordWindow 经 `config.get_config(opt=...)` 读取。

- [ ] **Step 1: 写失败测试**（`tests/regression/test_config_loading.py`，`TestConfigLoading` 类内追加）

```python
    def test_config_has_record_settings(self, real_config_dir):
        cfg = TxtConfig(join(real_config_dir, "Config.txt"))
        assert cfg.get_config(opt="record.click_move_threshold") == "15"
        assert cfg.get_config(opt="record.hold_threshold") == "300"
        assert cfg.get_config(opt="record.refresh_interval") == "200"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m pytest tests/regression/test_config_loading.py::TestConfigLoading::test_config_has_record_settings -q`
Expected: FAIL（`KeyError: 'record.click_move_threshold'`）

- [ ] **Step 3: 实现**（`jczx/Config/Config.txt`，`debug.screenshot.mode` 行之后追加）

```
/ 记录窗口：手势判定阈值与画面刷新间隔
record.click_move_threshold : 15
record.hold_threshold : 300
record.refresh_interval : 200
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/regression/test_config_loading.py -q`
Expected: PASS（原有 14 + 新增 1 = 15）

- [ ] **Step 5: 不提交**

---

### Task 5: RecordWindow 窗口类（recordWindow.py）

**Files:**
- Modify: `jczx/debug/recordWindow.py`（追加 `RecordWindow` 类）
- Test: `tests/engine/test_record_window.py`（追加本任务用例）

**Interfaces:**
- Consumes: Task 3 的 `classify_gesture` / `build_action_entry`；Task 1 的标注；Task 2 的 `_recorder.last_saved`；Task 4 的 `record.*` 配置。
- Produces: `RecordWindow(device, config, output_dir, log)`，`run()` 阻塞至窗口关闭；`_apply_gesture(gesture, px1, py1, px2, py2)`（像素坐标，内部换算设备坐标）；`_close()` 写 JSON。

- [ ] **Step 1: 写失败测试**（追加到 `tests/engine/test_record_window.py`）

```python
import json
import os
from types import SimpleNamespace

from jczx.debug.recordWindow import RecordWindow


class FakeRecordRecorder:
    """模拟 DebugRecorder：on_click/on_swipe 更新 last_saved。"""

    def __init__(self):
        self.last_saved = None
        self._n = 0

    def on_click(self, screenshot, x, y):
        self._n += 1
        self.last_saved = f"{self._n}.png"

    def on_swipe(self, *a, **k):
        self._n += 1
        self.last_saved = f"{self._n}.png"


def make_record_window(gaming, tmp_path, recorder):
    """构造 RecordWindow：不启动 tkinter，注入桩替身与固定配置。"""
    win = RecordWindow(
        gaming,
        SimpleNamespace(get_config=lambda opt: {
            "record.click_move_threshold": "15",
            "record.hold_threshold": "300",
            "record.refresh_interval": "200",
        }.get(opt, "")),
        str(tmp_path),
        logging.getLogger("record-test"),
    )
    win._session_id = "20260823_153000"
    win._scale = 1.0
    win._root = None
    win._last_gesture = None
    gaming._recorder = recorder
    gaming.device_id = "127.0.0.1:7555"
    gaming.size = (200, 200)
    return win


class TestRecordWindowApplyGesture:
    def test_click_applies_and_records(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.click = lambda x, y: (gaming.clicks.append((x, y)), rec.on_click(None, x, y))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("click", 30, 40, 30, 40)
        assert gaming.clicks == [(30, 40)], "应点击换算后的设备坐标"
        assert win._actions[0]["type"] == "click"
        assert win._actions[0]["x"] == 30 and win._actions[0]["y"] == 40
        assert win._actions[0]["screenshot"] == "1.png", "screenshot 应取自 recorder.last_saved"

    def test_swipe_applies_and_records(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.swipes = []
        gaming.swipe = lambda x1, y1, x2, y2, duration: (gaming.swipes.append((x1, y1, x2, y2, duration)), rec.on_swipe(None, x1, y1))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("swipe", 0, 0, 100, 200)
        assert gaming.swipes == [(0, 0, 100, 200, 200)], "swipe 应带默认时长 200"
        assert win._actions[0]["type"] == "swipe"
        assert win._actions[0]["x2"] == 100 and win._actions[0]["duration"] == 200

    def test_drag_applies_and_records(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.drags = []
        gaming.dragAndDrop = lambda x1, y1, x2, y2, duration: (gaming.drags.append((x1, y1, x2, y2, duration)), rec.on_swipe(None, x1, y1))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("drag", 1, 2, 3, 4)
        assert gaming.drags == [(1, 2, 3, 4, 200)]
        assert win._actions[0]["type"] == "drag"

    def test_coords_scaled_by_scale(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.click = lambda x, y: (gaming.clicks.append((x, y)), rec.on_click(None, x, y))
        win = make_record_window(gaming, tmp_path, rec)
        win._scale = 2.0
        win._apply_gesture("click", 60, 80, 60, 80)
        assert gaming.clicks == [(30, 40)], "像素坐标应除以缩放系数换算设备坐标"


class TestRecordWindowClose:
    def test_close_writes_json(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.click = lambda x, y: (gaming.clicks.append((x, y)), rec.on_click(None, x, y))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("click", 30, 40, 30, 40)
        win._close()
        path = os.path.join(str(tmp_path), "record_20260823_153000.json")
        assert os.path.exists(path), "关闭窗口应写出 JSON"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["session"] == "20260823_153000"
        assert data["device"] == "127.0.0.1:7555"
        assert data["resolution"] == [200, 200]
        assert data["actions"][0]["screenshot"] == "1.png"

    def test_close_no_actions_no_file(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        win = make_record_window(gaming, tmp_path, rec)
        win._close()
        path = os.path.join(str(tmp_path), "record_20260823_153000.json")
        assert not os.path.exists(path), "无操作时不生成 JSON"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m pytest tests/engine/test_record_window.py -q`
Expected: FAIL（`AttributeError: type object 'RecordWindow' has no attribute '...'` 或 `RecordWindow` 未定义）

- [ ] **Step 3: 实现 `RecordWindow` 类**（追加到 `jczx/debug/recordWindow.py`）

```python
class RecordWindow:
    """tkinter 记录窗口：实时画面 + 手势捕获 + JSON 记录。"""

    CANVAS_W = 800
    CANVAS_H = 600

    def __init__(self, device, config, output_dir, log):
        self._device = device
        self._config = config
        self._output_dir = output_dir
        self._log = log
        self._session_id = time.strftime("%Y%m%d_%H%M%S")
        self._actions = []
        self._seq = 1
        self._scale = None
        self._photo = None
        self._press_t = None
        self._press_xy = None
        self._move_start_t = None
        self._cur_xy = None
        self._last_gesture = None
        self._root = None
        self._click_move_threshold = self._cfg_int("record.click_move_threshold", 15)
        self._hold_threshold = self._cfg_int("record.hold_threshold", 300)
        self._refresh_interval = self._cfg_int("record.refresh_interval", 200)

    def _cfg_int(self, opt, default):
        """读取 int 配置，缺键/非法值回退默认。"""
        try:
            return int(self._config.get_config(opt=opt))
        except (KeyError, TypeError, ValueError):
            return default

    def run(self):
        """创建 Tk 窗口并 mainloop（阻塞直到窗口关闭）。"""
        self._root = tk.Tk()
        self._root.title(f"记录 - {self._session_id}")
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._canvas = tk.Canvas(self._root, width=self.CANVAS_W, height=self.CANVAS_H, bg="black")
        self._canvas.pack()
        self._status = tk.Label(self._root, text="", anchor="w")
        self._status.pack(fill="x")
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._refresh()
        self._root.mainloop()

    def _refresh(self):
        """定时拉取设备画面并显示到 Canvas。"""
        try:
            img = self._device.screenshot()
            h, w = img.shape[:2]
            scale = min(self.CANVAS_W / w, self.CANVAS_H / h)
            self._scale = scale
            display = cv2.resize(img, (max(int(w * scale), 1), max(int(h * scale), 1)))
            rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            self._photo = ImageTk.PhotoImage(PILImage.fromarray(rgb))
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
            self._status.config(
                text=f"{w}x{h}  缩放 {scale:.2f}  操作 {self._seq - 1}  {self._last_gesture or ''}"
            )
        except Exception as e:
            self._log.warning(f"记录窗口刷新失败: {e}")
        self._root.after(self._refresh_interval, self._refresh)

    def _on_press(self, event):
        self._press_t = time.time()
        self._press_xy = (event.x, event.y)
        self._move_start_t = None
        self._cur_xy = (event.x, event.y)

    def _on_motion(self, event):
        if self._move_start_t is None:
            self._move_start_t = time.time()
        self._cur_xy = (event.x, event.y)

    def _on_release(self, event):
        if self._press_xy is None:
            return
        px, py = self._press_xy
        gesture = classify_gesture(
            self._press_t, px, py, time.time(), event.x, event.y,
            self._move_start_t, self._click_move_threshold, self._hold_threshold,
        )
        self._apply_gesture(gesture, px, py, event.x, event.y)
        self._press_xy = None

    def _apply_gesture(self, gesture, px1, py1, px2, py2):
        """设备操作（复用 DebugRecorder 标注截图）+ 记录条目。"""
        x1 = round(px1 / self._scale) if self._scale else px1
        y1 = round(py1 / self._scale) if self._scale else py1
        x2 = round(px2 / self._scale) if self._scale else px2
        y2 = round(py2 / self._scale) if self._scale else py2
        time_str = time.strftime("%H:%M:%S")
        if gesture == "click":
            self._device.click(x1, y1)
            entry = build_action_entry(self._seq, "click", x1, y1, None, None, None,
                                       time_str, self._last_saved())
        elif gesture == "swipe":
            self._device.swipe(x1, y1, x2, y2, 200)
            entry = build_action_entry(self._seq, "swipe", x1, y1, x2, y2, 200,
                                       time_str, self._last_saved())
        else:  # drag
            self._device.dragAndDrop(x1, y1, x2, y2, 200)
            entry = build_action_entry(self._seq, "drag", x1, y1, x2, y2, 200,
                                       time_str, self._last_saved())
        self._actions.append(entry)
        self._seq += 1
        self._last_gesture = gesture
        self._log.info(f"记录操作 [{gesture}] ({x1},{y1}) -> ({x2},{y2})")

    def _last_saved(self):
        """读取 DebugRecorder 最近保存的标注截图文件名。"""
        recorder = getattr(self._device, "_recorder", None)
        return getattr(recorder, "last_saved", None)

    def _close(self):
        """会话结束，写 JSON。"""
        if self._actions:
            data = {
                "session": self._session_id,
                "device": getattr(self._device, "device_id", ""),
                "resolution": list(self._device.size) if getattr(self._device, "size", None) else [],
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "actions": self._actions,
            }
            path = os.path.join(self._output_dir, f"record_{self._session_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log.info(f"记录已保存: {path}")
        else:
            self._log.info("无操作，未生成记录")
        if self._root is not None:
            self._root.destroy()
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/engine/test_record_window.py -q`
Expected: 全 PASS（本任务用例 + Task 2 的 TestRecorderLastSaved）

- [ ] **Step 5: 不提交**

---

### Task 6: DeviceBar "记录" 按钮（widgets.py）

**Files:**
- Modify: `jczx/widgets.py`（`DeviceBar`）
- Test: `tests/engine/test_record_window.py`（追加用例）

**Interfaces:**
- Produces: `DeviceBar(..., show_record: bool = False)` 参数；`DeviceBar.RecordPressed` 消息类；`show_record=True` 时 compose 产出 `id="record-btn"` 的 `LabelButton`。
- Consumes: 无。

- [ ] **Step 1: 写失败测试**（追加到 `tests/engine/test_record_window.py`）

```python
from jczx.widgets import DeviceBar


class TestDeviceBarRecordButton:
    def test_record_button_shown_when_show_record(self):
        bar = DeviceBar(show_record=True)
        ids = [w.id for w in bar.compose()]
        assert "record-btn" in ids, "show_record=True 时应渲染记录按钮"

    def test_record_button_hidden_by_default(self):
        bar = DeviceBar()
        ids = [w.id for w in bar.compose()]
        assert "record-btn" not in ids, "默认不渲染记录按钮"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m pytest tests/engine/test_record_window.py::TestDeviceBarRecordButton -q`
Expected: FAIL（`TypeError: DeviceBar.__init__() got an unexpected keyword argument 'show_record'`）

- [ ] **Step 3: 实现**（`jczx/widgets.py`）

`DeviceBar` 类内新增消息类：

```python
    class RecordPressed(Message):
        """Emitted when the record button is pressed."""
```

`__init__` 增加参数并保存：

```python
    def __init__(
        self,
        devices: list[str] | None = None,
        current_device: str = "",
        current_port: str = "7555",
        show_record: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._devices = devices or []
        self._current_device = current_device
        self._current_port = current_port
        self._show_record = show_record
```

`compose()` 中 `config-reload-btn` 之后追加：

```python
        yield LabelButton("重载配置", id="config-reload-btn")
        if self._show_record:
            yield LabelButton("记录", id="record-btn")
```

`on_label_button_pressed` 中 `config-reload-btn` 分支后追加：

```python
        elif event.sender_id == "record-btn":
            self.post_message(self.RecordPressed())
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/engine/test_record_window.py::TestDeviceBarRecordButton -q`
Expected: 2 passed

- [ ] **Step 5: 不提交**

---

### Task 7: TUI 接线（jczxCli.py JczxTUI）

**Files:**
- Modify: `jczx/jczxCli.py`（`JczxTUI.compose` + 新 handler）
- Test: `tests/engine/test_record_window.py`（追加用例）

**Interfaces:**
- Consumes: Task 6 的 `DeviceBar.show_record` / `DeviceBar.RecordPressed`；Task 5 的 `RecordWindow`。
- Produces: `JczxTUI.on_device_bar_record_pressed(event)`；`JczxTUI._run_record_window()`。
- Note: `jczxCli.py` 已 `import threading`（`_init_mcp` 使用），无需新增导入。

- [ ] **Step 1: 写失败测试**（追加到 `tests/engine/test_record_window.py`）

```python
from jczx.jczxCli import JczxTUI


class TestRecordPressed:
    def test_no_device_warns_and_no_thread(self, monkeypatch, caplog):
        cli = object.__new__(JczxTUI)
        cli.device = None
        cli.logger = logging.getLogger("record-test")
        started = []
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name=None: SimpleNamespace(start=lambda: started.append(target)))
        cli.on_device_bar_record_pressed(SimpleNamespace())
        assert started == [], "设备未连接不应启动线程"
        assert any("设备未连接" in r.message for r in caplog.records)

    def test_device_starts_thread(self, monkeypatch):
        cli = object.__new__(JczxTUI)
        cli.device = SimpleNamespace(_exec_mgr=SimpleNamespace(is_running=lambda: False))
        cli.logger = logging.getLogger("record-test")
        started = []
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name=None: SimpleNamespace(start=lambda: started.append(target)))
        cli.on_device_bar_record_pressed(SimpleNamespace())
        assert len(started) == 1, "设备已连接应启动记录线程"
        assert started[0].daemon is True
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m pytest tests/engine/test_record_window.py::TestRecordPressed -q`
Expected: FAIL（`AttributeError: 'JczxTUI' object has no attribute 'on_device_bar_record_pressed'`）

- [ ] **Step 3: 实现**（`jczx/jczxCli.py`）

`JczxTUI.compose()` 中 DeviceBar 调用增加 `show_record`：

```python
        yield DeviceBar(
            devices=devices,
            current_device=current_device,
            current_port=self.config.get_config(opt="adb.port") or "7555",
            show_record=(self.config.get_config(opt="debug.screenshot.mode") == "annotated"),
        )
```

在 `on_device_bar_reload_pressed` 之后新增：

```python
    def on_device_bar_record_pressed(self, event: DeviceBar.RecordPressed) -> None:
        if not self.device:
            self.logger.warning("设备未连接，无法打开记录窗口")
            return
        if self.device._exec_mgr.is_running():
            self.logger.warning("任务执行中打开记录窗口，可能互相干扰")
        self.logger.info("打开记录窗口...")
        threading.Thread(target=self._run_record_window, daemon=True).start()

    def _run_record_window(self) -> None:
        from .debug.recordWindow import RecordWindow
        window = RecordWindow(
            self.device,
            self.config,
            os.path.join(self._program_dir(), "screenHistory"),
            self.logger,
        )
        window.run()
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m pytest tests/engine/test_record_window.py -q`
Expected: 全 PASS（Task 2/5/6/7 全部用例）

- [ ] **Step 5: 不提交**

---

## 验证汇总

- **全量测试**：`uv run python -m pytest -q`。预期新增用例全过；既有失败 `test_exec_match.py::test_non_bool_none_result_not_written` 为已知既有状态（b9747a3 revert 引入），与本功能无关。
- **手动验证**（用户）：`uv run python -m jczx.jczxCli` → 确认 DeviceBar 出现"记录"按钮（当前 `debug.screenshot.mode=annotated`）→ 点击"记录"打开 tkinter 窗口，实时画面刷新 → 点击/滑动/拖动画面，观察设备真实响应 → 关闭窗口 → 检查 `screenHistory/record_<时间戳>.json` 与对应标注截图。
- 工作区改动（用户统一提交）：`jczx/debug/annotator.py`、`jczx/debug/recorder.py`、`jczx/debug/recordWindow.py`（新建）、`jczx/widgets.py`、`jczx/jczxCli.py`、`jczx/Config/Config.txt`、`tests/pure/test_annotator.py`（新建）、`tests/pure/test_gesture.py`（新建）、`tests/engine/test_record_window.py`（新建）、`tests/regression/test_config_loading.py`。
