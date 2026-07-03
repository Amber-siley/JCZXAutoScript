# 占位符解析统一重构 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将分散在 `taskManage.py` 和 `jczxCli.py` 中的 15 个占位符解析方法合并为单一 `PlaceholderResolver` 类，提供 `resolve(text, after_key) -> str` 统一入口。

**Architecture:** 新增 `PlaceholderResolver` 类（~120 行）绑定 JCZXGaming，内部按 `${}` → `@{}` → `%{}` → `&{...}` 顺序解析。JCZXGaming 持有一个 `self._resolver` 实例，所有 exec_* 方法通过 `self._resolver.resolve()` 替代手动组合调用。删除 14 个旧方法/常量。

**Tech Stack:** Python 3.14, `re`

**Spec:** `docs/superpowers/specs/2026-07-04-placeholder-resolver-consolidation-design.md`

---

## File Changes

| 文件 | 操作 |
|------|------|
| `jczx/jczx/jczxCli.py` | 新增 PlaceholderResolver 类 + 修改 JCZXGaming.__init__ + 修改 7 个 call site + 删除 14 个旧方法/属性 |

---

### Task 1: 创建 PlaceholderResolver 类

**Files:**
- Modify: `jczx/jczx/jczxCli.py` (插入在 `TaskExecutionManager` 之后、`JCZXGaming` 之前)

- [ ] **Step 1: 写入完整的 PlaceholderResolver 类**

找到 `class TaskExecutionManager:` 所在的代码块结尾（在 `class JCZXGaming` 之前）。在两者之间插入以下代码：

```python
class PlaceholderResolver:
    _CONFIG_PATTERN = re.compile(r"\$\{(.+?)\}")
    _EXEC_PATTERN = re.compile(r"@\{(.+?)\}")
    _CTX_PATTERN = re.compile(r"%\{(.+?)\}")
    _CONDITION_PATTERN = re.compile(r"^&\{(.+)\}$")
    _LOG_CONDITION_PATTERN = re.compile(r"&\{(.+?)\}")

    def __init__(self, gaming):
        self._gaming = gaming

    def resolve(self, text: str, after_key: str) -> str:
        if not text or not isinstance(text, str):
            return text
        result = self._resolve_config(text, after_key)
        result = self._resolve_exec(result)
        result = self._resolve_context(result)
        result = self._resolve_condition(result, after_key)
        return result

    def resolve_list(self, items: list, after_key: str) -> list:
        return [self.resolve(i, after_key) if isinstance(i, str) else i for i in items]

    # ── ${} ──

    def _resolve_config(self, text: str, after_key: str) -> str:
        result = text
        for m in self._CONFIG_PATTERN.findall(text):
            val = self._gaming.task_manage._resolve_placeholder("${" + m + "}", after_key)
            result = result.replace("${" + m + "}", str(val) if val else "")
        return result

    # ── @{} ──

    def _resolve_exec(self, text: str) -> str:
        result = text
        for m in self._EXEC_PATTERN.findall(result):
            val = self._gaming.exec(m)
            result = result.replace("@{" + m + "}", str(val) if val is not None else "")
        return result

    # ── %{} ──

    def _resolve_context(self, text: str) -> str:
        result = text
        for m in self._CTX_PATTERN.findall(result):
            if self._is_context_expr(m):
                val = self._eval_context_expr(m)
            else:
                val = self._gaming._context.get(m, "")
            result = result.replace("%{" + m + "}", str(val) if val else "")
        return result

    # ── &{...} ──

    def _resolve_condition(self, text: str, after_key: str) -> str:
        if self._CONDITION_PATTERN.match(text):
            return str(self._eval_condition_expr(
                self._CONDITION_PATTERN.match(text).group(1)))
        result = text
        for m in self._LOG_CONDITION_PATTERN.findall(text):
            resolved_expr = self.resolve(m, after_key)
            val = self._eval_condition_expr_raw(m)
            result = result.replace("&{" + m + "}", str(val))
        return result

    # ── Expression evaluators ──

    def _eval_condition_expr(self, expr: str) -> bool:
        tokens = self._tokenize(expr)
        return self._parse_expression(tokens, condition_mode=True)

    def _eval_condition_expr_raw(self, expr: str) -> bool:
        tokens = self._tokenize(expr)
        return self._parse_expression(tokens, condition_mode=True)

    def _eval_context_expr(self, expr: str):
        tokens = self._tokenize(expr)
        return self._parse_expression(tokens, condition_mode=False)

    def _parse_expression(self, tokens: list, *, condition_mode: bool):
        pos = [0]

        def parse_or():
            left = parse_and()
            while pos[0] < len(tokens) and tokens[pos[0]] == "|":
                pos[0] += 1
                left = bool(left) or bool(parse_and())
            return left

        def parse_and():
            left = parse_cmp()
            while pos[0] < len(tokens) and tokens[pos[0]] == "&":
                pos[0] += 1
                left = bool(left) and bool(parse_cmp())
            return left

        def parse_cmp():
            left = parse_primary()
            if pos[0] < len(tokens) and tokens[pos[0]] in (">=", "<=", ">", "<", "==", "!="):
                op_token = tokens[pos[0]]
                pos[0] += 1
                right = parse_primary()
                if op_token == ">=": return float(left) >= float(right)
                if op_token == "<=": return float(left) <= float(right)
                if op_token == ">":  return float(left) > float(right)
                if op_token == "<":  return float(left) < float(right)
                if op_token == "==": return str(left) == str(right)
                if op_token == "!=": return str(left) != str(right)
            return left

        def parse_primary():
            if pos[0] >= len(tokens):
                return False
            token = tokens[pos[0]]
            pos[0] += 1
            if token == "(":
                result = parse_or()
                if pos[0] < len(tokens) and tokens[pos[0]] == ")":
                    pos[0] += 1
                return result
            try:
                if "." in token:
                    return float(token)
                return int(token)
            except (ValueError, TypeError):
                pass
            if condition_mode:
                # &{...}: 四种占位符 + 裸实体 key
                if self._CTX_PATTERN.match(token):
                    return self._gaming._context.get(
                        self._CTX_PATTERN.match(token).group(1), "")
                if self._EXEC_PATTERN.match(token):
                    return self._gaming.exec(
                        self._EXEC_PATTERN.match(token).group(1))
                if self._CONFIG_PATTERN.match(token):
                    return self._gaming.task_manage._resolve_placeholder(token)
                return self._gaming.exec(token)
            else:
                # %{...}: 仅从上下文读取
                if self._CTX_PATTERN.match(token):
                    return self._gaming._context.get(
                        self._CTX_PATTERN.match(token).group(1), "")
                return self._gaming._context.get(token, token)

        result = parse_or()
        return bool(result) if result is not None else False

    # ── Tokenizer ──

    @staticmethod
    def _tokenize(expr: str) -> list:
        tokens = []
        i = 0
        n = len(expr)
        while i < n:
            c = expr[i]
            if c.isspace():
                i += 1
                continue
            if c in "()":
                tokens.append(c)
                i += 1
            elif c == "&":
                tokens.append("&")
                i += 1
            elif c == "|":
                tokens.append("|")
                i += 1
            elif expr[i : i + 2] in (">=", "<=", "!=", "=="):
                tokens.append(expr[i : i + 2])
                i += 2
            elif c in "><":
                tokens.append(c)
                i += 1
            else:
                j = i
                while j < n and not expr[j].isspace() and expr[j] not in "()&|><=!":
                    j += 1
                tokens.append(expr[i:j])
                i = j
        return tokens

    # ── Helpers ──

    @staticmethod
    def _is_context_expr(expr: str) -> bool:
        if not expr:
            return False
        return any(op in expr for op in ("&", "|", ">=", "<=", ">", "<", "==", "!="))
```

- [ ] **Step 2: 提交**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "feat: add PlaceholderResolver class"
```

---

### Task 2: JCZXGaming 集成 — __init__ + call site 替换

**Files:**
- Modify: `jczx/jczx/jczxCli.py` — JCZXGaming 类

- [ ] **Step 1: `__init__` 中添加 `self._resolver`**

在 `self._exec_mgr = TaskExecutionManager()` 之后增加一行：

```python
self._exec_mgr = TaskExecutionManager()
self._resolver = PlaceholderResolver(self)
```

- [ ] **Step 2: `exec_func` call site 替换**

找到 `exec_func` 中的 `_on_exec` 函数（当前代码约 L406-407）：

```python
# 旧:
                args = self.task_manage.resolve_placeholders(raw_args, e.only_key)
                args = self._resolve_exec_placeholders(args)
# 新:
                args = self._resolver.resolve_list(raw_args, e.only_key)
```

- [ ] **Step 3: `exec_context` call site 替换**

找到 `exec_context` 中的 `_on_exec` 函数（当前代码约 L485-486）：

```python
# 旧:
                actions = self.task_manage.resolve_placeholders(e.action, e.only_key)
                actions = self._resolve_exec_placeholders(actions)
# 新:
                actions = self._resolver.resolve_list(e.action, e.only_key)
```

- [ ] **Step 4: `exec_ocr` call site 替换**

找到 `exec_ocr`（当前代码约 L448）：

```python
# 旧:
                target = self._resolve_placeholder(e.target)
# 新:
                target = self._resolver.resolve(e.target, e.only_key)
```

- [ ] **Step 5: `exec_click` target 解析替换**

找到 `exec_click` 的 `_on_exec` 中 target 解析（当前代码约 L544-545）：

```python
# 旧:
                target = self._resolve_placeholder(e.target)
                target = self._resolve_exec_placeholder(target) if target else None
# 新:
                target = self._resolver.resolve(e.target, e.only_key) if e.target else None
```

- [ ] **Step 6: `exec_click` 内部条件的 call site 替换**

在 `exec_click` 的 while 循环中（当前代码约 L549-564），将条件块的 `_eval_condition` + `_format_condition` 替换为统一调用：

```python
# 旧:
                while True:
                    self._exec_mgr.token.check()
                    if e.condition_not:
                        cond_result = self._eval_condition(e.condition_not)
                        if not cond_result:
                            self.log.debug(f"条件 {self._format_condition(e.condition_not, cond_result)} 满足 condition_not，执行 condition_then {e.condition_then}")
                            for s in entity.condition_then: result = self.exec(s)
                        else:
                            self.log.debug(f"条件 {self._format_condition(e.condition_not, cond_result)} 不满足 condition_not，执行 condition_else {e.condition_else}")
                            for s in entity.condition_else: result = self.exec(s)
                        break
                    elif e.condition:
                        cond_result = self._eval_condition(e.condition)
                        if cond_result:
                            self.log.debug(f"条件 {self._format_condition(e.condition, cond_result)} 满足 condition，执行 condition_then {e.condition_then}")
                            for s in entity.condition_then: result = self.exec(s)
                        else:
                            self.log.debug(f"条件 {self._format_condition(e.condition, cond_result)} 不满足 condition，执行 condition_else {e.condition_else}")
                            for s in entity.condition_else: result = self.exec(s)
                        break

# 新:
                while True:
                    self._exec_mgr.token.check()
                    if e.condition_not:
                        if self._resolver.resolve(e.condition_not, e.only_key) != "True":
                            self.log.debug(f"条件 {e.condition_not} 满足 condition_not，执行 condition_then {e.condition_then}")
                            for s in entity.condition_then: result = self.exec(s)
                        else:
                            self.log.debug(f"条件 {e.condition_not} 不满足 condition_not，执行 condition_else {e.condition_else}")
                            for s in entity.condition_else: result = self.exec(s)
                        break
                    elif e.condition:
                        if self._resolver.resolve(e.condition, e.only_key) == "True":
                            self.log.debug(f"条件 {e.condition} 满足 condition，执行 condition_then {e.condition_then}")
                            for s in entity.condition_then: result = self.exec(s)
                        else:
                            self.log.debug(f"条件 {e.condition} 不满足 condition，执行 condition_else {e.condition_else}")
                            for s in entity.condition_else: result = self.exec(s)
                        break
```

- [ ] **Step 7: `exec_condition` call site 替换**

找到 `exec_condition` 的 `_on_exec` 函数（当前代码约 L501-522），替换为：

```python
        def _on_exec(e: JczxSectionEntity):
            result = None
            if e.condition_not:
                if self._resolver.resolve(e.condition_not, e.only_key) != "True":
                    self.log.debug(f"条件 {e.condition_not} 满足 condition_not，执行 condition_then {e.condition_then}")
                    for s in e.condition_then:
                        result = self.exec(s)
                else:
                    self.log.debug(f"条件 {e.condition_not} 不满足 condition_not，执行 condition_else {e.condition_else}")
                    for s in e.condition_else:
                        result = self.exec(s)
            elif e.condition:
                if self._resolver.resolve(e.condition, e.only_key) == "True":
                    self.log.debug(f"条件 {e.condition} 满足 condition，执行 condition_then {e.condition_then}")
                    for s in e.condition_then:
                        result = self.exec(s)
                else:
                    self.log.debug(f"条件 {e.condition} 不满足 condition，执行 condition_else {e.condition_else}")
                    for s in e.condition_else:
                        result = self.exec(s)
            return result
```

- [ ] **Step 8: `_log_message` call site 替换**

找到 `_log_message` 方法（当前代码约 L747-758），替换为：

```python
    def _log_message(self, entity: JczxSectionEntity) -> None:
        if not entity.log:
            return
        msg = self._resolver.resolve(entity.log, entity.only_key)
        log_fn = getattr(self.log, entity.log_level, self.log.info)
        log_fn(f"[{entity.get_task_name() or entity.only_key}] {msg}")
```

- [ ] **Step 9: 提交**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "refactor: integrate PlaceholderResolver into JCZXGaming call sites"
```

---

### Task 3: 删除旧方法和清理

**Files:**
- Modify: `jczx/jczx/jczxCli.py` — JCZXGaming 类

- [ ] **Step 1: 删除所有旧方法/属性**

搜索并删除以下所有方法（均在 JCZXGaming 类内部）：

```python
# 删除这些类属性（正则常量，约 L193-197）:
    _EXEC_PLACEHOLDER_PATTERN = re.compile(...)
    _CTX_PLACEHOLDER_PATTERN = re.compile(...)
    _CONDITION_EXPR_PATTERN = re.compile(...)
    _LOG_CONDITION_PATTERN = re.compile(...)
    _CONFIG_PLACEHOLDER_PATTERN = re.compile(...)

# 删除这些方法:
    def _eval_condition(self, ...)       # ~L199-206
    def _eval_condition_expr(self, ...)  # ~L208-279
    def _eval_context_expr(self, ...)    # ~L281-340
    def _tokenize_condition(self, ...)   # ~L344-374
    def _resolve_exec_placeholders(...)  # ~L376-381
    def _resolve_exec_placeholder(...)   # ~L383-409
    def _is_context_expr(...)            # ~L424-428
    def _resolve_placeholder(self, ...)  # ~L842-843
    def parse_placeholder(self, ...)     # ~L845-846
    def _resolve_log_condition_placeholders(...)  # ~L772-789
    def _format_condition(self, ...)     # ~L759-770
```

**删除后验证：** 搜索以下名称，确认在文件中均已消失：
- `_eval_condition`（不含 `expre`）
- `_tokenize_condition`
- `_resolve_exec_placeholder`
- `_format_condition`
- `_resolve_log_condition_placeholders`
- `parse_placeholder`
- `_EXEC_PLACEHOLDER_PATTERN`
- `_CONDITION_EXPR_PATTERN`
- `_LOG_CONDITION_PATTERN`
- `_CONFIG_PLACEHOLDER_PATTERN`
- `_CTX_PLACEHOLDER_PATTERN`

**保留确认：** 搜索 `_CONFIG_PLACEHOLDER_PATTERN` 在新代码中只出现在 `PlaceholderResolver` 类中。

- [ ] **Step 2: 提交**

```bash
git add jczx/jczx/jczxCli.py
git commit -m "refactor: remove old placeholder methods from JCZXGaming"
```

---

### Task 4: 手动验证

- [ ] **Step 1: 启动 TUI 并验证各项功能**

```powershell
.\venv\Scripts\activate
python -m jczx.jczxCli
```

验证以下场景均正常：
1. **任务启动** — 点击 Toggle 正常执行
2. **条件分支** — `condition` / `condition_not` 正确判断
3. **配置占位符** — `${}` 在函数参数中正确解析
4. **执行占位符** — `@{}` 在参数中正确执行并替换
5. **上下文占位符** — `%{}` 正确读取变量
6. **log 输出** — entity.log 中四种占位符正常显示
7. **任务停止** — 取消令牌正常工作
