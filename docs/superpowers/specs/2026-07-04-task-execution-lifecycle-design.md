# 任务执行生命周期重构 — 设计文档

**日期**: 2026-07-04
**目标**: 用 CancellationToken + TaskExecutionManager 替代 polling 式的 `stop_event` 检查，使任务启动/停止更精准、即时、可维护。

## 1. 问题分析

### 现状

| 检查点 | 文件:行号 | 方式 |
|--------|-----------|------|
| `exec()` 入口 | jczxCli.py:741 | `stop_event.is_set()` → `return None` |
| `_exec_entity()` 循环 | jczxCli.py:558 | `stop_event.is_set()` → `return None` |
| `exec_dynamic()` | jczxCli.py:413 | `stop_event.is_set()` → `return None` |
| `exec_task()` | jczxCli.py:494,538 | `stop_event.is_set()` → `return None` |
| `_wait_for_image()` | jczxCli.py:782 | `while not stop_event.is_set()` |
| `_start_task()` | jczxCli.py:1121-1124 | `stop_event.clear()` + submit |
| `_stop_running_task()` | jczxCli.py:1127-1133 | `stop_event.set()` + `future.cancel()` |

### 缺陷

1. **分散轮询** — 7 个地点各自检查，新增 exec 方法易遗漏
2. **不可即刻中断** — `time.sleep(x)` 和 `future.cancel()` 无法中断正在运行的线程
3. **静默返回 None** — `return None` 可能被误当做正常结果，上层无感知
4. **全局状态耦合** — `stop_event` 在 JCZXGaming，`_running_future` / `_running_task_id` 在 JczxCli，状态一致靠手动

## 2. 设计方案

### 2.1 CancellationToken — 底层中断原语

```python
class TaskCancelledError(Exception):
    """任务被取消时抛出的异常。"""

class CancellationToken:
    """可中断的取消令牌。"""

    def __init__(self):
        self._event = threading.Event()

    def sleep(self, seconds: float) -> None:
        """可中断的 sleep：若在等待期间被 cancel()，立即抛 TaskCancelledError。"""
        if self._event.wait(timeout=seconds):
            raise TaskCancelledError()

    def cancel(self) -> None:
        """标记取消，唤醒所有正在 sleep() 的调用者。"""
        self._event.set()

    def reset(self) -> None:
        """重置为未取消状态。"""
        self._event.clear()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """门禁检查：若已取消则立即抛异常，否则无操作。"""
        if self._event.is_set():
            raise TaskCancelledError()
```

- `sleep(sec)` 替代所有 `time.sleep(sec)` — 被 cancel 后**立即**抛异常，不等待
- `check()` 替代所有 `stop_event.is_set()` 检查 — 统一用异常传播中断
- `reset()` / `cancel()` 独立于构造，支持复用

### 2.2 TaskExecutionManager — 任务生命周期管理器

单一、长期存活的管理器，负责一次任务执行的状态机：`idle → running → idle`。

```python
class TaskExecutionManager:
    """管理单次任务执行的生命周期。创建于 JCZXGaming.__init__，长期存活。"""

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
        """启动任务：重置 token 并记录 task_id。"""
        self._token.reset()
        self._task_id = task_id

    def stop(self) -> None:
        """停止任务：幂等取消。"""
        if not self._token.is_cancelled():
            self._token.cancel()

    def reset(self) -> None:
        """任务结束（正常/异常/取消后），回到 idle。"""
        self._token.reset()
        self._task_id = None
```

**设计决策：**
- `stop()` 不直接改 `_task_id` — task_id 只有在 `reset()` 时才清除，保证异常处理时仍可追踪
- `start()` 必须对已取消的 token 做 `reset()` — 否则残留的 cancel 状态会直接中断新任务
- Manager 不关心 `JczxSectionEntity` / `JczxCli` — 纯状态管理，零业务耦合

### 2.3 JCZXGaming 集成

移除 `self.stop_event`，替换为 `self._exec_mgr: TaskExecutionManager`。

| 位置 | 当前 | 改为 |
|------|------|------|
| `__init__` | `self.stop_event = threading.Event()` | `self._exec_mgr = TaskExecutionManager()` |
| `exec()` (L741) | `if self.stop_event.is_set(): return None` | `self._exec_mgr.token.check()` |
| `_exec_entity()` (L558) | `if self.stop_event.is_set(): return None` | `self._exec_mgr.token.check()` |
| `exec_dynamic()` (L413) | `if self.stop_event.is_set(): return None` | `self._exec_mgr.token.check()` |
| `exec_task()` (L494,538) | `if self.stop_event.is_set(): return None` | `self._exec_mgr.token.check()` |
| `_wait_for_image()` (L782) | `while not self.stop_event.is_set()` | 循环顶部 `self._exec_mgr.token.check()` |
| 所有 `time.sleep(x)` | `time.sleep(x)` | `self._exec_mgr.token.sleep(x)` |

**异常传播：** `check()` 和 `sleep()` 抛出 `TaskCancelledError`，沿调用栈向上冒泡。无需在各层 `return None`。最高层调用方（`_run_task`）捕获并处理日志。

### 2.4 JczxCli 集成

移除 `self._running_task_id: str | None`，改为委托查询 manager。保留 `self._running_future`（UI 侧 future 跟踪）。

```python
@property
def _running_task_id(self) -> str | None:
    return self.device._exec_mgr.task_id if self.device else None
```

| 方法 | 当前 | 改为 |
|------|------|------|
| `_start_task()` | `self.device.stop_event.clear()` + `self._running_task_id = task_id` | `self.device._exec_mgr.start(task_id)` |
| `_stop_running_task()` | `self.device.stop_event.set()` + `future.cancel()` | `self.device._exec_mgr.stop()` |
| `_on_task_finished()` | 检查 `self._running_task_id != task_id` + 手动清理 | `self.device._exec_mgr.reset()` + UI 复位 |

`_run_task` 增加异常处理：

```python
def _run_task(self, entity, task_id):
    try:
        self.device.exec_task_raw(entity)
    except TaskCancelledError:
        self.logger.info("任务已取消: %s", entity.get_task_name())
    except Exception as e:
        self.logger.error("任务执行异常: %s", e)
    finally:
        self.call_from_thread(self._on_task_finished, task_id)
```

`_on_task_finished` 保证执行 `exec_mgr.reset()`，无论任务正常结束、取消还是崩溃。

### 2.5 设计模式总结

| 模式 | 应用 |
|------|------|
| **Template Method** | `_exec_entity` 已是，不动 |
| **Command** | `CancellationToken.token.check()` / `sleep()` 统一中断命令 |
| **Observer (轻量)** | `threading.Event.wait()` 作为唤醒机制，替代轮询 |
| **State** | `TaskExecutionManager` 管理 idle / running 状态转换 |

## 3. 文件变更清单

| 文件 | 变更 |
|------|------|
| `jczx/jczx/jczxCli.py` | 新增 `TaskCancelledError`、`CancellationToken`、`TaskExecutionManager` 类；JCZXGaming 替换 `stop_event`；JczxCli 替换 `_running_task_id`；`_run_task` 增加异常捕获 |
| 无其他文件变更 | — |

## 4. 验收标准

1. **即刻停止** — 任意耗时操作（sleep、wait_for_image）被 stop 后 < 100ms 内中断
2. **幂等停止** — 多次调用 `_stop_running_task()` 不报错
3. **停止后再启动** — 同一个 manager 可反复 start/stop/start，无残留状态
4. **异常安全** — 任务异常（包括 `TaskCancelledError`）后 UI 正确复位 toggle
5. **无遗漏检查点** — 新 exec 方法只需在入口调用 `self._exec_mgr.token.check()` 即获得保护
