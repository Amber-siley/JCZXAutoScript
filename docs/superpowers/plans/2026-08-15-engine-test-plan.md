# 引擎级测试（方案 2） Implementation Plan

> **For agentic workers:** 按本文档逐步实现，checkbox 跟踪。**提交规则**：按 `AGENTS.md`，功能经用户验证后再提交，本文档不包含 commit 步骤。

**Goal:** 用 FakeDevice 桩替身测试执行引擎（`tests/engine/`），先落地 `test_exec_entity` + `test_exec_match` 两个高价值文件，基础设施 + 其余文件逐步补齐。

**Architecture:** `tests/engine/fake_device.py` 提供 harness（`object.__new__(JCZXGaming)` 绕过 ADB + `FakeMatcher`/`FakeToken`/`make_match`），`conftest.py` 暴露 fixture。复用根 conftest 的 `real_config_dir`。

**Tech Stack:** pytest、cv2、numpy、标准库。

**Files:** ~8 new（`tests/engine/`），1 modified（`CLAUDE.md`）

---

### Task 1: 引擎测试基础设施

**Files:**
- Create: `tests/engine/__init__.py`、`tests/engine/fake_device.py`、`tests/engine/conftest.py`

- [ ] **Step 1: 创建 `tests/engine/fake_device.py`** — `make_match` / `FakeMatcher` / `FakeToken` / `make_gaming`
- [ ] **Step 2: 创建 `tests/engine/conftest.py`** — 暴露 `gaming`（带 matcher/clicks）fixture
- [ ] **Step 3: 冒烟**：`uv run pytest tests/engine -q` 能收集到 0 测试不报错

---

### Task 2: test_exec_entity.py

**Files:**
- Create: `tests/engine/test_exec_entity.py`

- [ ] **Step 1:** `times` 循环执行 action 链
- [ ] **Step 2:** `testFor_before` 门控（命中/未命中）
- [ ] **Step 3:** `wait_target` + `wait_target_sleep`（FakeToken 记录 sleep 时长）
- [ ] **Step 4:** action 链按序执行 + `testFor_after` 重试
- [ ] **Step 5: 运行** `uv run pytest tests/engine/test_exec_entity.py -q` 通过

---

### Task 3: test_exec_match.py

**Files:**
- Create: `tests/engine/test_exec_match.py`

- [ ] **Step 1:** 级联匹配 — `FakeMatcher.calls` 断言 cutPoints 为 action 变换后区域
- [ ] **Step 2:** action 变换 — 返回的 MatchTemplete 点 == 变换后坐标
- [ ] **Step 3:** 标注时机 — RecordingRecorder 断言 `on_match` 收到变换后点（回归标注修复）
- [ ] **Step 4: 运行** `uv run pytest tests/engine/test_exec_match.py -q` 通过

---

### Task 4: 全量验证 + 文档同步

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 全量运行** `uv run pytest -q`，全部通过
- [ ] **Step 2: CLAUDE.md** 测试章节补充 `tests/engine` 说明
- [ ] **Step 3: 交由用户在 TUI 环境确认后提交**
