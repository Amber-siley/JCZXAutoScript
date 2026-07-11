# 任务执行生命周期重构 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 `CancellationToken` + `TaskExecutionManager` 替代 polling 式的 `stop_event` 检查，使任务启动/停止更精准、即时、可维护。

**Architecture:** 新增两个类（`TaskCancelledError`、`CancellationToken`、`TaskExecutionManager`）插入 `jczxCli.py` 顶部，替换 `JCZXGaming` 中全部 `stop_event` 引用和 `JczxCli` 中 `_running_task_id` / `_stop_running_task` / `_run_task` 逻辑。

**Tech Stack:** Python 3.14, `threading.Event`

**Spec:** `docs/superpowers/specs/2026-07-04-task-execution-lifecycle-design.md`

---

## File Changes

| 文件 | 操作 |
|------|------|
| `jczx/jczx/jczxCli.py` | 新增 3 个类 + 修改 7 处 stop_event 引用 + 修改 5 处 JczxCli 方法 |

---

### Task 1: 新增 TaskCancelledError + CancellationToken + TaskExecutionManager 三个类

**Files:**
- Modify: `jczx/jczx/jczxCli.py` (插入在 `JCZXGaming` 类定义之前)

- [ ] **Step 1: 在 `jczxCli.py` 顶部 `JCZXGaming` 类之前插入三个新类**

定位到 `class JCZXGaming(Device, JCZXGamingTaskFunc):` 所在行（约 L73）。在它上方插入以下代码：

```python
class TaskCancelledError(Exception):
    pass


class CancellationToken:
    def __init__(self):
        self._event = threading.Event()

    def sleep(self, seconds: float) -> None:
        if self._event.wait(timeout=seconds):
            raise TaskCancelledError()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise TaskCancelledError()


class TaskExecutionManager:
    def __init__(self):
        self._token = CancellationToken()
        self._task_id: str | None = None

    @property
    def token(self) -> CancellationToken:
        return self._token

    @property
    def task_id(self) -> str | None:
        return self._task_id

    def is_running(self) -> bool:
        return self._task_id is not None and not self._token.is_cancelled()

    def start(self, task_id: str) -> None:
        self._token.reset()
        self._task_id = task_id

    def stop(self) -> None:
        if not self._token.is_cancelled():
            self._token.cancel()

    def reset(self) -> None:
        self._token.reset()
        self._task_id = None
```

- [ ] **Step 2: 提交**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add CancellationToken and TaskExecutionManager classes"
```

---

### Task 2: JCZXGaming 替换 stop_event → _exec_mgr

**Files:**
- Modify: `jczx/jczx/jczxCli.py` — JCZXGaming.__init__ (L87) + 7 处 stop_event 引用

- [ ] **Step 1: `__init__` 中将 `self.stop_event = threading.Event()` 替换为 `self._exec_mgr = TaskExecutionManager()`**

```python
# 旧 (L87)
self.stop_event = threading.Event()
# 新
self._exec_mgr = TaskExecutionManager()
```

- [ ] **Step 2: `exec()` 入口 (L741) — `stop_event.is_set()` → `token.check()`**

```python
# 旧
if self.stop_event.is_set():
    return None
# 新
self._exec_mgr.token.check()
```

- [ ] **Step 3: `exec_dynamic()` (L413) — `stop_event.is_set()` → `token.check()`**

```python
# 旧
if self.stop_event.is_set(): return None
# 新
self._exec_mgr.token.check()
```

- [ ] **Step 4: `exec_click()` 内部 while 循环 (L494) — `stop_event.is_set()` → `token.check()`**

```python
# 旧
if self.stop_event.is_set(): return None
# 新
self._exec_mgr.token.check()
```

- [ ] **Step 5: `exec_task()` 内部 for 循环 (L538-540) — `stop_event.is_set()` → `token.check()`**

```python
# 旧
if self.stop_event.is_set():
    log_fn(f"{prefix}已被用户停止")
    return None
# 新
self._exec_mgr.token.check()
```

- [ ] **Step 6: `_exec_entity()` 循环内 (L558-559) — `stop_event.is_set()` → `token.check()`**

```python
# 旧
if self.stop_event.is_set():
    return None
# 新
self._exec_mgr.token.check()
```

- [ ] **Step 7: `_wait_for_image()` (L782) — `while not self.stop_event.is_set()` → `token.check()` + `token.sleep()`**

```python
# 旧 (L779-788)
def _wait_for_image(self, img, max_wait: int, per: float = 0.8) -> bool:
    start = time.monotonic()
    while not self.stop_event.is_set():
        if self.findImageCenterLocations(img, per=per):
            return True
        if max_wait > 0 and time.monotonic() - start >= max_wait:
            break
        time.sleep(0.3)
    return False
# 新
def _wait_for_image(self, img, max_wait: int, per: float = 0.8) -> bool:
    start = time.monotonic()
    while True:
        self._exec_mgr.token.check()
        if self.findImageCenterLocations(img, per=per):
            return True
        if max_wait > 0 and time.monotonic() - start >= max_wait:
            break
        self._exec_mgr.token.sleep(0.3)
    return False
```

- [ ] **Step 8: 替换所有普通 `time.sleep(x)` → `self._exec_mgr.token.sleep(x)`**

用 grep 确认所有 `time.sleep(` 调用位置（排除 pass 掉的 `_wait_for_image` 中已改的）：

搜索确认后，将以下位置替换：
- `_exec_entity` 中 L565: `time.sleep(entity.testFor_pre_sleep)` → `self._exec_mgr.token.sleep(entity.testFor_pre_sleep)`
- `_exec_entity` 中 L571: `time.sleep(entity.testFor_sleep)` → `self._exec_mgr.token.sleep(entity.testFor_sleep)`
- `_exec_entity` 中 L573: `time.sleep(entity.pre_sleep)` → `self._exec_mgr.token.sleep(entity.pre_sleep)`
- `_exec_entity` 中 L576: `time.sleep(entity.sleep)` → `self._exec_mgr.token.sleep(entity.sleep)`
- `exec_click` L521: `time.sleep(e.sleep)` → `self._exec_mgr.token.sleep(e.sleep)`

- [ ] **Step 9: 提交**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "refactor: replace stop_event with _exec_mgr in JCZXGaming"
```

---

### Task 3: JczxCli 集成 — _start_task / _stop_running_task / _run_task / _on_task_finished

**Files:**
- Modify: `jczx/jczx/jczxCli.py` — JczxCli 类内部

- [ ] **Step 1: 添加 `_running_task_id` 属性委托给 exec_mgr**

在 `JczxCli` 类中，将 `self._running_task_id: Optional[str] = None` (L887) 替换为属性：

```python
# 删除 L887 的
self._running_task_id: Optional[str] = None

# 在 JczxCli 类中新增 property
@property
def _running_task_id(self) -> str | None:
    return self.device._exec_mgr.task_id if self.device else None
```

- [ ] **Step 2: `_start_task()` 替换 stop_event.clear() + 手动赋值**

```python
# 旧 (L1110-1125)
def _start_task(self, task_id: str) -> bool:
    if not self.device:
        self.logger.warning("设备未就绪，无法启动任务")
        return False
    if not self.ocr:
        self.logger.warning("OCR 未初始化完成，无法启动任务")
        return False
    entity = self.task_manage.get_task(task_id)
    if not entity:
        self.logger.error("任务实体不存在: %s", task_id)
        return False
    self.device.stop_event.clear()
    self._running_task_id = task_id
    self.logger.info("任务启动: %s", entity.get_task_name())
    self._running_future = self.executor.submit(self._run_task, entity, task_id)
    return True
# 新
def _start_task(self, task_id: str) -> bool:
    if not self.device:
        self.logger.warning("设备未就绪，无法启动任务")
        return False
    if not self.ocr:
        self.logger.warning("OCR 未初始化完成，无法启动任务")
        return False
    entity = self.task_manage.get_task(task_id)
    if not entity:
        self.logger.error("任务实体不存在: %s", task_id)
        return False
    self.device._exec_mgr.start(task_id)
    self.logger.info("任务启动: %s", entity.get_task_name())
    self._running_future = self.executor.submit(self._run_task, entity, task_id)
    return True
```

- [ ] **Step 3: `_stop_running_task()` 替换 stop_event.set() + future.cancel()**

```python
# 旧 (L1127-1134)
def _stop_running_task(self) -> None:
    if self.device:
        self.device.stop_event.set()
    if self._running_future:
        self._running_future.cancel()
        self._running_future = None
    self._running_task_id = None
    self.logger.info("任务已停止")
# 新
def _stop_running_task(self) -> None:
    if self.device:
        self.device._exec_mgr.stop()
    self.logger.info("任务已停止")
```

- [ ] **Step 4: `_run_task()` 增加 TaskCancelledError 捕获**

```python
# 旧 (L1136-1142)
def _run_task(self, entity: JczxSectionEntity, task_id: str) -> None:
    try:
        self.device.exec_task_raw(entity)
    except Exception as e:
        self.logger.error("任务执行异常: %s", e)
    finally:
        self.call_from_thread(self._on_task_finished, task_id)
# 新
def _run_task(self, entity: JczxSectionEntity, task_id: str) -> None:
    try:
        self.device.exec_task_raw(entity)
    except TaskCancelledError:
        self.logger.info("任务已取消: %s", entity.get_task_name())
    except Exception as e:
        self.logger.error("任务执行异常: %s", e)
    finally:
        self.call_from_thread(self._on_task_finished, task_id)
```

- [ ] **Step 5: `_on_task_finished()` 替换手动清理 → exec_mgr.reset()**

```python
# 旧 (L1144-1152)
def _on_task_finished(self, task_id: str) -> None:
    if self._running_task_id != task_id:
        return
    panel = self.query_one("#task-list-panel", TaskListPanel)
    for card in panel.body.query(TaskCard):
        if card._task_id == task_id:
            card.reset_toggle()
    self._running_future = None
    self._running_task_id = None
# 新
def _on_task_finished(self, task_id: str) -> None:
    if self.device and self.device._exec_mgr.task_id != task_id:
        return
    if self.device:
        self.device._exec_mgr.reset()
    panel = self.query_one("#task-list-panel", TaskListPanel)
    for card in panel.body.query(TaskCard):
        if card._task_id == task_id:
            card.reset_toggle()
    self._running_future = None
```

- [ ] **Step 6: `_stop_running_task` 中移除 `_running_future` 和 `_running_task_id` 的直接操作**

确认 `_running_future` 只在 `_start_task` 赋值、`_on_task_finished` 清空，`_stop_running_task` 不再碰它。

- [ ] **Step 7: 提交**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "refactor: integrate TaskExecutionManager into JczxCli lifecycle"
```

---

### Task 4: 验证 — 手动运行确认停止功能

- [ ] **Step 1: 启动 TUI**

```powershell
.\venv\Scripts\activate
python -m jczx.jczxCli
```

- [ ] **Step 2: 验证正常启动任务**

选择一个任务，点击 Toggle 启动。确认：
- 日志显示 "任务启动: xxx"
- 任务开始执行
- 无 `TaskCancelledError` 异常

- [ ] **Step 3: 验证立即停止**

任务执行期间再次点击 Toggle 关闭。确认：
- 日志显示 "任务已取消: xxx" 或 "任务已停止"
- Toggle 复位 OFF
- UI 无异常
- 耗时操作被立即中断（不会继续 sleep 到结束）

- [ ] **Step 4: 验证停止后再启动**

再次点击同一个或不同任务的 Toggle。确认：
- 新任务正常启动
- 无残留 cancel 状态导致立即中断

- [ ] **Step 5: 验证幂等停止**

快速单击 Toggle 2-3 次。确认不报错、不崩溃。
