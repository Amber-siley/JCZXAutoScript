"""Reusable TUI widgets for the JCZX AutoScript Textual app.

Provides composable building blocks: toggle buttons, collapsible sections,
task cards, device bar, settings forms, and task editor panels.
"""

from dataclasses import dataclass, field

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.binding import Binding
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static
from textual.validation import Integer

# ═══════════════════════════════════════════════════════════
# CompactSwitch — single-line boolean toggle
# ═══════════════════════════════════════════════════════════

class CompactSwitch(Static, can_focus=True):
    """Single-line toggle rendering ``[X]`` / ``[ ]`` at height 1."""

    class Changed(Message):
        """Emitted when toggled."""

        def __init__(self, value: bool, sender_id: str) -> None:
            self.value = value
            self.sender_id = sender_id
            super().__init__()

    value: reactive[bool] = reactive(False, init=False)

    def __init__(self, value: bool = False, id: str | None = None) -> None:
        super().__init__(id=id)
        self.value = value

    def render(self) -> str:
        return "\\[X]" if self.value else "\\[ ]"

    def on_click(self) -> None:
        self.value = not self.value
        self.post_message(self.Changed(self.value, str(self.id)))

# ═══════════════════════════════════════════════════════════
# ToggleButton
# ═══════════════════════════════════════════════════════════

class ToggleButton(Static, can_focus=True):
    """Start / stop toggle that renders as a coloured label.

    Clicks toggle ``state`` (False→True / True→False) and post a
    :class:`Toggled` message so parent containers can react.
    """

    class Toggled(Message):
        """Emitted when the button is clicked."""

        def __init__(self, sender_id: str, state: bool) -> None:
            self.sender_id = sender_id
            self.state = state
            super().__init__()

    state: reactive[bool] = reactive(False, init=False)

    def __init__(
        self,
        label_off: str = "开始",
        label_on: str = "停止",
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(id=id, disabled=disabled)
        self._label_off = label_off
        self._label_on = label_on

    def render(self) -> str:
        label = self._label_on if self.state else self._label_off
        style = "white on red" if self.state else "white on green"
        return f"[{style}] {label} [/]"

    def on_click(self) -> None:
        self.state = not self.state
        self.post_message(self.Toggled(str(self.id), self.state))

    def reset(self) -> None:
        """Reset to OFF state."""
        self.state = False


# ═══════════════════════════════════════════════════════════
# LabelButton
# ═══════════════════════════════════════════════════════════

class LabelButton(Static, can_focus=True):
    """Compact clickable label that renders as a coloured button.

    Unlike Textual's built-in ``Button`` (which needs height ≥ 3),
    this widget renders at ``height: 1`` using Rich markup.
    """

    class Pressed(Message):
        """Emitted when the button is clicked."""

        def __init__(self, sender_id: str) -> None:
            self.sender_id = sender_id
            super().__init__()

    def __init__(
        self,
        label: str,
        *,
        style: str = "white on blue",
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(id=id, disabled=disabled)
        self._label = label
        self._style = style

    def render(self) -> str:
        return f"[{self._style}] {self._label} [/]"

    def on_click(self) -> None:
        self.post_message(self.Pressed(str(self.id)))


# ═══════════════════════════════════════════════════════════
# Section — bordered panel with title
# ═══════════════════════════════════════════════════════════

class Section(Container):
    """A bordered container with a title label at the top and a
    scrollable body for dynamic content."""

    def __init__(self, title: str, *, id: str | None = None, **kwargs) -> None:
        self._section_title = title
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        yield Label(self._section_title, classes="section-title")
        yield VerticalScroll(classes="section-body")

    @property
    def body(self) -> VerticalScroll:
        """The scrollable body where dynamic content is mounted."""
        return self.query_one(".section-body", VerticalScroll)


# ═══════════════════════════════════════════════════════════
# CompactSelect — dropdown selector at height 1
# ═══════════════════════════════════════════════════════════

class _SelectOverlay(Screen):
    """Overlay screen that presents a ListView for CompactSelect."""

    def __init__(self, options: list[tuple[str, str]], current: str) -> None:
        super().__init__()
        self._options = options
        self.result = current

    def compose(self) -> ComposeResult:
        items = [ListItem(Label(o[0])) for o in self._options]
        yield ListView(*items)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = event.list_view.index
        if idx is not None and idx < len(self._options):
            self.result = self._options[idx][1]
        self.dismiss(self.result)


class CompactSelect(Static, can_focus=True):
    """A dropdown selector that renders at height 1.

    Opens a full-screen overlay ``ListView`` on click so the user can
    pick an option.  Compatible API subset with Textual's ``Select``.
    """

    class Changed(Message):
        """Emitted when the selected value changes."""

        def __init__(self, value: str, sender_id: str) -> None:
            self.value = value
            self.sender_id = sender_id
            super().__init__()

    def __init__(
        self,
        options: list[tuple[str, str]],
        value: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._options = options
        self._value = value

    def render(self) -> str:
        label = self._value or "---"
        for display, val in self._options:
            if val == self._value:
                label = display
                break
        return f"[on $surface]{label} ▼[/]"

    @property
    def value(self) -> str:
        return self._value

    @value.setter
    def value(self, val: str) -> None:
        self._value = val
        self.refresh()

    def set_options(self, options: list[tuple[str, str]]) -> None:
        self._options = options

    def on_click(self) -> None:
        if not self._options:
            return
        self.app.push_screen(
            _SelectOverlay(self._options, self._value),
            callback=self._on_selected,
        )

    def _on_selected(self, result: str) -> None:
        if result != self._value:
            self._value = result
            self.refresh()
            self.post_message(self.Changed(result, str(self.id)))


# ═══════════════════════════════════════════════════════════
# MultiSelectField — horizontal [Switch] [Label] pairs
# ═══════════════════════════════════════════════════════════

class MultiSelectField(Horizontal):
    """Horizontal row of [Switch] [Label] pairs for multi-select settings.

    Args:
        options: list of (name, label, checked) tuples.
    """

    class Changed(Message):
        """Emitted when any switch is toggled."""

        def __init__(self, sender_id: str, values: dict[str, bool]) -> None:
            self.sender_id = sender_id
            self.values = values
            super().__init__()

    def __init__(
        self,
        options: list[tuple[str, str, bool]] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._opts: list[tuple[str, str, bool]] = options or []

    def compose(self) -> ComposeResult:
        for i, (name, label, checked) in enumerate(self._opts):
            yield CompactSwitch(value=checked, id=f"{self.id}-{i}")
            yield Label(label, classes="multi-select-label")

    @property
    def values(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for i, (name, _, _) in enumerate(self._opts):
            sw = self.query_one(f"#{self.id}-{i}", CompactSwitch)
            result[name] = sw.value
        return result

    def on_compact_switch_changed(self, event: CompactSwitch.Changed) -> None:
        event.stop()
        self.post_message(self.Changed(str(self.id), self.values))


# ═══════════════════════════════════════════════════════════
# MultiSelectSwitchField — multi-select with a sub-toggle per row
# ═══════════════════════════════════════════════════════════

class MultiSelectSwitchField(VerticalScroll):
    """Multi-select where each option row has two switches: a main enable
    toggle and a secondary toggle (e.g. "allow crafting").

    Renders as::

        [Switch] Label  [Switch] sub-label
        [Switch] Label  [Switch] sub-label
    """

    class Changed(Message):
        """Emitted when any switch is toggled."""

        def __init__(self, sender_id: str, values: dict[str, tuple[bool, bool]]) -> None:
            self.sender_id = sender_id
            self.values = values
            super().__init__()

    def __init__(
        self,
        options: list[tuple[str, str, bool, bool]] | None = None,
        switch_label: str = "",
        id: str | None = None,
    ) -> None:
        """*options*: list of ``(name, label, main_checked, sub_checked)``."""
        super().__init__(id=id)
        self._opts: list[tuple[str, str, bool, bool]] = options or []
        self._switch_label = switch_label

    def compose(self) -> ComposeResult:
        for i, (name, label, main_checked, sub_checked) in enumerate(self._opts):
            with Horizontal(classes="multi-switch-row"):
                yield CompactSwitch(value=main_checked, id=f"{self.id}-main-{i}")
                yield Label(label, classes="multi-switch-label")
                yield CompactSwitch(value=sub_checked, id=f"{self.id}-sub-{i}")
                if self._switch_label:
                    yield Label(self._switch_label, classes="multi-switch-sub-label")

    @property
    def values(self) -> dict[str, tuple[bool, bool]]:
        result: dict[str, tuple[bool, bool]] = {}
        for i, (name, _, _, _) in enumerate(self._opts):
            main = self.query_one(f"#{self.id}-main-{i}", CompactSwitch)
            sub = self.query_one(f"#{self.id}-sub-{i}", CompactSwitch)
            result[name] = (main.value, sub.value)
        return result

    def on_compact_switch_changed(self, event: CompactSwitch.Changed) -> None:
        event.stop()
        self.post_message(self.Changed(str(self.id), self.values))


# ═══════════════════════════════════════════════════════════
# DeviceBar
# ═══════════════════════════════════════════════════════════

class DeviceBar(Horizontal):
    """Top bar: device select, port input, save button, refresh button."""

    class Saved(Message):
        """Emitted when the save button is pressed."""

        def __init__(self, device: str, port: str) -> None:
            self.device = device
            self.port = port
            super().__init__()

    class RefreshPressed(Message):
        """Emitted when the refresh button is pressed."""

    class ReloadPressed(Message):
        """Emitted when the reload-config button is pressed."""

    def __init__(
        self,
        devices: list[str] | None = None,
        current_device: str = "",
        current_port: str = "7555",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._devices = devices or []
        self._current_device = current_device
        self._current_port = current_port

    def compose(self) -> ComposeResult:
        opts = [(d, d) for d in self._devices] or [("无设备", "__none__")]
        value = self._current_device if self._current_device and self._devices else "__none__"
        yield Label("设备:")
        yield CompactSelect(opts, value=value, id="device-select")
        yield Label("端口:")
        yield Input(
            value=self._current_port,
            id="port-input",
            placeholder="7555",
            validators=[Integer(minimum=1, maximum=65535)],
        )
        yield LabelButton("保存", id="device-save-btn", style="white on green")
        yield LabelButton("刷新", id="device-refresh-btn")
        yield Static("", classes="device-bar-spacer")
        yield LabelButton("重载配置", id="config-reload-btn")

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        if event.sender_id == "device-refresh-btn":
            self.post_message(self.RefreshPressed())
        elif event.sender_id == "config-reload-btn":
            self.post_message(self.ReloadPressed())
        elif event.sender_id == "device-save-btn":
            select = self.query_one("#device-select", CompactSelect)
            port = self.query_one("#port-input", Input)
            self.post_message(self.Saved(select.value, port.value))

    def set_devices(self, devices: list[str], current: str = "") -> None:
        """Replace the device dropdown options."""
        w = self.query_one("#device-select", CompactSelect)
        opts = [(d, d) for d in devices] or [("无设备", "__none__")]
        w.set_options(opts)
        w.value = current if current and devices else "__none__"


# ═══════════════════════════════════════════════════════════
# TaskCard
# ═══════════════════════════════════════════════════════════

class TaskCard(Horizontal):
    """A single task row: task name, toggle button, settings button."""

    class SettingsPressed(Message):
        """Emitted when the settings button is clicked."""

        def __init__(self, task_id: str) -> None:
            self.task_id = task_id
            super().__init__()

    class TogglePressed(Message):
        """Emitted when the start/stop toggle is clicked."""

        def __init__(self, task_id: str, running: bool) -> None:
            self.task_id = task_id
            self.running = running
            super().__init__()

    def __init__(self, task_id: str, task_name: str, id: str | None = None) -> None:
        self._task_id = task_id
        self._task_name = task_name
        super().__init__(id=id)

    def compose(self) -> ComposeResult:
        yield Label(self._task_name, classes="task-name")
        yield ToggleButton(id=f"toggle-{self._task_id}")
        yield LabelButton("设置", id=f"settings-{self._task_id}")

    def on_toggle_button_toggled(self, event: ToggleButton.Toggled) -> None:
        """Auto-handler: re-emit as TaskCard.TogglePressed."""
        event.stop()
        self.post_message(self.TogglePressed(self._task_id, event.state))

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        event.stop()
        self.post_message(self.SettingsPressed(self._task_id))

    @property
    def toggle(self) -> ToggleButton:
        """The toggle button inside this card."""
        return self.query_one(ToggleButton)

    def reset_toggle(self) -> None:
        """Reset toggle to OFF state."""
        self.toggle.reset()


# ═══════════════════════════════════════════════════════════
# TaskListPanel
# ═══════════════════════════════════════════════════════════

class TaskListPanel(Section):
    """Scrollable panel holding a list of :class:`TaskCard` widgets."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__("任务列表", id=id)

    def add_task(self, task_id: str, task_name: str) -> TaskCard:
        """Append a task card and return it."""
        card = TaskCard(task_id, task_name)
        self.body.mount(card)
        return card

    def clear_tasks(self) -> None:
        """Remove all task cards."""
        for child in self.body.query(TaskCard):
            child.remove()


# ═══════════════════════════════════════════════════════════
# SettingField
# ═══════════════════════════════════════════════════════════

@dataclass
class SettingField:
    """Descriptor for a single field in :class:`TaskSettingsPanel`."""

    name: str
    label: str
    type: str = "input"          # "input" | "integer" | "select" | "multi_select" | "multi_select_switch"
    value: str = ""
    options: list[str] = field(default_factory=list)
    switch_label: str = ""                        # multi_select_switch: sub-toggle label
    switch_values: dict[str, bool] = field(default_factory=dict)  # multi_select_switch: per-option sub-toggle state
    min: int | None = None                        # integer: min value
    max: int | None = None                        # integer: max value
    desc: str = ""                                # help text


# ═══════════════════════════════════════════════════════════
# TaskSettingsPanel
# ═══════════════════════════════════════════════════════════

class TaskSettingsPanel(Section):
    """Dynamic settings form that renders fields from :class:`SettingField`
    definitions and emits a :class:`Saved` message."""

    class Saved(Message):
        """Emitted when the save button is pressed."""

        def __init__(self, values: dict[str, object]) -> None:
            self.values = values
            super().__init__()

    def __init__(self, id: str | None = None) -> None:
        super().__init__("任务设置", id=id)
        self._fields: list[SettingField] = []
        self._mounted: list[Widget] = []
        self._pending_fields: list[SettingField] | None = None

    def set_fields(self, fields: list[SettingField]) -> None:
        """Clear existing widgets and rebuild the form (deferred to next refresh)."""
        self._fields = fields
        self._pending_fields = fields
        for w in self._mounted:
            w.remove()
        self._mounted.clear()
        self.call_after_refresh(self._rebuild_form)

    def _rebuild_form(self) -> None:
        if self._pending_fields is None:
            return
        fields = self._pending_fields
        self._pending_fields = None
        body = self.body
        mounted: list[Widget] = []
        for f in fields:
            label = Label(f.label, classes="field-label")
            body.mount(label)
            mounted.append(label)
            if f.type == "select":
                opts = [(o, o) for o in (f.options or [])]
                w = CompactSelect(opts, value=f.value, id=f"field-{f.name}")
                body.mount(w)
                mounted.append(w)
            elif f.type == "multi_select":
                selected = set(f.value.split(",") if f.value else [])
                for i, opt in enumerate(f.options or []):
                    row = Horizontal(classes="multi-select-row")
                    body.mount(row)
                    mounted.append(row)
                    sw = CompactSwitch(value=opt in selected, id=f"field-{f.name}-{i}")
                    row.mount(sw)
                    row.mount(Label(opt, classes="switch-label"))
            elif f.type == "multi_select_switch":
                selected = set(f.value.split(",") if f.value else [])
                sub_values = f.switch_values or {}
                opts: list[tuple[str, str, bool, bool]] = []
                for opt in f.options or []:
                    main_on = opt in selected
                    sub_on = sub_values.get(opt, False)
                    opts.append((opt, opt, main_on, sub_on))
                w = MultiSelectSwitchField(
                    options=opts,
                    switch_label=f.switch_label,
                    id=f"field-{f.name}",
                )
                body.mount(w)
                mounted.append(w)
            elif f.type == "integer":
                validators = [Integer(
                    minimum=f.min if f.min is not None else 0,
                    maximum=f.max if f.max is not None else None,
                )]
                w = Input(value=f.value or "", id=f"field-{f.name}",
                          placeholder=f.label, validators=validators)
                body.mount(w)
                mounted.append(w)
            elif f.type == "input":
                w = Input(value=f.value, id=f"field-{f.name}", placeholder=f.label)
                body.mount(w)
                mounted.append(w)
        if fields:
            save_btn = LabelButton("保存设置", id="settings-save-btn")
            body.mount(save_btn)
            mounted.append(save_btn)
        else:
            lb = Label("无可用设置")
            body.mount(lb)
            mounted.append(lb)
        self._mounted = mounted

    def on_label_button_pressed(self, event: LabelButton.Pressed) -> None:
        if event.sender_id != "settings-save-btn":
            return
        event.stop()
        values: dict[str, object] = {}
        for f in self._fields:
            if f.type == "select":
                w = self.query_one(f"#field-{f.name}", CompactSelect)
                values[f.name] = w.value
            elif f.type == "multi_select":
                selected = []
                for i, opt in enumerate(f.options or []):
                    sw = self.query_one(f"#field-{f.name}-{i}", CompactSwitch)
                    if sw.value:
                        selected.append(opt)
                values[f.name] = ",".join(selected) if selected else ""
            elif f.type == "multi_select_switch":
                w = self.query_one(f"#field-{f.name}", MultiSelectSwitchField)
                enabled: list[str] = []
                sub_on: list[str] = []
                for name, (main, sub) in w.values.items():
                    if main:
                        enabled.append(name)
                        if sub:
                            sub_on.append(name)
                values[f.name] = ",".join(enabled) if enabled else ""
                values[f"{f.name}__sub"] = ",".join(sub_on) if sub_on else ""
            elif f.type == "integer":
                w = self.query_one(f"#field-{f.name}", Input)
                values[f.name] = w.value
            elif f.type == "input":
                w = self.query_one(f"#field-{f.name}", Input)
                values[f.name] = w.value
        self.post_message(self.Saved(values))


# ═══════════════════════════════════════════════════════════
# QueuePanel
# ═══════════════════════════════════════════════════════════

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
        qs = queues or []
        self._opts = qs if qs else [("-- 无队列 --", "")]

    def on_mount(self) -> None:
        self.body.mount(Label("队列:", classes="field-label"))
        select = CompactSelect(self._opts, id="queue-select")
        if self._opts and self._opts[0][1]:
            select.value = self._opts[0][1]
        self.body.mount(select)
        has_queue = bool(self._opts[0][1]) if self._opts else False
        self.body.mount(
            ToggleButton(label_off="开始执行", label_on="停止执行", id="queue-toggle", disabled=not has_queue)
        )
        self.body.mount(LabelButton("新建队列", id="queue-new"))
        self.body.mount(LabelButton("编辑队列", id="queue-edit", disabled=not has_queue))

    def on_compact_select_changed(self, event: CompactSelect.Changed) -> None:
        if event.sender_id != "queue-select":
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
        if event.sender_id == "queue-new":
            self.post_message(self.EditRequested(None))
        elif event.sender_id == "queue-edit":
            select = self.query_one("#queue-select", CompactSelect)
            self.post_message(self.EditRequested(select.value or None))

    def set_queues(self, queues: list[tuple[str, str]]) -> None:
        opts = queues if queues else [("-- 无队列 --", "")]
        w = self.query_one("#queue-select", CompactSelect)
        w.set_options(opts)
        if queues:
            w.value = queues[0][1]
        else:
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


# ═══════════════════════════════════════════════════════════
# _ConfirmDialog — simple yes/no confirmation overlay
# ═══════════════════════════════════════════════════════════

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
        if event.sender_id == "confirm-yes":
            self.result = True
        self.dismiss(self.result)


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
        cid = event.sender_id or ""
        if cid.startswith("up-"):
            self.post_message(self.ActionRequested(self._index, "up"))
        elif cid.startswith("down-"):
            self.post_message(self.ActionRequested(self._index, "down"))
        elif cid.startswith("del-"):
            self.post_message(self.ActionRequested(self._index, "delete"))


# ═══════════════════════════════════════════════════════════
# QueueEditorScreen — full-screen queue editor
# ═══════════════════════════════════════════════════════════

class QueueEditorScreen(Screen):
    """Full-screen queue editor."""

    BINDINGS = [
        Binding("escape", "cancel", "取消"),
        Binding("ctrl+s", "save", "保存"),
        Binding("ctrl+up", "move_up", "上移"),
        Binding("ctrl+down", "move_down", "下移"),
    ]

    def __init__(self, queue_id: str | None, queue_name: str, tasks: list[tuple[str, str]],
                 available_tasks: list[tuple[str, str]]):
        super().__init__()
        self._queue_id = queue_id
        self._queue_name = queue_name
        self._queue_tasks: list[tuple[str, str]] = tasks
        self._available = available_tasks

    def compose(self) -> ComposeResult:
        title = f"编辑队列: {self._queue_name}" if self._queue_name else "新建队列"
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

    def on__available_task_row_add_requested(self, event: _AvailableTaskRow.AddRequested) -> None:
        event.stop()
        key = event.task_key
        name = next((n for k, n in self._available if k == key), key)
        self._queue_tasks.append((key, name))
        self._refresh_queue_tasks()

    def on__queue_task_row_action_requested(self, event: _QueueTaskRow.ActionRequested) -> None:
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

    def action_save(self) -> None:
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
        cid = event.sender_id
        if cid == "editor-save":
            self.action_save()
        elif cid == "editor-cancel":
            self.action_cancel()
        elif cid == "editor-delete":
            self._confirm_delete()

    def _confirm_delete(self) -> None:
        def callback(result: bool) -> None:
            if result:
                self.dismiss({"delete": True})
        self.app.push_screen(_ConfirmDialog("确认删除此队列？此操作不可撤销。"), callback=callback)
