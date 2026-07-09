# 调试截图可视化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 TUI 脚本执行添加调试可视化——两种模式（连续截图 / 标注截图），通过 Config.txt 控制，对现有逻辑零副作用。

**Architecture:** 新建 `jczx/debug/` 包，`DebugRecorder` 管理模式和文件 I/O，`ScreenAnnotator` 负责 cv2 绘图。`JCZXGaming` 持有可选的 `_recorder` 引用，在 click/swipe/drag/exec_match/exec_ocr 中注入一行调用。

**Tech Stack:** Python stdlib + cv2 (OpenCV，项目已依赖)

**Files:** 3 new (`jczx/debug/`), 2 modified (`jczxCli.py`, `Config.txt`)

---

### Task 1: Create debug package — annotator.py + __init__.py

**Files:**
- Create: `jczx/debug/__init__.py`
- Create: `jczx/debug/annotator.py`

- [ ] **Step 1: Create `jczx/debug/__init__.py`**

```python
from .recorder import DebugRecorder
from .annotator import ScreenAnnotator
```

- [ ] **Step 2: Create `jczx/debug/annotator.py`**

```python
import cv2


class ScreenAnnotator:
    COLOR = (0, 255, 0)
    THICKNESS = 2
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE = 0.5
    CROSS_SIZE = 10

    @classmethod
    def _draw_label(cls, img, x, y, text):
        cv2.putText(img, text, (x + 4, y - 4),
                    cls.FONT, cls.FONT_SCALE, cls.COLOR, 1)

    @classmethod
    def draw_click(cls, img, x, y):
        cv2.drawMarker(img, (x, y), cls.COLOR,
                       cv2.MARKER_CROSS, cls.CROSS_SIZE, cls.THICKNESS)
        cls._draw_label(img, x, y, "点击")

    @classmethod
    def draw_match(cls, img, pts, index):
        (x0, y0), (x1, _y0), (_x0, y1), (_x1, _y1) = pts
        cv2.rectangle(img, (x0, y0), (x1, y1), cls.COLOR, cls.THICKNESS)
        cls._draw_label(img, x0, y0, f"匹配:{index}")

    @classmethod
    def draw_swipe(cls, img, x1, y1, x2, y2, label):
        cv2.arrowedLine(img, (x1, y1), (x2, y2), cls.COLOR,
                        cls.THICKNESS, tipLength=0.1)
        cls._draw_label(img, x1, y1, label)

    @classmethod
    def draw_ocr(cls, img, pt_range, text):
        if pt_range is None:
            return
        (x0, y0), (x1, y1) = pt_range
        cv2.rectangle(img, (x0, y0), (x1, y1), cls.COLOR, cls.THICKNESS)
        cls._draw_label(img, x0, y0, f"OCR: {text}")
```

- [ ] **Step 3: Commit**

```bash
git add jczx/debug/__init__.py jczx/debug/annotator.py
git commit -m "feat: add debug package with ScreenAnnotator"
```

---

### Task 2: Create DebugRecorder (recorder.py)

**Files:**
- Create: `jczx/debug/recorder.py`
- Modify: `jczx/debug/__init__.py` (already done in Task 1, import pre-existing)

- [ ] **Step 1: Create `jczx/debug/recorder.py`**

```python
import os
import shutil
import cv2
from logging import Logger
from cv2.typing import MatLike

from ..CommoneBuilder.CommonBuilder.Android.Adb import MatchTemplete
from .annotator import ScreenAnnotator


class DebugRecorder:
    MODE_OFF = "off"
    MODE_SIMPLE = "simple"
    MODE_ANNOTATED = "annotated"

    def __init__(self, mode: str, output_dir: str, log: Logger):
        self._mode = mode
        self._output_dir = output_dir
        self._index = 1
        self._log = log
        self._annotator = ScreenAnnotator()

    def ensure_dir(self):
        if os.path.isdir(self._output_dir):
            for f in os.listdir(self._output_dir):
                os.remove(os.path.join(self._output_dir, f))
            self._log.debug(f"已清空调试截图目录 {self._output_dir}")
        else:
            os.makedirs(self._output_dir, exist_ok=True)

    def _save(self, img):
        path = os.path.join(self._output_dir, f"{self._index}.png")
        cv2.imwrite(path, img)
        self._log.debug(f"调试截图 #{self._index} 已保存")
        self._index += 1

    def on_step(self, screenshot: MatLike):
        if self._mode == self.MODE_SIMPLE:
            self._save(screenshot)

    def on_match(self, screenshot: MatLike, mt: MatchTemplete):
        if self._mode != self.MODE_ANNOTATED or not mt.matched:
            return
        for idx, pts in enumerate(mt.matchTempletePoints):
            self._annotator.draw_match(screenshot, pts, idx)
        self._save(screenshot)

    def on_click(self, screenshot: MatLike, x: int, y: int):
        if self._mode != self.MODE_ANNOTATED:
            return
        self._annotator.draw_click(screenshot, x, y)
        self._save(screenshot)

    def on_swipe(self, screenshot: MatLike, x1, y1, x2, y2, label: str):
        if self._mode != self.MODE_ANNOTATED:
            return
        self._annotator.draw_swipe(screenshot, x1, y1, x2, y2, label)
        self._save(screenshot)

    def on_ocr(self, screenshot: MatLike, mt: MatchTemplete, text: str):
        if self._mode != self.MODE_ANNOTATED or not mt.matched:
            return
        self._annotator.draw_ocr(screenshot, mt.matchTempletePointRange, text)
        self._save(screenshot)
```

- [ ] **Step 2: Commit**

```bash
git add jczx/debug/recorder.py
git commit -m "feat: add DebugRecorder with simple and annotated modes"
```

---

### Task 3: Add config + wire up in JczxCli

**Files:**
- Modify: `jczx/Config/Config.txt`
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: Add config entry**

Append to `jczx/Config/Config.txt`:

```
/ 调试截图模式: off=关闭 simple=连续截图 annotated=标注截图
debug.screenshot.mode : off
```

- [ ] **Step 2: Import DebugRecorder in jczxCli.py**

At the top of `jczx/jczxCli.py`, add import:

```python
from .debug import DebugRecorder
```

- [ ] **Step 3: Create DebugRecorder in JczxCli.__init__**

In `JczxCli.__init__`, after `self.ocr = None` (line 930), add:

```python
mode = self.config.get_config(opt="debug.screenshot.mode") or "off"
debug_dir = os.path.join(os.getcwd(), "screenHistory")
self._debug_recorder = DebugRecorder(mode, debug_dir, self.logger)
self._debug_recorder.ensure_dir()
```

Requires `import os` at top of file (already imported via `os.getcwd` usage elsewhere).

- [ ] **Step 4: Inject recorder into device in _init_device**

In `JczxCli._init_device`, after `self.logger.info(f"ADB加载完成 {self.device.device_id}")` (line 1012), add:

```python
self.device._recorder = self._debug_recorder
```

(Place this right after the `set_ocr` line we added earlier.)

- [ ] **Step 5: Commit**

```bash
git add jczx/Config/Config.txt jczx/jczx/jczxCli.py
git commit -m "feat: wire DebugRecorder into JczxCli and Config.txt"
```

---

### Task 4: Add hooks in JCZXGaming — click, swipe, dragAndDrop

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: Add `_recorder` field to JCZXGaming**

In `JCZXGaming.__init__`, after `self._screen_cache = ScreenshotCache(...)` (line 339), add:

```python
self._recorder = None
```

- [ ] **Step 2: Add hook in JCZXGaming.click**

Replace the `click` method (lines 351-353):

```python
def click(self, x, y):
    if self._recorder:
        self._recorder.on_click(self.screenshot(), x, y)
    super().click(x, y)
    self._screen_cache.invalidate()
```

- [ ] **Step 3: Add hook in JCZXGaming.swipe**

Replace the `swipe` method (lines 355-357):

```python
def swipe(self, x1, y1, x2, y2, duration=200):
    if self._recorder:
        self._recorder.on_swipe(self.screenshot(), x1, y1, x2, y2, "滑动")
    super().swipe(x1, y1, x2, y2, duration)
    self._screen_cache.invalidate()
```

- [ ] **Step 4: Add hook in JCZXGaming.dragAndDrop**

Replace the `dragAndDrop` method (lines 359-361):

```python
def dragAndDrop(self, x1, y1, x2, y2, duration=200):
    if self._recorder:
        self._recorder.on_swipe(self.screenshot(), x1, y1, x2, y2, "拖动")
    super().dragAndDrop(x1, y1, x2, y2, duration)
    self._screen_cache.invalidate()
```

- [ ] **Step 5: Commit**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add debug recorder hooks to click/swipe/dragAndDrop"
```

---

### Task 5: Add hooks in exec methods — _exec_entity, exec_match, exec_ocr

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: Add on_step hook in _exec_entity**

In `_exec_entity`, after `self._exec_mgr.token.sleep(self._resolve_scalar(entity, "pre_sleep"))` (line 633), add:

```python
if self._recorder:
    self._recorder.on_step(self.screenshot())
```

- [ ] **Step 2: Add on_match hook in exec_match._on_exec**

In `exec_match`, inside `_on_exec` (around line 412), after `if not result or not result.matched: self.log.debug(...); return None`, and BEFORE the transform loop, add:

```python
self._recorder.on_match(self.screenshot(), result)
```

Place it between the `result.matched` check and the `for action in e.action:` loop. So the screenshot is taken before transforms modify the coordinates.

- [ ] **Step 3: Add on_ocr hook in exec_ocr._on_exec**

In `exec_ocr._on_exec` (around line 440), after OCR result is obtained (both `match` and `target` paths produce a result), add at the end of `_on_exec` before `return result`:

```python
if result:
    self._recorder.on_ocr(self.screenshot(), mt, result)
```

Make `mt` available in the outer scope of `_on_exec` by declaring `mt = None` at the top of the closure.

- [ ] **Step 4: Commit**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add debug recorder hooks to _exec_entity, exec_match, exec_ocr"
```

---

### Task 6: Verify — import and syntax check

**Files:**
- No code changes, verification only.

- [ ] **Step 1: Python syntax check**

```bash
python -c "from jczx.debug import DebugRecorder, ScreenAnnotator; print('import OK')"
```

- [ ] **Step 2: Verify Config.txt has entry**

```bash
python -c "from jczx.CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import Config; c=Config('jczx/Config/Config.txt').Config; print(c.get_config(opt='debug.screenshot.mode'))"
```

Expected: `off`
