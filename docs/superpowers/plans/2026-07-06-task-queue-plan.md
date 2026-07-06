# 任务队列系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TUI 右侧 `TaskEditorPanel` 替换为任务队列系统——创建、编辑、保存有序队列，顺序执行，支持取消和进度显示，与单任务执行互斥。

**Architecture:** `QueuePanel`(Section) 替换 `TaskEditorPanel`，`QueueEditorScreen`(全屏 Screen) 提供队列编辑，`QueueEntity`(dataclass) 定义数据模型，`TaskManage` 新增队列持久化方法。队列执行复用 `exec_task_raw`，取消通过已有 `CancellationToken`。

**Tech Stack:** Textual TUI, existing `TxtConfig`/`Device`/`CancellationToken` infrastructure

**Files:** 1 new (`Queues.txt`), 4 modified (`widgets.py`, `jczxCli.py`, `taskManage.py`, `main.tcss`)

---

### Task 1: Create sample Queues.txt + QueueEntity dataclass

**Files:**
- Create: `jczx/Config/Queues.txt`
- Modify: `jczx/jczx/taskManage.py`

- [ ] **Step 1: Create Queues.txt**

Write `jczx/Config/Queues.txt`:

```ini
/ 任务队列配置
/ [队列id]  section 名即队列 ID（建议 queue- 前缀）
/ name: 显示名称
/ tasks: 逗号分隔的任务 entity key，按顺序执行，允许重复

[queue-daily]
name: 日常
tasks: jjc, inllusion, screenshot-task

[queue-weekly]
name: 周常
tasks: jjc, inllusion
```

- [ ] **Step 2: Add QueueEntity dataclass to taskManage.py**

At the top of `taskManage.py`, after existing imports, add:

```python
from dataclasses import dataclass

@dataclass
class QueueEntity:
    id: str
    name: str
    tasks: list[str]
```

- [ ] **Step 3: Commit**

```bash
git add jczx/Config/Queues.txt jczx/jczx/taskManage.py
git commit -m "feat: add QueueEntity dataclass and sample Queues.txt"
```

---

### Task 2: Add queue CRUD methods to TaskManage

**Files:**
- Modify: `jczx/jczx/taskManage.py`

- [ ] **Step 1: Add queue_config initialization**

In `TaskManage.__init__`, after `self.menu_config: TxtConfig = None`, add:

```python
self.queue_config_path = None
self.queue_config: TxtConfig = None
```

In `TaskManage.ready_env()`, after the menu_config initialization block, add:

```python
self.queue_config_path = self.fm.join(self.config_dir, "Queues.txt", seq="\\")
if not self.fm.isfile(self.queue_config_path):
    queue_config_path = self.fm.join_p("Config", "Queues.txt")
    self.fm.cp(queue_config_path, self.queue_config_path)
self.queue_config = Config(self.queue_config_path).Config
self._queue_cache: dict[str, QueueEntity] = {}
self.load_queues()
```

- [ ] **Step 2: Add load_queues method**

```python
def load_queues(self) -> None:
    self._queue_cache.clear()
    configs = self.queue_config.trans_entity_dict(JczxSectionEntity)
    for key, entity in configs.items():
        tasks_str = getattr(entity, 'tasks', '')
        task_list = [t.strip() for t in tasks_str.split(",") if t.strip()] if isinstance(tasks_str, str) else []
        name = getattr(entity, 'name', None) or key
        self._queue_cache[key] = QueueEntity(id=key, name=name, tasks=task_list)
    self.log.debug(f"加载 {len(self._queue_cache)} 个队列")
```

- [ ] **Step 3: Add get_queues, get_queue**

```python
def get_queues(self) -> list[QueueEntity]:
    return list(self._queue_cache.values())

def get_queue(self, queue_id: str) -> QueueEntity | None:
    return self._queue_cache.get(queue_id)
```

- [ ] **Step 4: Add save_queue method**

```python
def save_queue(self, queue_id: str, name: str, tasks: list[str]) -> None:
    self.queue_config.set_config(queue_id, "name", name)
    self.queue_config.set_config(queue_id, "tasks", ",".join(tasks))
    self.queue_config.save()
    self._queue_cache[queue_id] = QueueEntity(id=queue_id, name=name, tasks=tasks)
    self.log.debug(f"队列 {queue_id} 已保存")
```

- [ ] **Step 5: Add delete_queue method**

```python
def delete_queue(self, queue_id: str) -> None:
    if queue_id not in self._queue_cache:
        return
    sec_data = self.queue_config.get_section(queue_id)
    for opt in list(sec_data.keys()):
        self.queue_config.remove_config(queue_id, opt)
    self.queue_config.save()
    del self._queue_cache[queue_id]
    self.log.debug(f"队列 {queue_id} 已删除")
```

- [ ] **Step 6: Update refresh_config to reload queues**

In `TaskManage.refresh_config()`, add `self.load_queues()` at the end of the method body.

- [ ] **Step 7: Commit**

```bash
git add jczx/jczx/taskManage.py
git commit -m "feat: add queue CRUD methods to TaskManage"
```

---

### Task 3: Add QueuePanel widget (replaces TaskEditorPanel)

**Files:**
- Modify: `jczx/jczx/widgets.py`

- [ ] **Step 1: Replace TaskEditorPanel with QueuePanel**

Remove the entire `TaskEditorPanel` class (lines 624-679) and replace with `QueuePanel`:

```python
class QueuePanel(Section):
    """Task queue panel: select queue, start/stop, progress, create/edit."""

    class RunRequested(Message):
        def __init__(self, queue_id: str, running: bool) -> None:
            self.queue_id = queue_id
            self.running = running
            super().__init__()

    class EditRequested(Message):
        def __init__(self, queue_id: str | None) -> None:
            self.queue_id = queue_id
            super().__init__()

    def __init__(self, queues: list[tuple[str, str]] | None = None, id: str | None = None):
        super().__init__("任务队列", id=id)
        self._opts = [("-- 无队列 --", "")] + (queues or [])

    def on_mount(self) -> None:
        self.body.mount(Label("队列:", classes="field-label"))
        self.body.mount(CompactSelect(self._opts, id="queue-select"))
        self.body.mount(
            ToggleButton(label_off="开始执行", label_on="停止执行", id="queue-toggle", disabled=True)
        )
        self.body.mount(LabelButton("新建队列", id="queue-new"))
        self.body.mount(LabelButton("编辑队列", id="queue-edit", disabled=True))

    def on_compact_select_changed(self, event: CompactSelect.Changed) -> None:
        if event.control_id != "queue-select":
            return
        has_queue = bool(event.value)
        self.query_one("#queue-toggle", ToggleButton).disabled = not has_queue
        self.query_one("#queue-edit", LabelButton).disabled = not has_queue

    def on_toggle_button_toggled(self, event: ToggleButton.Toggled) -> None:
        event.stop()
        select = self.query_one("#queue-select", CompactSelect)
        self.post_message(self.RunRequested(select.value, event.state))

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        if event.control_id == "queue-new":
            self.post_message(self.EditRequested(None))
        elif event.control_id == "queue-edit":
            select = self.query_one("#queue-select", CompactSelect)
            self.post_message(self.EditRequested(select.value or None))

    def set_queues(self, queues: list[tuple[str, str]]) -> None:
        opts = [("-- 无队列 --", "")] + queues
        w = self.query_one("#queue-select", CompactSelect)
        w.set_options(opts)
        w.value = ""

    def select_queue(self, queue_id: str) -> None:
        w = self.query_one("#queue-select", CompactSelect)
        w.value = queue_id

    def update_progress(self, name: str, idx: int, total: int, task_name: str) -> None:
        self.body.query(".queue-progress").remove()
        self.body.mount(Label(f"{name} → {idx + 1}/{total} {task_name}", classes="queue-progress"))

    def clear_progress(self) -> None:
        self.body.query(".queue-progress").remove()

    @property
    def toggle(self) -> ToggleButton:
        return self.query_one("#queue-toggle", ToggleButton)

    def reset_toggle(self) -> None:
        self.toggle.reset()
```

- [ ] **Step 2: Commit**

```bash
git add jczx/jczx/widgets.py
git commit -m "feat: replace TaskEditorPanel with QueuePanel"
```

---

### Task 4: Add ConfirmDialog widget

**Files:**
- Modify: `jczx/jczx/widgets.py`

- [ ] **Step 1: Add _ConfirmDialog class**

At the end of `widgets.py`, add:

```python
class _ConfirmDialog(Screen):
    """Simple yes/no confirmation dialog overlay."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message
        self.result = False

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Label(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield LabelButton("确认", id="confirm-yes")
                yield LabelButton("取消", id="confirm-no")

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        if event.control_id == "confirm-yes":
            self.result = True
        self.dismiss(self.result)
```

- [ ] **Step 2: Commit**

```bash
git add jczx/jczx/widgets.py
git commit -m "feat: add ConfirmDialog overlay"
```

---

### Task 5: Add QueueEditorScreen widgets

**Files:**
- Modify: `jczx/jczx/widgets.py`

- [ ] **Step 1: Add AvailableTasksPanel and QueueTasksPanel**

After `_ConfirmDialog`, add:

```python
class _AvailableTaskRow(Horizontal):
    class AddRequested(Message):
        def __init__(self, task_key: str) -> None:
            self.task_key = task_key
            super().__init__()

    def __init__(self, task_key: str, task_name: str):
        super().__init__()
        self._task_key = task_key
        self._task_name = task_name

    def compose(self) -> ComposeResult:
        yield Label(self._task_name, classes="editor-task-name")
        yield LabelButton("[+]", id=f"add-{self._task_key}")

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        self.post_message(self.AddRequested(self._task_key))


class _QueueTaskRow(Horizontal):
    class ActionRequested(Message):
        def __init__(self, index: int, action: str) -> None:
            self.index = index
            self.action = action
            super().__init__()

    def __init__(self, index: int, task_name: str, is_first: bool, is_last: bool):
        super().__init__()
        self._index = index
        self._task_name = task_name
        self._is_first = is_first
        self._is_last = is_last

    def compose(self) -> ComposeResult:
        yield Label(f"{self._index + 1}. {self._task_name}", classes="editor-task-name")
        yield LabelButton("↑", id=f"up-{self._index}", disabled=self._is_first)
        yield LabelButton("↓", id=f"down-{self._index}", disabled=self._is_last)
        yield LabelButton("✕", id=f"del-{self._index}")

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        cid = event.control_id or ""
        if cid.startswith("up-"):
            self.post_message(self.ActionRequested(self._index, "up"))
        elif cid.startswith("down-"):
            self.post_message(self.ActionRequested(self._index, "down"))
        elif cid.startswith("del-"):
            self.post_message(self.ActionRequested(self._index, "delete"))
```

- [ ] **Step 2: Commit**

```bash
git add jczx/jczx/widgets.py
git commit -m "feat: add queue editor row widgets"
```

---

### Task 6: Add QueueEditorScreen

**Files:**
- Modify: `jczx/jczx/widgets.py`

- [ ] **Step 1: Add QueueEditorScreen class**

After the row widgets, add:

```python
class QueueEditorScreen(Screen):
    """Full-screen queue editor."""

    BINDINGS = [
        Binding("escape", "cancel", "取消"),
        Binding("ctrl+s", "save", "保存"),
        Binding("ctrl+up", "move_up", "上移"),
        Binding("ctrl+down", "move_down", "下移"),
    ]

    def __init__(self, queue_id: str | None, queue_name: str, tasks: list[str],
                 available_tasks: list[tuple[str, str]]):
        super().__init__()
        self._queue_id = queue_id
        self._queue_name = queue_name
        self._queue_tasks: list[tuple[str, str]] = tasks  # [(key, display_name), ...]
        self._available = available_tasks  # [(key, display_name), ...]

    def compose(self) -> ComposeResult:
        title = f"编辑队列: {self._queue_name}" if self._queue_name else "新建队列"
        yield Header(show_clock=False)
        yield Label(title, id="editor-title")
        with Horizontal(id="editor-columns"):
            with Section("可用任务", id="available-panel"):
                pass
            with Section("队列任务", id="queue-tasks-panel"):
                pass
        with Horizontal(id="editor-bottom"):
            yield Input(placeholder="队列名称", value=self._queue_name, id="queue-name-input")
            yield LabelButton("保存", id="editor-save")
            yield LabelButton("取消", id="editor-cancel")
            if self._queue_id:
                yield LabelButton("删除队列", id="editor-delete")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self._refresh_available()
        self._refresh_queue_tasks()

    def _refresh_available(self) -> None:
        panel = self.query_one("#available-panel", Section)
        panel.body.remove_children()
        for key, name in self._available:
            row = _AvailableTaskRow(key, name)
            panel.body.mount(row)

    def _refresh_queue_tasks(self) -> None:
        panel = self.query_one("#queue-tasks-panel", Section)
        panel.body.remove_children()
        n = len(self._queue_tasks)
        for i, (key, name) in enumerate(self._queue_tasks):
            row = _QueueTaskRow(i, name, is_first=(i == 0), is_last=(i == n - 1))
            panel.body.mount(row)

    def on_available_task_row_add_requested(self, event: _AvailableTaskRow.AddRequested) -> None:
        event.stop()
        key = event.task_key
        name = next((n for k, n in self._available if k == key), key)
        self._queue_tasks.append((key, name))
        self._refresh_queue_tasks()

    def on_queue_task_row_action_requested(self, event: _QueueTaskRow.ActionRequested) -> None:
        event.stop()
        idx = event.index
        if event.action == "up" and idx > 0:
            self._queue_tasks[idx], self._queue_tasks[idx - 1] = self._queue_tasks[idx - 1], self._queue_tasks[idx]
        elif event.action == "down" and idx < len(self._queue_tasks) - 1:
            self._queue_tasks[idx], self._queue_tasks[idx + 1] = self._queue_tasks[idx + 1], self._queue_tasks[idx]
        elif event.action == "delete":
            del self._queue_tasks[idx]
        self._refresh_queue_tasks()

    def action_move_up(self) -> None:
        focused = self.focused
        if isinstance(focused, _QueueTaskRow) and focused._index > 0:
            idx = focused._index
            self._queue_tasks[idx], self._queue_tasks[idx - 1] = self._queue_tasks[idx - 1], self._queue_tasks[idx]
            self._refresh_queue_tasks()

    def action_move_down(self) -> None:
        focused = self.focused
        if isinstance(focused, _QueueTaskRow) and focused._index < len(self._queue_tasks) - 1:
            idx = focused._index
            self._queue_tasks[idx], self._queue_tasks[idx + 1] = self._queue_tasks[idx + 1], self._queue_tasks[idx]
            self._refresh_queue_tasks()

    def action_cancel(self) -> None:
        self.dismiss(None)

    async def action_save(self) -> None:
        name_input = self.query_one("#queue-name-input", Input)
        name = name_input.value.strip()
        if not name:
            self.notify("队列名称不能为空", severity="warning")
            return
        result = {
            "name": name,
            "tasks": [k for k, _ in self._queue_tasks],
        }
        self.dismiss(result)

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        cid = event.control_id
        if cid == "editor-save":
            self.action_save()
        elif cid == "editor-cancel":
            self.action_cancel()
        elif cid == "editor-delete":
            self._confirm_delete()

    async def _confirm_delete(self) -> None:
        def callback(result: bool) -> None:
            if result:
                self.dismiss({"delete": True})
        self.app.push_screen(_ConfirmDialog("确认删除此队列？此操作不可撤销。"), callback=callback)
```

- [ ] **Step 2: Commit**

```bash
git add jczx/jczx/widgets.py
git commit -m "feat: add QueueEditorScreen"
```

---

### Task 7: Add CSS styles for queue widgets

**Files:**
- Modify: `jczx/jczx/Css/main.tcss`

- [ ] **Step 1: Append queue-related CSS**

After the last line of `main.tcss`, append:

```css
/* ═══════════════════════════════════════════════════
   QueuePanel
   ═══════════════════════════════════════════════════ */

#queue-select {
    width: 100%;
}

.queue-progress {
    height: 1;
    padding: 0 1;
    color: $text-muted;
    content-align: left middle;
}

/* ═══════════════════════════════════════════════════
   QueueEditorScreen
   ═══════════════════════════════════════════════════ */

QueueEditorScreen {
    align: center middle;
}

#editor-title {
    height: 1;
    padding: 0 1;
    text-style: bold;
    content-align: left middle;
}

#editor-columns {
    height: 1fr;
    padding: 0 1;
}

#editor-columns > Section {
    width: 1fr;
    margin: 0 1;
    border: solid $primary;
}

#editor-bottom {
    height: auto;
    padding: 0 1;
    margin: 1 0;
    align: center middle;
}

#editor-bottom Input {
    width: 20;
    height: 1;
    margin-right: 2;
    border: none;
    background: $surface;
}

#editor-bottom LabelButton {
    min-width: 8;
    margin-right: 1;
}

.editor-task-name {
    width: 1fr;
    content-align: left middle;
}

_AvailableTaskRow, _QueueTaskRow {
    height: 1;
    padding: 0 1;
    align: center middle;
}

_AvailableTaskRow > LabelButton, _QueueTaskRow > LabelButton {
    min-width: 4;
    margin: 0;
}

/* ═══════════════════════════════════════════════════
   ConfirmDialog
   ═══════════════════════════════════════════════════ */

#confirm-dialog {
    width: 40;
    height: auto;
    margin: 1 2;
    padding: 1 2;
    border: solid $error;
    background: $surface;
}

#confirm-message {
    width: 100%;
    content-align: center middle;
    padding: 1 0;
}

#confirm-buttons {
    width: 100%;
    height: auto;
    align: center middle;
    content-align: center middle;
}

#confirm-buttons LabelButton {
    min-width: 10;
    margin: 0 1;
}
```

- [ ] **Step 2: Commit**

```bash
git add jczx/jczx/Css/main.tcss
git commit -m "feat: add queue panel and editor CSS styles"
```

---

### Task 8: Wire up QueuePanel in JczxTUI (compose + refresh)

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: Update imports**

At the top of `jczxCli.py`, update the import line:

```python
# change:
from .widgets import TaskEditorPanel, ... (keep others)
# to:
from .widgets import QueuePanel, QueueEditorScreen, TaskListPanel, TaskSettingsPanel, ...
```

(Only replace `TaskEditorPanel` with `QueuePanel, QueueEditorScreen` in the existing import.)

- [ ] **Step 2: Replace TaskEditorPanel with QueuePanel in compose()**

In `JczxTUI.compose()`, replace:

```python
yield TaskEditorPanel(
    task_list_names=self._get_editor_task_options(),
    id="task-editor-panel",
)
```

with:

```python
yield QueuePanel(
    queues=self._get_queue_options(),
    id="queue-panel",
)
```

- [ ] **Step 3: Add _get_queue_options helper**

```python
def _get_queue_options(self) -> list[tuple[str, str]]:
    return [(q.name, q.id) for q in self.task_manage.get_queues()]
```

- [ ] **Step 4: Update _refresh_all_panels**

In `_refresh_all_panels`, replace the editor panel line:

```python
editor_panel = self.query_one("#task-editor-panel", TaskEditorPanel)
editor_panel.set_task_lists(self._get_editor_task_options())
```

with:

```python
queue_panel = self.query_one("#queue-panel", QueuePanel)
queue_panel.set_queues(self._get_queue_options())
```

- [ ] **Step 5: Commit**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: wire QueuePanel into JczxTUI compose"
```

---

### Task 9: Add exec_queue to JCZXGaming

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: Add exec_queue method**

In `JCZXGaming` class, after `exec_task_raw`, add:

```python
def exec_queue(self, queue_id: str) -> None:
    queue = self.task_manage.get_queue(queue_id)
    if not queue:
        self.log.warning(f"队列 {queue_id} 不存在")
        return
    tasks = queue.tasks
    n = len(tasks)
    self.log.info(f"开始执行队列 [{queue.name}]，共 {n} 个任务")
    for i, task_key in enumerate(tasks):
        self._exec_mgr.token.check()
        entity = self.task_manage.get_task(task_key)
        if entity is None:
            self.log.warning(f"队列任务 [{task_key}] 不存在，跳过")
            continue
        self.log.info(f"队列 [{queue.name}] {i + 1}/{n}: {entity.get_task_name()}")
        self.exec_task_raw(task_key)
    self.log.info(f"队列 [{queue.name}] 执行完毕")
```

- [ ] **Step 2: Commit**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add exec_queue method to JCZXGaming"
```

---

### Task 10: Add queue execution lifecycle to JczxTUI

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 0: Add _editing_queue_id to JczxTUI.__init__**

In `JczxTUI.__init__`, add:

```python
self._editing_queue_id: str | None = None
```

- [ ] **Step 1: Add queue-related message handlers**

In `JczxTUI`, replace the `on_task_editor_panel_run_requested` handler with:

```python
def on_queue_panel_run_requested(self, event: QueuePanel.RunRequested) -> None:
    if not getattr(self, '_initialized', False):
        self.logger.debug("初始化未完成，忽略队列操作")
        return
    if event.running:
        self._start_queue(event.queue_id)
    else:
        self._stop_running_task()

def on_queue_panel_edit_requested(self, event: QueuePanel.EditRequested) -> None:
    if not getattr(self, '_initialized', False):
        return
    self._editing_queue_id = event.queue_id
    if event.queue_id:
        queue = self.task_manage.get_queue(event.queue_id)
        name = queue.name if queue else ""
        tasks = [(k, self.task_manage.get_task_display_name(k)) for k in (queue.tasks if queue else [])]
    else:
        name = ""
        tasks = []
    available = [(k, self.task_manage.get_task_display_name(k)) for k in self._get_editor_task_names()]
    self.push_screen(
        QueueEditorScreen(event.queue_id, name, tasks, available),
        callback=self._on_queue_editor_closed,
    )

def _on_queue_editor_closed(self, result: dict | None) -> None:
    if result is None:
        return
    if result.get("delete"):
        queue_id = self._editing_queue_id
        self.task_manage.delete_queue(queue_id)
        self.logger.info("队列已删除: %s", queue_id)
        self._refresh_queue_panel()
        return
    name = result["name"]
    task_keys = result["tasks"]
    queue_id = self._editing_queue_id or f"queue-{name}"
    if self._editing_queue_id and not task_keys:
        self.logger.warning("队列任务列表为空，未保存")
        return
    self.task_manage.save_queue(queue_id, name, task_keys)
    self.logger.info("队列已保存: %s (%d 个任务)", name, len(task_keys))
    self._refresh_queue_panel()
    self.query_one("#queue-panel", QueuePanel).select_queue(queue_id)

def _refresh_queue_panel(self) -> None:
    panel = self.query_one("#queue-panel", QueuePanel)
    panel.set_queues(self._get_queue_options())
```

- [ ] **Step 2: Add _start_queue method + mutual exclusion**

```python
def _start_queue(self, queue_id: str) -> bool:
    if not self.device:
        self.logger.warning("设备未就绪，无法启动队列")
        return False
    if not self.ocr:
        self.logger.warning("OCR 未初始化完成，无法启动队列")
        return False
    if self.device._exec_mgr.is_running():
        self.logger.warning("已有任务/队列正在执行，请先停止")
        queue_panel = self.query_one("#queue-panel", QueuePanel)
        queue_panel.reset_toggle()
        return False
    queue = self.task_manage.get_queue(queue_id)
    if not queue:
        self.logger.error("队列不存在: %s", queue_id)
        return False
    self.device._exec_mgr.start(queue_id)
    self.logger.info("队列启动: %s", queue.name)
    self._running_future = self.executor.submit(self._run_queue, queue_id)
    return True

def _run_queue(self, queue_id: str) -> None:
    try:
        self.device.exec_queue(queue_id)
    except TaskCancelledError:
        self.logger.info("队列已取消: %s", queue_id)
    except Exception as e:
        self.logger.error("队列执行异常: %s", e)
    finally:
        self.call_from_thread(self._on_queue_finished, queue_id)

def _on_queue_finished(self, queue_id: str) -> None:
    if self.device and self.device._exec_mgr.task_id != queue_id:
        return
    if self.device:
        self.device._exec_mgr.reset()
    panel = self.query_one("#queue-panel", QueuePanel)
    panel.reset_toggle()
    panel.clear_progress()
    self._running_future = None
```

- [ ] **Step 3: Add mutual exclusion to _start_task**

In `_start_task`, add after the OCR check:

```python
if self.device._exec_mgr.is_running():
    self.logger.warning("已有任务/队列正在执行，请先停止")
    return False
```

- [ ] **Step 4: Update _stop_running_task to also reset queue panel**

```python
def _stop_running_task(self) -> None:
    if self.device:
        self.device._exec_mgr.stop()
    self.logger.info("任务已停止")
    try:
        panel = self.query_one("#queue-panel", QueuePanel)
        panel.clear_progress()
        panel.reset_toggle()
    except Exception:
        pass
```

- [ ] **Step 5: Commit**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add queue execution lifecycle and handlers"
```

---

### Task 11: Add queue progress to exec_queue

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: Update exec_queue with optional on_progress callback**

In `JCZXGaming`, replace the `exec_queue` from Task 9 with:

```python
def exec_queue(self, queue_id: str, on_progress=None) -> None:
    queue = self.task_manage.get_queue(queue_id)
    if not queue:
        self.log.warning(f"队列 {queue_id} 不存在")
        return
    tasks = queue.tasks
    n = len(tasks)
    self.log.info(f"开始执行队列 [{queue.name}]，共 {n} 个任务")
    for i, task_key in enumerate(tasks):
        self._exec_mgr.token.check()
        entity = self.task_manage.get_task(task_key)
        if entity is None:
            self.log.warning(f"队列任务 [{task_key}] 不存在，跳过")
            continue
        self.log.info(f"队列 [{queue.name}] {i + 1}/{n}: {entity.get_task_name()}")
        if on_progress:
            on_progress(queue.name, i, n, entity.get_task_name())
        self.exec_task_raw(task_key)
    self.log.info(f"队列 [{queue.name}] 执行完毕")
```

- [ ] **Step 2: Pass progress callback from _run_queue**

In `_run_queue` in `JczxTUI`, update to pass the progress callback:

```python
def _run_queue(self, queue_id: str) -> None:
    try:
        self.device.exec_queue(queue_id, on_progress=lambda name, i, n, tn:
            self.call_from_thread(self._on_queue_progress, name, i, n, tn))
    except TaskCancelledError:
        self.logger.info("队列已取消: %s", queue_id)
    except Exception as e:
        self.logger.error("队列执行异常: %s", e)
    finally:
        self.call_from_thread(self._on_queue_finished, queue_id)

def _on_queue_progress(self, name: str, idx: int, total: int, task_name: str) -> None:
    try:
        panel = self.query_one("#queue-panel", QueuePanel)
        panel.update_progress(name, idx, total, task_name)
    except Exception:
        pass
```

- [ ] **Step 3: Commit**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add queue progress via on_progress callback"<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="read">
<｜｜DSML｜｜parameter name="offset" string="false">13
