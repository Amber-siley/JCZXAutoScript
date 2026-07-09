# 调试截图可视化系统设计

## 概述

为 TUI 脚本执行添加可视化调试功能，支持两种模式：连续截图（simple）和标注截图（annotated）。通过 Config.txt 控制模式切换，对现有执行逻辑零副作用。

## 设计决策

| 决策 | 选项 | 理由 |
|------|------|------|
| 架构模式 | Recorder 对象注入 | 高内聚（调试逻辑集中），低耦合（Gaming 只需一行调用） |
| 模式控制 | 单键 `debug.screenshot.mode` | 简单，三态互斥 |
| 标注时机 | 点击/swipe前截图 | 操作后游戏画面已变化，操作前截图可准确标注操作位置 |
| 绘图库 | cv2 (OpenCV) | 项目已依赖，无需额外安装 |
| 颜色方案 | 绿色 (0,255,0) BGR | 白色/深色背景上清晰可见 |
| 索引编号 | 全局自增，从 1 开始 | 两种模式共享计数器，保证文件名顺序 |

## 配置

### Config.txt

```
/ 调试截图模式: off=关闭 simple=连续截图 annotated=标注截图
debug.screenshot.mode : off
```

- `off`：不执行任何调试截图
- `simple`：每个实体执行步骤前保存当前截图到 `screenHistory/N.png`
- `annotated`：仅在匹配/点击/滑动/拖动/OCR 时保存标注后的截图

## 架构

### 文件结构

```
jczx/debug/                   （新建 package）
├── __init__.py
├── recorder.py               DebugRecorder — 模式管理、索引、保存
└── annotator.py              ScreenAnnotator — cv2 绘图
```

### 类图

```
┌─────────────────┐         ┌─────────────────────┐
│   JCZXGaming    │         │    DebugRecorder     │
│─────────────────│         │─────────────────────│
│ + _recorder ────│────────>│ - _mode: str         │
│                 │ 引用     │ - _output_dir: str   │
└─────────────────┘         │ - _index: int        │
                            │ - _log: Logger       │
                            │ - _annotator: Annotator│
                            │─────────────────────│
                            │ + ensure_dir(): void │
                            │ + on_step(img)       │
                            │ + on_match(img, mt)  │
                            │ + on_click(img,x,y)  │
                            │ + on_swipe(img,...)  │
                            │ + on_ocr(img,mt,txt) │
                            └────────┬────────────┘
                                     │ 委托绘图
                            ┌────────┴────────────┐
                            │   ScreenAnnotator   │
                            │─────────────────────│
                            │ + draw_match(img,mt,idx)│
                            │ + draw_click(img,x,y)   │
                            │ + draw_swipe(img,x1,y1,x2,y2,label) │
                            │ + draw_ocr(img,mt,text) │
                            └─────────────────────┘
```

### `DebugRecorder`

**职责**：模式判断、索引管理、文件 I/O。绘图委托给 `ScreenAnnotator`。

```python
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
        """创建输出目录，若存在则清空。"""
        ...

    def _save(self, img: ndarray):
        path = f"{self._output_dir}/{self._index}.png"
        cv2.imwrite(path, img)
        self._log.debug(f"调试截图 #{self._index} 已保存")
        self._index += 1

    # ── 对外接口 ──

    def on_step(self, screenshot: ndarray):
        """模式1：每步保存截图"""
        if self._mode == self.MODE_SIMPLE:
            self._save(screenshot)

    def on_match(self, screenshot: ndarray, mt: MatchTemplete):
        """模式2：匹配成功时框选所有目标"""
        if self._mode != self.MODE_ANNOTATED or not mt.matched:
            return
        for idx, pts in enumerate(mt.matchTempletePoints):
            self._annotator.draw_match(screenshot, pts, idx)
        self._save(screenshot)

    def on_click(self, screenshot: ndarray, x: int, y: int):
        """模式2：标注点击位置"""
        if self._mode != self.MODE_ANNOTATED:
            return
        self._annotator.draw_click(screenshot, x, y)
        self._save(screenshot)

    def on_swipe(self, screenshot: ndarray, x1, y1, x2, y2, label: str):
        """模式2：标注滑动/拖动箭头"""
        if self._mode != self.MODE_ANNOTATED:
            return
        self._annotator.draw_swipe(screenshot, x1, y1, x2, y2, label)
        self._save(screenshot)

    def on_ocr(self, screenshot: ndarray, mt: MatchTemplete, text: str):
        """模式2：框选 OCR 识别区域并标注结果"""
        if self._mode != self.MODE_ANNOTATED or not mt.matched:
            return
        self._annotator.draw_ocr(screenshot, mt, text)
        self._save(screenshot)
```

### `ScreenAnnotator`

**职责**：纯 cv2 绘图，所有操作为无副作用的静态方法或工具方法。

```python
class ScreenAnnotator:
    COLOR = (0, 255, 0)       # BGR 绿色
    THICKNESS = 2
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE = 0.5

    @classmethod
    def _draw_label(cls, img, x, y, text):
        """在坐标旁边绘制小字标注"""
        cv2.putText(img, text, (x + 4, y - 4),
                    cls.FONT, cls.FONT_SCALE, cls.COLOR, 1)

    @classmethod
    def draw_click(cls, img, x, y):
        """点击点 + 十字标记 + '点击'"""
        cv2.drawMarker(img, (x, y), cls.COLOR, cv2.MARKER_CROSS, 10, cls.THICKNESS)
        cls._draw_label(img, x, y, "点击")

    @classmethod
    def draw_match(cls, img, pts, index):
        """矩形框 + '匹配:N'"""
        (x0, y0), (x1, _), (_, y1), (_, _) = pts
        cv2.rectangle(img, (x0, y0), (x1, y1), cls.COLOR, cls.THICKNESS)
        cls._draw_label(img, x0, y0, f"匹配:{index}")

    @classmethod
    def draw_swipe(cls, img, x1, y1, x2, y2, label):
        """箭头线 + 标签"""
        cv2.arrowedLine(img, (x1, y1), (x2, y2), cls.COLOR, cls.THICKNESS, tipLength=0.1)
        cls._draw_label(img, x1, y1, label)

    @classmethod
    def draw_ocr(cls, img, mt, text):
        """匹配区域矩形 + 'OCR: 结果'"""
        pt_range = mt.matchTempletePointRange
        if pt_range is None:
            return
        (x0, y0), (x1, y1) = pt_range
        cv2.rectangle(img, (x0, y0), (x1, y1), cls.COLOR, cls.THICKNESS)
        cls._draw_label(img, x0, y0, f"OCR: {text}")
```

## 调用注入点

### 创建与注入

```python
# JczxCli.__init__
mode = self.config.get_config(opt="debug.screenshot.mode") or "off"
dir = self.fm.join(os.getcwd(), "screenHistory")
self._debug_recorder = DebugRecorder(mode, dir, self.logger)
self._debug_recorder.ensure_dir()

# JczxCli._init_device → 设备创建后
self.device._recorder = self._debug_recorder
```

### JCZXGaming 中的 hook

只在 `_recorder is not None` 且 mode 非 off 时有开销：

| 方法 | 注入位置 | 代码 |
|------|----------|------|
| `_exec_entity` | `pre_sleep` 后 | `self._recorder.on_step(self.screenshot())` |
| `exec_match._on_exec` | `findImageDetail` 返回且 matched | `self._recorder.on_match(self.screenshot(), result)` |
| `exec_ocr._on_exec` | OCR 识别完成后 | `self._recorder.on_ocr(self.screenshot(), mt, result)` |
| `JCZXGaming.click` | `super().click(x, y)` **前** | `self._recorder.on_click(self.screenshot(), x, y)` |
| `JCZXGaming.swipe` | `super().swipe(...)` **前** | `self._recorder.on_swipe(self.screenshot(), x1,y1,x2,y2,"滑动")` |
| `JCZXGaming.dragAndDrop` | `super().dragAndDrop(...)` **前** | `self._recorder.on_swipe(self.screenshot(), x1,y1,x2,y2,"拖动")` |

> 点击/swipe/drag hook 在 `JCZXGaming` 重载方法中，自动覆盖所有调用路径（`exec_click` 的三种点击方式、func 类型中的 `click_proportion` 等）。match/OCR hook 在 exec 方法中，需要额外的上下文信息（匹配坐标列表、OCR 结果文本）。

> `self.screenshot()` 利用已有的 `ScreenshotCache`，在 TTL 内不额外截图。点击/swipe/drag 前调用会拿缓存中的上一次帧；操作后 `invalidate()` 被调用，下次截图会重新捕获。

## 启动流程

```
JczxCli.__init__
  → 读取 debug.screenshot.mode
  → new DebugRecorder(mode, "screenHistory/", log)
  → ensure_dir() → mkdir + 清空 # 每次启动重新开始索引
  → _init_device → device._recorder = recorder
```

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `jczx/debug/__init__.py` | **新建** |
| `jczx/debug/recorder.py` | **新建**，`DebugRecorder` |
| `jczx/debug/annotator.py` | **新建**，`ScreenAnnotator` |
| `jczx/Config/Config.txt` | 新增 `debug.screenshot.mode` 配置项 |
| `jczx/jczxCli.py` | `JczxCli.__init__` 创建 Recorder；`_init_device` 注入到 device；6 处 hook 调用 |

## 不在范围内

- 视频生成（用户自行用 ffmpeg 将 PNG 序列合成）
- 标注颜色的自定义（固定绿色方案）
- WebUI / TUI 中的调试开关（仅通过 Config.txt 控制，需重启生效）

## 注意事项

- `screenHistory/` 目录每次启动清空，避免磁盘膨胀
- `off` 模式下所有 `on_xxx` 调用立即返回，开销为一次属性访问 + if 判断
- 标注截图使用 cv2 直接修改 ndarray（原地修改），确保 `_save` 在标注完成后调用
