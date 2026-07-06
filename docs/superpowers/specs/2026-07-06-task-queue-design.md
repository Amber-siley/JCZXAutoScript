# 任务队列系统设计

## 概述

将 TUI 右侧面板的 `TaskEditorPanel`（原"任务编辑器"：下拉选任务 + 开始/停止）改造为**任务队列系统**，支持用户创建、编辑、保存有顺序的任务队列，并按顺序依次执行。

原 TaskEditorPanel 只是从任务列表下拉选择一个任务执行，功能简单。改造后，用户可将多个任务组合为队列，队列持久化到独立配置文件，支持运行时进度显示，与单个任务执行互斥。

## 设计决策

| 决策 | 选项 | 理由 |
|------|------|------|
| 队列持久化 | 新的 `Config/Queues.txt` | 与 MainMenu.txt 隔离，职责清晰 |
| 编辑器 | 全屏 Screen (`push_screen`) | 空间充足，交互不拥挤 |
| 排序交互 | ↑↓ 按钮 + Ctrl+Up/Down 快捷键 | Textual 终端不支持原生拖拽 |
| 互斥行为 | 阻止启动（不自动停止） | 安全，log 提示即可 |
| 进度显示 | log + 队列选择器旁文字 | 不增加新 widget，信息量刚好 |

## 数据模型

### 队列配置文件

**文件路径**: `jczx/Config/Queues.txt`

```ini
/ 任务队列配置
/ section 名 = queue ID（建议 queue- 前缀避免与 task entity 冲突）
/ name: 队列显示名称
/ tasks: 逗号分隔的任务 entity key，按顺序执行，允许重复

[queue-daily]
name: 日常
tasks: jjc, inllusion, screenshot-task

[queue-weekly]
name: 周常
tasks: jjc, inllusion
```

### 运行时数据结构

```python
@dataclass
class QueueEntity:
    id: str                    # "queue-daily"
    name: str                  # "日常"
    tasks: list[str]           # ["jjc", "inllusion", "screenshot-task"]
```

不直接复用 `JczxSectionEntity`（字段含义不匹配），用简单 dataclass。

### TaskManage 扩展

```python
class TaskManage:
    queue_config: TxtConfig           # 新增：Queues.txt 的配置对象
    _queue_cache: dict[str, QueueEntity]  # queue_id → QueueEntity

    def load_queues(self) -> None:
        """加载 Queues.txt，解析为 QueueEntity 缓存"""
    def get_queues(self) -> list[QueueEntity]:
        """返回所有队列"""
    def get_queue(self, queue_id: str) -> QueueEntity | None:
        """获取单个队列"""
    def save_queue(self, queue_id: str, name: str, tasks: list[str]) -> None:
        """保存/创建队列，写入 Queues.txt"""
    def delete_queue(self, queue_id: str) -> None:
        """删除队列，从 Queues.txt 移除对应 section"""
    def get_queue_tasks(self, queue_id: str) -> list[JczxSectionEntity]:
        """解析队列的 tasks 列表为 JczxSectionEntity 对象（仅 view:on 的任务）"""
```

`QueueEntity.tasks` 存储的是 entity key（字符串），运行时通过 `task_pool` 解析为 `JczxSectionEntity`。

## UI 设计

### 主界面右侧面板

将第三块 `TaskEditorPanel` 替换为 **`QueuePanel`**（仍是 `Section` 子类）：

```
┌─ 任务队列 ──────────────────┐
│ [队列: ▼ 日常           ]    │  ← CompactSelect（含 "-- 无队列 --"）
│ [▶ 开始]                     │  ← ToggleButton（运行中显示 ■ 停止）
│ 日常 → 2/5 jjc-challenge    │  ← 进度标签（仅运行时可见，class="queue-progress"）
│ [新建队列] [编辑队列]        │  ← 两个 LabelButton
└─────────────────────────────┘
```

**组件说明**：
- `CompactSelect`: 列出所有队列 + `("-- 无队列 --", "")` 默认项
- `ToggleButton`: `label_off="开始执行"`, `label_on="停止执行"`，队列未选中时 disabled
- 进度标签：运行时动态更新 `mount`/`remove`，显示 `{队列名} → {当前序号}/{总数} {当前任务名}`
- `新建队列`按钮：`push_screen(QueueEditorScreen())` 空名称
- `编辑队列`按钮：传入当前选中队列数据；未选中队列时 disabled
- 队列编辑完成保存后 `dismiss` 回主界面，下拉框自动刷新选中新/编辑的队列

**保存流程**：编辑器中点保存 → `TaskManage.save_queue()` 写入 Queues.txt → `TaskManage.load_queues()` 刷新缓存 → `QueuePanel` 重建下拉列表选项 → 选中刚保存的队列

**消息**：
- `QueuePanel.RunRequested(queue_id: str, running: bool)`
- `QueuePanel.EditRequested(queue_id: str | None)` — None 表示新建

### 队列编辑器 Screen

全屏 `Screen`，三区域布局：

```
QueueEditorScreen
├── Header（队列名称 + 关闭提示）
├── 主体（Horizontal 两栏）
│   ├── 左侧：可用任务列表（Section "可用任务"）
│   │   └── 每行：[+] Label  ← 点击添加到右侧
│   └── 右侧：队列任务列表（Section "队列任务"）
│       └── 每行：序号. 任务名  ↑ ↓ ✕
│           ↑ 上移 / ↓ 下移 / ✕ 删除
└── 底部：名称输入 + 操作按钮
    ├── Input(placeholder="队列名称", value=name)
    ├── [保存] [取消]
    └── [删除队列]（仅编辑已有队列时显示）
```

**左侧面板** (`AvailableTasksPanel`，`Section` 子类)：
- 从 `task_pool` 获取所有 `view: on` 的任务
- 每行：任务名 + `[+]` 按钮
- 点击 `[+]` → 发送 `AddTaskRequested(task_key)` 消息

**右侧面板** (`QueueTasksPanel`，`Section` 子类)：
- 显示已添加任务的排序列表
- 每行组件 `QueueTaskRow`：
  - `Label`: `{序号}. {任务显示名}`
  - `↑` 按钮：上移（第一条隐藏/disabled）
  - `↓` 按钮：下移（最后一条隐藏/disabled）
  - `✕` 按钮：删除此项
- 支持 `Ctrl+Up`/`Ctrl+Down` 移动当前选中行（通过 `ListView` focus + 快捷键）
- 允许重复添加同一任务

**快捷键**（仅队列编辑器 Screen 内有效）：
| 快捷键 | 操作 |
|--------|------|
| `Ctrl+S` | 保存 |
| `Ctrl+Up` | 当前选中任务上移 |
| `Ctrl+Down` | 当前选中任务下移 |
| `Escape` | 取消/返回 |

**删除队列**：
- 点击"删除队列"按钮 → 弹出确认对话框（`_ConfirmDialog` overlay Screen）
- 确认后删除，dismiss 回主界面

### 主界面交互流

1. 用户在 `QueuePanel` 下拉框选择队列
2. 点击"开始执行" → `_start_queue(queue_id)`
3. ToggleButton 变为"停止执行"
4. 进度标签显示 `队列名 → 1/5 第一个任务名`
5. 依次执行每个任务的 `exec_task_raw`
6. 执行完毕 → ToggleButton 恢复，进度标签移除

## 执行引擎

### 新增方法

```python
def exec_queue(self, queue_id: str) -> None:
    """按顺序执行队列中的所有任务"""
    queue = self.task_manage.get_queue(queue_id)
    tasks = queue.tasks  # list[str] of entity keys
    n = len(tasks)
    self.log.info(f"开始执行队列 [{queue.name}]，共 {n} 个任务")

    for i, task_key in enumerate(tasks):
        self._exec_mgr.token.check()  # 支持外部取消
        entity = self.task_manage.get_task(task_key)
        if entity is None:
            self.log.warning(f"队列任务 [{task_key}] 不存在，跳过")
            continue

        self.log.info(f"队列 [{queue.name}] {i+1}/{n}: {entity.get_task_name()}")
        self.call_from_thread(self._on_queue_progress, queue.name, i, n, entity.get_task_name())
        self.exec_task_raw(task_key)

    self.log.info(f"队列 [{queue.name}] 执行完毕")
```

### 进度回调

```python
def _on_queue_progress(self, name: str, idx: int, total: int, task_name: str) -> None:
    """更新主界面进度标签（在主线程中调用）"""
    self.queue_panel.update_progress(name, idx, total, task_name)
```

### 互斥逻辑

在 `_start_queue` 和 `_start_task` 入口处：

```python
def _start_queue(self, queue_id: str) -> bool:
    if self._exec_mgr.is_running:
        self.log.warning("已有任务/队列正在执行，请先停止")
        return False
    # ... proceed
```

`is_running` 属性：
```python
@property
def is_running(self) -> bool:
    return self._current_task is not None and self.token is not None and not self.token.is_cancelled
```

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `jczx/jczxCli.py` | 新增 `QueuePanel` 处理、`QueueEditorScreen`、`exec_queue`、`_start_queue`、互斥检查、进度更新 |
| `jczx/widgets.py` | 新增 `QueuePanel`、`QueueEditorScreen`、`QueueTaskRow`、`AvailableTasksPanel`、`QueueTasksPanel`、`_ConfirmDialog` |
| `jczx/taskManage.py` | 新增 `queue_config`、`load_queues`、`get_queue`、`save_queue`、`delete_queue`、`QueueEntity` |
| `jczx/Css/main.tcss` | 新增 `.queue-progress`、`QueuePanel`、`QueueEditorScreen`、`QueueTaskRow` 样式 |
| `jczx/Config/Queues.txt` | **新建**，示例队列数据 |

### 注意事项

- **保存时校验**：保存队列时不校验 `tasks` 中的 entity key 是否存在（任务可能在后续被删除或改名）。执行时跳过不存在的任务并 log 警告。
- **Ctrl+S 快捷键**：仅在队列编辑器 Screen 内有效，主界面已有 `Ctrl+Shift+C` 绑定，不冲突。

## 不在范围内

- 队列嵌套（队列中包含队列）
- 队列的条件分支（if/else）
- 队列参数传递（队列间共享变量）
- 定时执行队列
- 旧版 PyQt6 GUI 适配
