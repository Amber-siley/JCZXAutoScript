# 占位符解析统一重构 — 设计文档

**日期**: 2026-07-04
**目标**: 将分散在 `taskManage.py` 和 `jczxCli.py` 中的 15+ 个占位符解析方法合并为一个 `PlaceholderResolver` 类，提供单一入口 `resolve(text, after_key) -> str`。

## 1. 问题分析

### 现状

占位符解析逻辑散落在两个文件、15 个方法中，调用方需手动组合多个解析步骤：

| 位置 | 方法 | 职责 | 行数 |
|------|------|------|------|
| `taskManage.py` | `_resolve_placeholder` | `${}` 核心解析 | 20 |
| `taskManage.py` | `resolve_placeholders` | 批量 `${}` | 12 |
| `jczxCli.py` | `_resolve_placeholder` | `${}` 桥接 | 2 |
| `jczxCli.py` | `parse_placeholder` | `${}` 外部包装 | 2 |
| `jczxCli.py` | `_resolve_exec_placeholders` | 批量 `@{}` | 5 |
| `jczxCli.py` | `_resolve_exec_placeholder` | 单个 `@{}` / `%{}` | 25 |
| `jczxCli.py` | `_eval_condition` | `&{}` 入口 | 7 |
| `jczxCli.py` | `_eval_condition_expr` | `&{}` 表达式 | 80 |
| `jczxCli.py` | `_tokenize_condition` | 词法分析 | 30 |
| `jczxCli.py` | `_eval_context_expr` | `%{}` 表达式 | 45 |
| `jczxCli.py` | `_is_context_expr` | 表达式检测 | 4 |
| `jczxCli.py` | `_resolve_log_condition_placeholders` | log 格式化(带副作用) | 18 |
| `jczxCli.py` | `_format_condition` | 条件格式化 | 12 |
| `jczxCli.py` | `_LOG_CONDITION_PATTERN` 等 | 正则常量 | 3 |

每个 exec_* 方法手动调用不同的组合：
- `exec_func`: `resolve_placeholders` + `_resolve_exec_placeholders`
- `exec_context`: `resolve_placeholders` + `_resolve_exec_placeholders`
- `exec_ocr`: `_resolve_placeholder`
- `exec_click`: `_resolve_placeholder` + `_resolve_exec_placeholder` + `_eval_condition` + `_format_condition`
- `exec_condition`: `_eval_condition` + `_format_condition`
- `_log_message`: `resolve_placeholders` + `_resolve_exec_placeholder` + `_resolve_log_condition_placeholders` + `_eval_condition_expr`

### 核心问题

1. **代码散落** — 同一功能横跨两个文件，修改一种占位符行为需改多处
2. **调用不一致** — 各 exec_* 方法调用不同解析组合，new type 易遗漏
3. **副作用与展示混合** — `_resolve_log_condition_placeholders` 在格式化日志时执行实体（已导致重复执行 bug）
4. **测试困难** — 解析逻辑与业务逻辑耦合在 JCZXGaming 巨型类中，无法独立验证
5. **jczxCli.py 臃肿** — ~1300 行，其中 ~250 行是占位符解析逻辑

## 2. 设计方案

### 2.1 PlaceholderResolver 类（Strategy 模式）

新增独立类，JCZXGaming 持有实例。单一入口 `resolve(text, after_key) -> str`。

```python
class PlaceholderResolver:
    """统一占位符解析器。
    四种占位符按固定顺序解析：${} → @{} → %{} → &{...}。
    """

    _CONFIG_PATTERN = re.compile(r"\$\{(.+?)\}")
    _EXEC_PATTERN = re.compile(r"@\{(.+?)\}")
    _CTX_PATTERN = re.compile(r"%\{(.+?)\}")
    _CONDITION_PATTERN = re.compile(r"^&\{(.+)\}$")
    _LOG_CONDITION_PATTERN = re.compile(r"&\{(.+?)\}")

    def __init__(self, gaming: 'JCZXGaming'):
        self._gaming = gaming

    def resolve(self, text: str, after_key: str) -> str:
        """统一入口。
        - 普通文本：${} → @{} → %{}，跳过 &{}。
        - 纯 &{...} 条件：一步返回 "True"/"False"。
        - 混合文本（如 log）：${} → @{} → %{} → 内嵌 &{...} 替换。
        """
        if not text or not isinstance(text, str):
            return text
        result = self._resolve_config(text, after_key)
        result = self._resolve_exec(result)
        result = self._resolve_context(result)
        result = self._resolve_condition(result, after_key)
        return result

    def resolve_list(self, items: list, after_key: str) -> list:
        return [self.resolve(i, after_key) if isinstance(i, str) else i for i in items]

    # ── Private ──

    def _resolve_config(self, text: str, after_key: str) -> str:
        """${section:option} / ${option} 配置值替换。委托 taskManage。"""
        result = text
        for m in self._CONFIG_PATTERN.findall(text):
            val = self._gaming.task_manage._resolve_placeholder("${" + m + "}", after_key)
            result = result.replace("${" + m + "}", str(val) if val else "")
        return result

    def _resolve_exec(self, text: str) -> str:
        """@{entity_key} 执行实体，替换返回值。"""
        result = text
        for m in self._EXEC_PATTERN.findall(result):
            val = self._gaming.exec(m)
            result = result.replace("@{" + m + "}", str(val) if val is not None else "")
        return result

    def _resolve_context(self, text: str) -> str:
        """%{context_key} / %{expr} 读取上下文变量或表达式求值。"""
        result = text
        for m in self._CTX_PATTERN.findall(result):
            if self._is_context_expr(m):
                val = self._eval_context_expr(m)
            else:
                val = self._gaming._context.get(m, "")
            result = result.replace("%{" + m + "}", str(val) if val else "")
        return result

    def _resolve_condition(self, text: str, after_key: str) -> str:
        """检测 &{...} 模式。纯条件直接求值，混合文本查找替换。"""
        if self._CONDITION_PATTERN.match(text):
            return str(self._eval_condition_expr(
                self._CONDITION_PATTERN.match(text).group(1), after_key))
        result = text
        for m in self._LOG_CONDITION_PATTERN.findall(text):
            val = self._eval_condition_expr(m, after_key)
            result = result.replace("&{" + m + "}", str(val))
        return result
```

### 2.2 JCZXGaming 集成

**构造：**
```python
# JCZXGaming.__init__ 增加一行
self._resolver = PlaceholderResolver(self)
```

**删除 14 个冗余方法/属性：**
- `_resolve_placeholder`, `parse_placeholder`（桥接方法）
- `_resolve_exec_placeholders`, `_resolve_exec_placeholder`
- `_eval_condition`, `_eval_condition_expr`, `_tokenize_condition`
- `_eval_context_expr`, `_is_context_expr`
- `_resolve_log_condition_placeholders`, `_format_condition`
- `_CONDITION_EXPR_PATTERN`, `_EXEC_PLACEHOLDER_PATTERN` 等正则常量

**保留：** `_CONFIG_PLACEHOLDER_PATTERN`, `_CTX_PLACEHOLDER_PATTERN` 在 condition 上下文引用时可能使用（如有保留引用则移到 resolver）。

**7 个 call site 改为统一调用：**

| 方法 | 当前 | 改为 |
|------|------|------|
| `exec_func` | `resolve_placeholders(args)` → `_resolve_exec_placeholders(args)` | `self._resolver.resolve_list(args, entity.only_key)` |
| `exec_context` | `resolve_placeholders(actions)` → `_resolve_exec_placeholders(actions)` | `self._resolver.resolve_list(actions, entity.only_key)` |
| `exec_ocr` | `_resolve_placeholder(target)` | `self._resolver.resolve(target, entity.only_key)` |
| `exec_click` | `_resolve_placeholder(target)` → `_resolve_exec_placeholder(target)` | `self._resolver.resolve(target, entity.only_key)` |
| `exec_condition` | `_eval_condition(cond)` + `_format_condition(cond, result)` | `self._resolver.resolve(cond, entity.only_key)` 对比 "True" |
| `exec_click` 内条件 | 同上 | 同上 |
| `_log_message` | `resolve_placeholders` → `_resolve_exec_placeholder` → `_resolve_log_condition_placeholders` → `_eval_condition_expr` | `self._resolver.resolve(msg, entity.only_key)` |

**exec_condition 简化示例：**

```python
# 当前 (20 行)
def exec_condition(self, section):
    entity = self._get_entity(section)
    def _on_exec(e):
        if e.condition_not:
            cond_result = self._eval_condition(e.condition_not)
            if not cond_result:
                self.log.debug(f"条件 {self._format_condition(e.condition_not, cond_result)} ...")
                for s in e.condition_then: result = self.exec(s)
            else:
                self.log.debug(f"条件 {self._format_condition(e.condition_not, cond_result)} ...")
                for s in e.condition_else: result = self.exec(s)
        elif e.condition:
            cond_result = self._eval_condition(e.condition)
            ...

# 改为 (12 行)
def exec_condition(self, section):
    entity = self._get_entity(section)
    def _on_exec(e):
        result = None
        if e.condition_not:
            if self._resolver.resolve(e.condition_not, e.only_key) != "True":
                self.log.debug(f"条件 {e.condition_not} 满足 condition_not，执行 condition_then {e.condition_then}")
                for s in e.condition_then: result = self.exec(s)
            else:
                self.log.debug(f"条件 {e.condition_not} 不满足 condition_not，执行 condition_else {e.condition_else}")
                for s in e.condition_else: result = self.exec(s)
        elif e.condition:
            if self._resolver.resolve(e.condition, e.only_key) == "True":
                self.log.debug(f"条件 {e.condition} 满足 condition，执行 condition_then {e.condition_then}")
                for s in e.condition_then: result = self.exec(s)
            else:
                ...
```

### 2.3 外部接口保持

`taskManage.py` 中的 `_resolve_placeholder(arg, after_key)` 方法**保留不变**——它被 `get_entity()` 和 `get_img()` 等内部方法使用，且这些调用属于实体/图片查找而非占位符文本替换。

`PlaceholderResolver._resolve_config` 通过 `self._gaming.task_manage._resolve_placeholder(...)` 调用该方法。

## 3. 文件变更

| 文件 | 变更 |
|------|------|
| `jczx/jczx/jczxCli.py` | 新增 `PlaceholderResolver` 类（~120 行）；JCZXGaming 删除 14 个旧方法/属性（~250 行）；7 个 call site 改为统一调用（每处 ~3 行） |
| `jczx/jczx/taskManage.py` | 不变 |

## 4. 验收标准

1. **单一入口** — 所有占位符解析通过 `self._resolver.resolve()` 完成，exec_* 方法不直接调用任何 `_resolve_*` 私有方法
2. **无副作用** — 条件日志格式化不再触发实体执行
3. **行为一致** — 四种占位符的解析行为与重构前完全一致（顺序、结果、边界情况）
4. **条件返回字符串** — `resolve()` 对 `&{...}` 条件返回 `"True"` / `"False"` 字符串，调用方通过 `== "True"` 判断
5. **代码量减少** — jczxCli.py 移除 ~250 行重复/冗余代码
6. **可测试** — PlaceholderResolver 可独立实例化（mock JCZXGaming 引用）进行单元验证
