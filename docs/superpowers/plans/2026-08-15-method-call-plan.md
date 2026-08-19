# method / call 可复用参数化执行链 Implementation Plan

> **For agentic workers:** 按本文档逐步实现，checkbox 跟踪。**提交规则**：按 `AGENTS.md`，功能经用户验证后再提交。

**Goal:** 引入 `type: method`（可复用参数化链）+ `type: call`（kwargs 绑定调用）+ `context.values`（批量初始化），用配置减少重复执行链。

**Architecture:** 在现有 `_exec_entity` 模板与占位符解析之上新增两个 exec 方法；参数绑定复用全局 context。新增回归测试。

**Tech Stack:** 现有引擎（无新依赖）。

**Files:** 2 modified（`configEntity.py`、`jczxCli.py`），1 new（`tests/engine/test_method_call.py`），2 modified（`TASK_CONFIG_GUIDE.md`、`CLAUDE.md`）

---

### Task 1: configEntity — 类型与字段

**Files:**
- Modify: `jczx/configEntity.py`

- [ ] **Step 1:** `SectionType` 新增 `METHOD = "method"`、`CALL = "call"`
- [ ] **Step 2:** `JczxSectionEntity` 新增字段：`fn: str = None`、`params: list[str] = field(default_factory=list)`、`param_defaults: list[str] = field(default_factory=list)`、`values: list[str] = field(default_factory=list)`

---

### Task 2: jczxCli — exec_method / exec_call / context.values

**Files:**
- Modify: `jczx/jczxCli.py`

- [ ] **Step 1:** `exec` 分发器新增 `case SectionType.METHOD` / `case SectionType.CALL`
- [ ] **Step 2:** `exec_method`：与 exec_task 同构，跑 action 链，复用 `_exec_entity`
- [ ] **Step 3:** `_parse_kv` 静态方法：解析 `k=v` 列表为 dict
- [ ] **Step 4:** `exec_call`：解析 args（位置参数按 params 顺序 + kwargs 混用）→ 合并 param_defaults → 对照 params 校验（warning）→ context_set 逐个绑定 → `self.exec(fn)`
- [ ] **Step 5:** `exec_context` 支持 `values` 批量初始化
- [ ] **Step 6:** `py_compile` 通过

---

### Task 3: 图片缓冲池 — 懒加载兜底

**Files:**
- Modify: `jczx/taskManage.py`

- [ ] **Step 1:** `get_img` 池未命中时懒加载（`_load_img_to_pool` 兜底）
- [ ] **Step 2:** 运行既有 `tests/regression` 确认无回归

---

### Task 4: 回归测试

**Files:**
- Create: `tests/engine/test_method_call.py`

- [ ] **Step 1:** method 执行 body 链
- [ ] **Step 2:** call kwargs 绑定进 context、body 读 `%{param}`
- [ ] **Step 3:** 参数校验（缺失/多余 warning）
- [ ] **Step 4:** param_defaults 默认值 + 调用覆盖
- [ ] **Step 5:** 嵌套调用（method body 内 call 另一个 method）
- [ ] **Step 6:** context.values 批量初始化
- [ ] **Step 7:** 运行通过

---

### Task 5: 文档 + 全量验证

**Files:**
- Modify: `TASK_CONFIG_GUIDE.md`、`CLAUDE.md`

- [ ] **Step 1:** `TASK_CONFIG_GUIDE.md` 增 method/call/context.values 语法与示例
- [ ] **Step 2:** `CLAUDE.md` 提及 method/call
- [ ] **Step 3:** 全量 `uv run pytest -q` 通过
- [ ] **Step 4:** 交由用户验证后提交
