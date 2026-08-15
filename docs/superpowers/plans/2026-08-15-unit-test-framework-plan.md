# 单元测试框架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 按本文档逐步实现，checkbox 跟踪。**提交规则**：按 `AGENTS.md`，功能经用户验证后再提交，本文档不包含 commit 步骤。

**Goal:** 搭建 pytest 单元测试框架，落地方案 1（纯逻辑单测 `tests/pure/`）+ 方案 3（真实配置回归 `tests/regression/`），全量通过。

**Architecture:** `tests/` 下 `pure/` 与 `regression/` 分层。`pure/` 自建最小 fixture；`regression/` 用 `conftest.py` 拷贝真实 `jczx/Config/` 到 `tmp_path`。pytest 由 `pyproject.toml` 配置导入路径。

**Tech Stack:** pytest + pytest-cov（uv dev 依赖）、cv2、numpy、标准库。

**Files:** 2 modified（`pyproject.toml`、`CLAUDE.md`）、~10 new（`tests/`）

---

### Task 1: pytest 基础设施

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`、`tests/pure/__init__.py`、`tests/regression/__init__.py`

- [ ] **Step 1: 安装 dev 依赖**

```bash
uv add --dev pytest pytest-cov
```

- [ ] **Step 2: pyproject.toml 追加 pytest 配置**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: 创建 tests/conftest.py**

```python
import shutil
from os.path import dirname, dirname as dd, join, abspath

import pytest

PROJECT_ROOT = dd(dd(abspath(__file__)))
CONFIG_DIR = join(PROJECT_ROOT, "jczx", "Config")


@pytest.fixture
def real_config_dir(tmp_path):
    """拷贝真实 jczx/Config 到临时目录（只读副本，方案3用）。"""
    dst = tmp_path / "cfg"
    shutil.copytree(CONFIG_DIR, dst)
    return str(dst)
```

- [ ] **Step 4: 创建 tests/pure/__init__.py 与 tests/regression/__init__.py（空文件）**

---

### Task 2: 方案 1 — test_config_entity.py + test_screenshot_cache.py

**Files:**
- Create: `tests/pure/test_config_entity.py`、`tests/pure/test_screenshot_cache.py`

- [ ] **Step 1: test_config_entity.py** — 类型强转 / list 拆分 / 占位符保留 / SectionType
- [ ] **Step 2: test_screenshot_cache.py** — TTL 复用 / 过期 / invalidate / **TTL=0 每次重截**（Fix B 回归）
- [ ] **Step 3: 运行** `uv run pytest tests/pure -k "config_entity or screenshot_cache" -q` 通过

---

### Task 3: 方案 1 — test_match_transform.py + test_config_utils.py

**Files:**
- Create: `tests/pure/test_match_transform.py`、`tests/pure/test_config_utils.py`

- [ ] **Step 1: test_match_transform.py** — `MatchTemplete.transform` 算子数学 / 链式 / 非法 action
- [ ] **Step 2: test_config_utils.py** — TxtConfig roundtrip / merge index=-1 / **save 双写回归**（Fix B）
- [ ] **Step 3: 运行** `uv run pytest tests/pure -k "match_transform or config_utils" -q` 通过

---

### Task 4: 方案 1 — test_placeholder_resolver.py

**Files:**
- Create: `tests/pure/test_placeholder_resolver.py`

- [ ] **Step 1:** 用 stub `gaming`（`_context`/`exec`/`task_manage._resolve_placeholder`）测四类占位符解析顺序、`resolve_list`、条件求值
- [ ] **Step 2: 运行** `uv run pytest tests/pure -k placeholder -q` 通过

---

### Task 5: 方案 3 — test_config_loading.py

**Files:**
- Create: `tests/regression/test_config_loading.py`

- [ ] **Step 1:** `TaskManage(real_config_dir)` 加载真实配置副本，断言关键实体存在、`type: file` 合并、`extend` 继承、跨文件占位符解析
- [ ] **Step 2: 运行** `uv run pytest tests/regression -k config_loading -q` 通过

---

### Task 6: 方案 3 — test_save_task_values.py（Fix A/B 回归）

**Files:**
- Create: `tests/regression/test_save_task_values.py`

- [ ] **Step 1:** 外部任务 `task-favor` 保存 → MainMenu 不被污染、Favor.txt 写入、重载解析新值、无冲突
- [ ] **Step 2:** 原生任务 `emu` 保存 → MainMenu 回写、无重复、无外部泄漏
- [ ] **Step 3: 运行** `uv run pytest tests/regression -q` 通过

---

### Task 7: 全量验证 + 文档同步

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新 CLAUDE.md** — 常用命令加入 `uv run pytest`，修正"无测试套件/不要运行 pytest"表述，注明 `tests/pure` 与 `tests/regression` 分层
- [ ] **Step 2: 全量运行** `uv run pytest -q`，全部通过
- [ ] **Step 3: 交由用户在 TUI 环境确认后提交**
