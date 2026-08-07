# taskView 可视化配置编辑器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 taskView 只读流程图可视化上扩展为可视化配置编辑器——通过表单 + 图联动完成实体字段编辑、实体增删复制、图结构编辑，严格校验后行级 patch 原子写回。

**Architecture:** 后端 `taskView/editor.py` 提供 `ConfigEditor`（行级 patch 写回，保留注释/空行/顺序）与严格校验层；`server.py` 新增实体池 / 预校验 / 应用变更三个 API；前端 `index.html` 在只读图上叠加编辑表单、草稿暂存与自动补全。保存 = 变更集一次校验、一次原子提交。

**Tech Stack:** Python 3.14 · FastAPI · uvicorn · Textual（仅复用 jczx 解析）· 前端 Cytoscape.js（CDN，零构建）。依赖由根 `pyproject.toml`（uv）统一管理。

## Global Constraints

- **无测试套件**：AGENTS.md 禁止运行 pytest/ruff/mypy。本计划用临时自检脚本 `taskView/_dev_check.py`（纯 `assert`，`uv run python` 执行）替代 pytest；Task 5 完成后删除。
- **uv 运行**：`uv run python -m taskView`；不创建独立 sde 虚拟环境。
- **零侵入**：不修改 `jczx/` 下任何文件；只新增/修改 `taskView/` 与文档。
- **实体文件格式**：`key : value`（冒号分隔）；实体文件无行内注释，注释均在行首 `/` 或 `//`；value 到行尾（可能以 `/` 开头，如 `action: /|%{simulate_times}`，**不得按注释切分**）。
- **编辑范围**：仅 `MainMenu.txt` 与 `tasks/*.txt`，不含 `Config.txt` / `Queues.txt`。
- **git 提交**：功能须经用户验证后再提交；提交格式 `[emoji: 中文信息]`。
- **写回原子性**：临时文件 + `os.replace`，不留半文件。

---

## 文件结构

| 文件 | 职责 | 变更 |
|------|------|------|
| `taskView/editor.py` | 新增：ConfigEditor 行级 patch + 严格校验层 | Create |
| `taskView/_dev_check.py` | 新增：临时自检脚本（纯 assert，Task 5 删除） | Create + Delete |
| `taskView/server.py` | 新增 3 个 API 端点 | Modify |
| `taskView/static/index.html` | 前端编辑交互：表单、草稿、自动补全、工具栏 | Modify |
| `taskView/README.md` | 更新运行方式（uv）与功能说明 | Modify |

---

## 接口契约（跨任务引用）

以下签名在 Task 1/2 定义，Task 3/4/5 引用，实现者不得改名。

```python
# ---- taskView/editor.py ----
CONFIG_DIR: str          # jczx/Config 绝对路径
RESOURCES_DIR: str       # jczx/resources 绝对路径

class ConfigEditor:
    def __init__(self, path: str) -> None
    def load(self) -> None                      # 解析文件为行模型
    @property
    def text(self) -> str                       # 当前完整文本（行以 \n 连接）
    @property
    def sections(self) -> list[str]             # 当前 section 列表（有序）
    def update_value(self, key: str, option: str, value: str) -> None
    def add_entity(self, key: str, fields: dict[str, str]) -> None
    def delete_entity(self, key: str) -> None
    def rename_entity(self, old: str, new: str) -> None
    def save(self) -> None                      # 原子写回

def file_hash(path: str) -> str                 # sha1 十六进制
def load_entity_pool() -> tuple[dict[str, JczxSectionEntity], dict[str, str]]
    # 返回 (entity_pool: key->实体，跨 MainMenu+tasks 全部；entity_file: key->定义文件路径)
def simulate_and_validate(pool, entity_file, file: str, ops: list[dict]) -> tuple[list[tuple[str, list[str]]], list[dict]]
    # 返回 (writes: [(路径, 新行列表), ...]；errors: [ValidationError, ...])。ops 非法则抛 ValueError。
# ValidationError = {"file": str, "key": str, "field": str, "message": str}
```

**ops 变更集格式**（前端 → 后端，所有字段值均为字符串）：
```json
{"type": "update", "key": "click-mail", "fields": {"sleep": "2"}}
{"type": "create", "key": "new-entity", "entity": {"type": "click", "target": "buttons\\x.png"}}
{"type": "delete", "key": "click-claimAll"}
{"type": "rename", "old": "old-key", "new": "new-key"}
```

---

### Task 1: ConfigEditor —— 行级 patch 解析与写回

**Files:**
- Create: `taskView/editor.py`（本任务只含 ConfigEditor 部分，校验层留 Task 2）
- Test: `taskView/_dev_check.py`

**Interfaces:**
- Produces: `ConfigEditor` 全部方法（契约见上）、`file_hash`

- [ ] **Step 1: 写临时自检脚本（先断言核心行为）**

创建 `taskView/_dev_check.py`：

```python
"""临时自检脚本（非 pytest）。uv run python taskView/_dev_check.py"""
import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.editor import ConfigEditor, file_hash

SAMPLE = (
    "/ 主菜单\n"
    "\n"
    "[goto-home]\n"
    "type: click\n"
    "name: 回家\n"
    "target: buttons\\home.png\n"
    "sleep: 1\n"
    "[click-mail]\n"
    "type: click\n"
    "target: buttons\\mail.png\n"
)

def make() -> str:
    fd, path = tempfile.mkstemp(suffix=".txt", dir=tempfile.gettempdir())
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(SAMPLE)
    return path

def test_parse():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    assert ed.sections == ["goto-home", "click-mail"], ed.sections
    os.unlink(p)

def test_update_preserves_comment_and_chain():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    ed.update_value("click-mail", "target", "buttons\\new.png")
    text = ed.text
    assert "target: buttons\\new.png\n" in text, text
    assert "/ 主菜单\n" in text, text          # 行首注释保留
    os.unlink(p)

def test_add_and_delete():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    ed.add_entity("new-click", {"type": "click", "target": "buttons\\a.png"})
    assert "[new-click]\n" in ed.text
    ed.delete_entity("new-click")
    assert "[new-click]" not in ed.text
    assert "/ 主菜单\n" in ed.text             # 注释保留为孤立注释
    os.unlink(p)

def test_rename():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    ed.rename_entity("goto-home", "goto-main")
    assert "[goto-main]\n" in ed.text
    assert "[goto-home]" not in ed.text
    os.unlink(p)

def test_save_atomic_and_hash():
    p = make()
    h1 = file_hash(p)
    ed = ConfigEditor(p)
    ed.load()
    ed.update_value("goto-home", "sleep", "2")
    ed.save()
    assert file_hash(p) != h1
    with open(p, encoding="utf-8") as f:
        assert "sleep: 2\n" in f.read()
    os.unlink(p)

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
```

- [ ] **Step 2: 运行自检脚本确认失败**

Run: `uv run python taskView/_dev_check.py`
Expected: FAIL — `ModuleNotFoundError: taskView.editor`（模块尚不存在）

- [ ] **Step 3: 实现 ConfigEditor**

创建 `taskView/editor.py`：

```python
"""taskView 可视化配置编辑器后端：行级 patch 写回（保留注释/空行/顺序） + 严格校验。

ConfigEditor 只处理实体文件（MainMenu.txt / tasks/*.txt）。已验证实体文件无行内注释，
注释均在行首 `/` 或 `//`；value 到行尾（可能以 `/` 开头，如 `action: /|%{x}`），不按注释切分。
"""
import os
import re
import tempfile
from hashlib import sha1
from typing import Optional

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jczx", "Config")
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jczx", "resources")

_SECTION_RE = re.compile(r"^\s*\[(?P<section>[^\]\r\n]+)\]\s*$")
# 兼容 TxtConfig：key 不含冒号，chain 为任意空白:空白，value 到行尾（去尾空白）
_OPTION_RE = re.compile(r"^(?P<key>[^:\r\n]+?)\s*(?P<chain>:)(?P<value>.*?)\s*$")


class _EntityModel:
    """单个实体 section 的行模型。"""
    __slots__ = ("name", "header_idx", "option_lines")

    def __init__(self, name: str, header_idx: int):
        self.name = name                # section 名（key）
        self.header_idx = header_idx    # section 头行索引
        self.option_lines = []          # 该 section 内 option 行索引（有序）


class ConfigEditor:
    def __init__(self, path: str):
        self.path = path
        self._lines: list[str] = []                 # 原始行（不含换行符）
        self._entities: list[_EntityModel] = []     # 有序实体
        self._entity_by_name: dict[str, _EntityModel] = {}

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as fp:
            self._lines = [ln.rstrip("\r\n") for ln in fp.readlines()]
        self._entities = []
        self._entity_by_name = {}
        cur: Optional[_EntityModel] = None
        for i, line in enumerate(self._lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("/"):
                continue                        # blank / 行首注释，跳过
            m = _SECTION_RE.match(line)
            if m:
                cur = _EntityModel(m.group("section").strip(), i)
                self._entities.append(cur)
                self._entity_by_name[cur.name] = cur
                continue
            m = _OPTION_RE.match(line)
            if m and cur is not None:
                cur.option_lines.append(i)

    @property
    def text(self) -> str:
        return "\n".join(self._lines) + ("\n" if self._lines else "")

    @property
    def sections(self) -> list[str]:
        return [e.name for e in self._entities]

    def _entity(self, key: str) -> _EntityModel:
        if key not in self._entity_by_name:
            raise ValueError(f"实体不存在: {key}")
        return self._entity_by_name[key]

    def update_value(self, key: str, option: str, value: str) -> None:
        ent = self._entity(key)
        for i in ent.option_lines:
            m = _OPTION_RE.match(self._lines[i])
            if m and m.group("key").strip() == option:
                # 保留原行 key+chain 前缀，只替换 value
                head = self._lines[i][: self._lines[i].find(m.group("value"))]
                self._lines[i] = head.rstrip() + " " + value
                return
        raise ValueError(f"实体 {key} 无字段 {option}")

    def add_option(self, key: str, option: str, value: str) -> None:
        """在实体末尾追加一个 option 行。

        用于 extend 实体的继承字段更新落盘：文件里没有该 option 行时，
        update_value 会抛 ValueError，此方法把字段行追加到 section 末尾。
        """
        ent = self._entity(key)
        insert_at = ent.option_lines[-1] + 1 if ent.option_lines else ent.header_idx + 1
        self._lines.insert(insert_at, f"{option}: {value}")
        self.load()

    def add_entity(self, key: str, fields: dict[str, str]) -> None:
        if key in self._entity_by_name:
            raise ValueError(f"实体已存在: {key}")
        lines = ["", f"[{key}]"]
        for opt, val in fields.items():
            lines.append(f"{opt}: {val}")
        # 追加到文件末尾；若文件末尾无空行则补一个空行分隔
        if self._lines and self._lines[-1].strip():
            self._lines.append("")
        self._lines.extend(lines)
        self.load()  # 重建索引

    def delete_entity(self, key: str) -> None:
        ent = self._entity(key)
        drop = {ent.header_idx, *ent.option_lines}
        self._lines = [ln for i, ln in enumerate(self._lines) if i not in drop]
        self.load()

    def rename_entity(self, old: str, new: str) -> None:
        if new in self._entity_by_name:
            raise ValueError(f"实体已存在: {new}")
        ent = self._entity(old)
        self._lines[ent.header_idx] = re.sub(r"\[[^\]]+\]", f"[{new}]", self._lines[ent.header_idx])
        self.load()

    def save(self) -> None:
        dirn = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(prefix=".jczx-edit-", suffix=".tmp", dir=dirn)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(self.text)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def file_hash(path: str) -> str:
    h = sha1()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```

- [ ] **Step 4: 运行自检脚本确认通过**

Run: `uv run python taskView/_dev_check.py`
Expected: `ALL PASS`

- [ ] **Step 5: 提交（先请用户验证 Task 1 后再提交）**

```bash
git add taskView/editor.py taskView/_dev_check.py
git commit -m ":sparkles: taskView ConfigEditor 行级 patch 写回"
```

---

### Task 2: 校验层 —— 实体池加载、模拟应用、严格校验

**Files:**
- Modify: `taskView/editor.py`（追加校验层）
- Test: `taskView/_dev_check.py`（追加断言）

**Interfaces:**
- Consumes: `JczxSectionEntity`、`SectionType`（`jczx.configEntity`）、`TxtConfig`（`jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils`）、`ConfigEditor`（Task 1）
- Produces: `load_entity_pool`、`simulate_and_validate`（契约见上）

- [ ] **Step 1: 追加自检断言**

在 `taskView/_dev_check.py` 末尾追加：

```python
from taskView.editor import load_entity_pool, simulate_and_validate

def test_load_pool():
    pool, efile = load_entity_pool()
    assert "goto-home" in pool or "click-center" in pool, "MainMenu 公共实体应存在"
    assert len(pool) > 5
    # 每个实体都能定位到定义文件
    assert all(k in efile for k in pool)

def test_validate_bad_ref_and_dup():
    pool, efile = load_entity_pool()
    # update 一个 action 指向不存在实体 -> 应报错
    writes, errors = simulate_and_validate(pool, efile, "tasks/receive.txt", [
        {"type": "update", "key": "task-receive-everyday", "fields": {"action": "no-such-entity"}}
    ])
    assert errors, "应产生引用错误"
    assert any("no-such-entity" in e["message"] for e in errors)
    assert writes == [], "校验失败时不得产生写回"

def test_validate_ok_and_create():
    pool, efile = load_entity_pool()
    writes, errors = simulate_and_validate(pool, efile, "tasks/receive.txt", [
        {"type": "create", "key": "_zz_dev_new", "entity": {"type": "click", "target": "buttons\\home.png"}},
        {"type": "delete", "key": "_zz_dev_new"},
    ])
    assert not errors, errors
    assert writes, "应产生写回"
```

- [ ] **Step 2: 运行确认新断言失败**

Run: `uv run python taskView/_dev_check.py`
Expected: FAIL — `ImportError: cannot import name 'load_entity_pool'`

- [ ] **Step 3: 实现校验层**

在 `taskView/editor.py` 末尾追加：

```python
from jczx.configEntity import JczxSectionEntity, SectionType
from jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig
from jczx.jczxCli import JCZXGaming

_REF_FIELDS = ("action", "condition", "condition_not", "condition_then",
               "condition_else", "extend", "match")
_PLACEHOLDER_RE = re.compile(r"\$\{[^}]*\}|@\{[^}]*\}|%\{[^}]*\}|&\{[^}]*\}")


def _is_editable_file(file: str) -> bool:
    """可编辑文件范围：MainMenu.txt 或 tasks/ 下 .txt；排除 Config.txt/Queues.txt。"""
    return file.endswith(".txt") and (file == "MainMenu.txt" or file.startswith("tasks/"))


def load_entity_pool() -> tuple[dict[str, JczxSectionEntity], dict[str, str]]:
    """加载 MainMenu.txt + tasks/*.txt 全部实体，返回 (pool, entity_file)。跨文件重名抛 ValueError。"""
    pool: dict[str, JczxSectionEntity] = {}
    entity_file: dict[str, str] = {}

    def _load(path: str, seen: set[str]) -> None:
        path = os.path.normpath(path)
        if path in seen or not os.path.isfile(path):
            return
        seen.add(path)
        cfg = TxtConfig(path)
        for key, ent in cfg.trans_entity_dict(JczxSectionEntity).items():
            if key in pool:
                raise ValueError(f"跨文件实体重名: {key}")
            pool[key] = ent
            entity_file[key] = path
            if ent.type == SectionType.FILE.value:
                sub = os.path.join(os.path.dirname(path),
                                   (getattr(ent, "target", "") or "").replace("/", os.sep))
                _load(sub, seen)

    _load(os.path.join(CONFIG_DIR, "MainMenu.txt"), set())
    tasks_dir = os.path.join(CONFIG_DIR, "tasks")
    if os.path.isdir(tasks_dir):
        for name in sorted(os.listdir(tasks_dir)):
            if name.endswith(".txt"):
                _load(os.path.join(tasks_dir, name), set())
    for key, ent in pool.items():
        ent.only_key = key
    return pool, entity_file


def _apply_field(ent: JczxSectionEntity, field: str, value: str, errors: list[dict]) -> None:
    """把字符串值设置到实体字段，复用 __setattr__ 类型转换；失败记错误。"""
    if field not in ent.__dataclass_fields__:
        errors.append({"file": ent.only_key or "", "key": ent.only_key or "",
                       "field": field, "message": f"未知字段: {field}"})
        return
    try:
        setattr(ent, field, value)
    except Exception as e:
        errors.append({"file": ent.only_key or "", "key": ent.only_key or "",
                       "field": field, "message": f"字段类型错误: {e}"})


def _validate_entity(pool: dict[str, JczxSectionEntity], key: str,
                     ent: JczxSectionEntity, resources_dir: str) -> list[dict]:
    errors: list[dict] = []
    e = {"file": "", "key": key, "field": "", "message": ""}

    if ent.type and not SectionType.__contains__(ent.type):
        return [{**e, "message": f"非法 type: {ent.type}"}]

    for f in _REF_FIELDS:
        val = getattr(ent, f, None)
        if isinstance(val, str) and val and val not in pool:
            errors.append({**e, "field": f, "message": f"引用实体不存在: {val}"})
        elif isinstance(val, list):
            for item in val:
                if item and item not in pool:
                    errors.append({**e, "field": f, "message": f"引用实体不存在: {item}"})

    settings = getattr(ent, "settings", None)
    if settings and settings in pool and pool[settings].type != SectionType.SETTINGS.value:
        errors.append({**e, "field": "settings", "message": f"{settings} 不是 settings 实体"})

    target = getattr(ent, "target", "") or ""
    if ent.type in (SectionType.CLICK.value, SectionType.MATCH.value, SectionType.OCR.value) \
            and target and "${" not in target:
        img = os.path.join(resources_dir, target.replace("\\", os.sep))
        if not os.path.isfile(img):
            errors.append({**e, "field": "target", "message": f"图片资源不存在: {target}"})

    func = getattr(ent, "func", "") or ""
    if ent.type == SectionType.FUNC.value and func and not hasattr(JCZXGaming, func):
        errors.append({**e, "field": "func", "message": f"JCZXGaming 无方法: {func}"})

    return errors


def _validate_pool(pool: dict[str, JczxSectionEntity], resources_dir: str) -> list[dict]:
    errors: list[dict] = []
    for key, ent in pool.items():
        errors.extend(_validate_entity(pool, key, ent, resources_dir))
    return errors


def simulate_and_validate(pool, entity_file, file: str, ops: list[dict]) -> tuple[list[tuple[str, list[str]]], list[dict]]:
    """模拟应用 ops → 校验 → 返回 (writes, errors)。ops 结构非法抛 ValueError。"""
    if not _is_editable_file(file):
        raise ValueError(f"不可编辑文件: {file}")

    # 目标文件路径 + 复制实体池（避免污染加载结果）
    target_path = os.path.join(CONFIG_DIR, *file.split("/"))
    new_pool = dict(pool)
    errors: list[dict] = []
    touched: dict[str, set] = {}   # 文件路径 -> 涉及实体 key 集合（用于生成 writes）

    def _touch(path: str, key: str) -> None:
        touched.setdefault(path, set()).add(key)

    for op in ops:
        t = op.get("type")
        if t == "update":
            key = op["key"]
            if key not in new_pool:
                errors.append({"file": file, "key": key, "field": "", "message": f"实体不存在: {key}"})
                continue
            ent = new_pool[key]
            for field, value in op.get("fields", {}).items():
                _apply_field(ent, field, value, errors)
            _touch(entity_file[key], key)
        elif t == "create":
            key = op["key"]
            if key in new_pool:
                errors.append({"file": file, "key": key, "field": "", "message": f"实体已存在: {key}"})
                continue
            ent = JczxSectionEntity()
            for field, value in op.get("entity", {}).items():
                _apply_field(ent, field, value, errors)
            if not ent.type:
                errors.append({"file": file, "key": key, "field": "type", "message": "缺少 type"})
            new_pool[key] = ent
            _touch(target_path, key)
        elif t == "delete":
            key = op["key"]
            if key not in new_pool:
                errors.append({"file": file, "key": key, "field": "", "message": f"实体不存在: {key}"})
                continue
            del new_pool[key]
            _touch(entity_file[key], key)
        elif t == "rename":
            old, new = op["old"], op["new"]
            if old not in new_pool or new in new_pool:
                errors.append({"file": file, "key": old, "field": "",
                               "message": "重命名失败（源不存在或目标已存在）"})
                continue
            old_path = entity_file[old]
            new_pool[new] = new_pool.pop(old)
            _touch(old_path, new)
            # 同步更新所有引用 old 的字段
            for other_key, other in new_pool.items():
                changed = False
                for f in _REF_FIELDS:
                    val = getattr(other, f, None)
                    if isinstance(val, str) and val == old:
                        setattr(other, f, new); changed = True
                    elif isinstance(val, list) and old in val:
                        setattr(other, f, [new if x == old else x for x in val]); changed = True
                if changed:
                    _touch(entity_file[other_key], other_key)
        else:
            raise ValueError(f"未知变更类型: {t}")

    # 严格校验（模拟后快照）
    errors.extend(_validate_pool(new_pool, RESOURCES_DIR))

    if errors:
        return [], errors

    # 生成写回：每个受影响文件用 ConfigEditor 应用涉及实体的字段变更
    writes: list[tuple[str, list[str]]] = []
    for path, keys in touched.items():
        ed = ConfigEditor(path)
        ed.load()
        for key in sorted(keys):
            ent = new_pool.get(key)
            if ent is None:
                ed.delete_entity(key)
                continue
            if key not in ed.sections:
                fields = {f: str(getattr(ent, f)) for f in ent.__dataclass_fields__
                          if getattr(ent, f) is not None
                          and getattr(ent, f) != getattr(JczxSectionEntity(), f)
                          and f not in ("only_key", "context_default_type")}
                ed.add_entity(key, fields)
                continue
            for f in ent.__dataclass_fields__:
                if f in ("only_key", "extend", "context_default_type"):
                    continue
                val = getattr(ent, f)
                if val is None:
                    continue
                if isinstance(val, list):
                    val = ",".join(str(x) for x in val)
                else:
                    val = str(val)
                try:
                    try:
                        ed.update_value(key, f, val)
                    except ValueError:
                        ed.add_option(key, f, val)  # 文件无此字段行 → 追加（extend 继承字段落盘）
        writes.append((path, ed.text))
    return writes, []
```

> **接口锁定**：`writes` 元素为 `(path, text)` 二元组——`path` 是受影响文件的绝对路径，`text` 是该文件修改后的完整文本（`ed.text` 已带尾换行）。Task 3 用模块级 `write_text_atomic(path, text)` 原子写盘。写入由 Task 3 的 server 层完成。

- [ ] **Step 4: 运行确认通过**

Run: `uv run python taskView/_dev_check.py`
Expected: `ALL PASS`（含新增 3 个断言）

- [ ] **Step 5: 提交（先请用户验证 Task 2 后再提交）**

```bash
git add taskView/editor.py taskView/_dev_check.py
git commit -m ":sparkles: taskView 实体池加载与严格校验层"
```

---

### Task 3: server.py —— 新增三个 API

**Files:**
- Modify: `taskView/server.py`
- Test: 手动（uvicorn + curl）

**Interfaces:**
- Consumes: `load_entity_pool`、`simulate_and_validate`、`file_hash`、`ConfigEditor`（Task 1/2）；`build_graph`（现有）
- Produces: `GET /api/entities`、`POST /api/file/{file}/validate`、`POST /api/file/{file}/apply`

- [ ] **Step 1: 扩展 server.py**

在 `taskView/server.py` 中追加 import 与端点：

```python
from typing import Optional
from pydantic import BaseModel
from fastapi import Body
from . import editor as ed
from .graph_builder import build_graph

class ApplyRequest(BaseModel):
    ops: list[dict]
    base_hash: Optional[str] = None


@app.get("/api/entities")
async def api_entities():
    """实体池候选列表（key + label + type），供自动补全。"""
    pool, _ = ed.load_entity_pool()
    return [{"key": k, "label": v.name or k, "type": v.type or ""} for k, v in pool.items()]


@app.post("/api/file/{file}/validate")
async def api_validate(file: str, req: ApplyRequest = Body(...)):
    pool, efile = ed.load_entity_pool()
    try:
        _, errors = ed.simulate_and_validate(pool, efile, file, req.ops)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"errors": errors}


@app.post("/api/file/{file}/apply")
async def api_apply(file: str, req: ApplyRequest = Body(...)):
    pool, efile = ed.load_entity_pool()
    target_path = os.path.join(ed.CONFIG_DIR, *file.split("/"))
    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file}")

    # 并发冲突保护：base_hash 与磁盘当前哈希不符则拒绝
    if req.base_hash and req.base_hash != ed.file_hash(target_path):
        return JSONResponse(status_code=409, content={"detail": "文件已被外部修改，请重新加载"})

    try:
        writes, errors = ed.simulate_and_validate(pool, efile, file, req.ops)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if errors:
        return JSONResponse(status_code=422, content={"errors": errors})

    written = []
    for path, new_text in writes:
        ed.write_text_atomic(path, new_text)   # writes 元素 = (path, 完整新文本)
        written.append(os.path.relpath(path, ed.CONFIG_DIR).replace(os.sep, "/"))

    graph = build_graph(file)
    return {"graph": graph, "file_hash": ed.file_hash(target_path), "written": written}
```

> **配套**：`editor.py` 追加模块级函数 `write_text_atomic`（放 `simulate_and_validate` 之后）。`writes` 元素为 `(path, text)`，Task 2 已按此产出（`ed.text` 带尾换行）：
>
> ```python
> def write_text_atomic(path: str, text: str) -> None:
>     dirn = os.path.dirname(path) or "."
>     fd, tmp = tempfile.mkstemp(prefix=".jczx-edit-", suffix=".tmp", dir=dirn)
>     try:
>         with os.fdopen(fd, "w", encoding="utf-8") as fp:
>             fp.write(text)
>         os.replace(tmp, path)
>     except Exception:
>         if os.path.exists(tmp):
>             os.unlink(tmp)
>         raise
> ```

- [ ] **Step 2: 启动服务手动验证**

Run:
```bash
uv run python -m taskView &
curl -s "http://localhost:8000/api/entities" | head -c 400
curl -s -X POST "http://localhost:8000/api/file/tasks/receive.txt/validate" -H "Content-Type: application/json" \
  -d '{"ops":[{"type":"update","key":"task-receive-everyday","fields":{"action":"no-such"}}]}'
curl -s -X POST "http://localhost:8000/api/file/tasks/receive.txt/apply" -H "Content-Type: application/json" \
  -d '{"ops":[{"type":"create","key":"_zz_curl_tmp","entity":{"type":"click","target":"buttons\\home.png"}}]}'
curl -s -X POST "http://localhost:8000/api/file/tasks/receive.txt/apply" -H "Content-Type: application/json" \
  -d '{"ops":[{"type":"delete","key":"_zz_curl_tmp"}]}'
```

Expected:
- `/api/entities` 返回实体候选列表
- validate 返回 `errors` 含 `no-such` 引用错误
- 两次 apply 各成功返回新图；第一次后 `tasks/receive.txt` 末尾出现 `_zz_curl_tmp` 实体，第二次后消失
- `git diff jczx/Config/tasks/receive.txt` 显示还原为原内容（无残留）

> 注意：apply 需要 `base_hash`，curl 测试可省略（None 跳过冲突检查）。完成后确保 `_zz_curl_tmp` 已被删除。

- [ ] **Step 3: 提交（先请用户验证 Task 3 后再提交）**

```bash
git add taskView/server.py taskView/editor.py
git commit -m ":sparkles: taskView 编辑 API（实体池/校验/应用变更）"
```

---

### Task 4: 前端 —— 编辑表单、草稿、自动补全、工具栏

**Files:**
- Modify: `taskView/static/index.html`
- Test: 手动（浏览器）

**Interfaces:**
- Consumes: `GET /api/entities`、`POST /api/file/{file}/validate`、`POST /api/file/{file}/apply`、现有 `GET /api/graph`（响应新增 `file_hash`）

- [ ] **Step 1: server 的 `/api/graph` 响应附带 `file_hash`**

在 `taskView/server.py` 的 `api_graph` 中：

```python
@app.get("/api/graph")
async def api_graph(file: str = Query(..., description="Config filename, e.g. MainMenu.txt")):
    result = build_graph(file)
    if not result["nodes"] and not result["edges"]:
        raise HTTPException(status_code=404, detail=f"File not found or empty: {file}")
    target = os.path.join(ed.CONFIG_DIR, *file.split("/"))
    result["file_hash"] = ed.file_hash(target) if os.path.isfile(target) else ""
    return result
```

- [ ] **Step 2: index.html —— 状态与草稿管理**

在 `<script>` 开头追加全局状态：

```js
let currentFile = null;      // 当前打开的配置文件（如 MainMenu.txt / tasks/receive.txt）
let baseHash = null;         // 加载时的 file_hash，保存时回传
let draftOps = [];           // 草稿变更集 [{type,key,...}]
let dirtyKeys = new Set();   // 有未保存改动的实体 key（脏标记）
let entityCandidates = [];   // /api/entities 缓存 {key,label,type}
```

新增核心 JS 函数（放在现有 `loadGraph` 附近）：

```js
async function fetchEntities() {
  entityCandidates = await (await fetch('/api/entities')).json();
}

function trackDirty(key) {
  dirtyKeys.add(key);
  const n = cy.getElementById(key);
  if (n) n.addClass('dirty');
  refreshDraftBar();
}

function refreshDraftBar() {
  const bar = document.getElementById('draft-bar');
  const count = draftOps.length;
  bar.innerHTML = count
    ? `草稿 ${count} 项 · <button onclick="saveAll()">保存</button> · <button onclick="discardAll()">放弃</button>`
    : '无未保存修改';
  bar.style.display = count ? 'flex' : 'none';
}

function discardAll() {
  draftOps = []; dirtyKeys.clear();
  cy.$('.dirty').removeClass('dirty');
  refreshDraftBar();
}

async function saveAll() {
  const res = await fetch(`/api/file/${encodeURIComponent(currentFile)}/apply`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ops: draftOps, base_hash: baseHash})
  });
  if (res.status === 409) { showBanner('文件已被外部修改，请重新加载', 'error'); return; }
  const data = await res.json();
  if (data.errors) { showErrors(data.errors); return; }
  baseHash = data.file_hash; draftOps = []; dirtyKeys.clear();
  cy.$('.dirty').removeClass('dirty');
  loadGraph(currentFile);            // 复用现有 loadGraph：重新拉图 + showAll + buildTaskList
  refreshDraftBar(); showBanner('已保存', 'ok');
}

function showBanner(msg, kind) {
  const b = document.getElementById('draft-bar');
  b.innerHTML = msg;
  b.style.display = 'flex';
  b.style.background = kind === 'error' ? '#7f1d1d' : '#0f3460';
  setTimeout(() => refreshDraftBar(), 2500);   // 提示后恢复草稿栏
}
```

- [ ] **Step 3: index.html —— 详情面板改为可编辑表单**

将 `#detail-content` 的只读渲染改为表单渲染。新增渲染函数：

```js
function buildEntityForm(detail) {
  const type = detail.type || '';
  // 字段定义：通用 + 按 type 追加
  const common = [
    ['name','显示名'], ['desc','备注'], ['action','action 链(引用)'], ['times','次数'],
    ['view','显示(view)'], ['sleep','sleep'], ['pre_sleep','pre_sleep'], ['max_wait','max_wait'],
    ['wait_target','wait_target'], ['testFor_before','testFor_before'], ['testFor_after','testFor_after'],
    ['log','log'], ['log_level','log_level'],
  ];
  const byType = {
    click: [['target','图片'], ['per','阈值'], ['pos','坐标'], ['match','match 引用'],
            ['index','index'], ['break_point','break_point'], ['condition','condition'],
            ['condition_not','condition_not'], ['condition_then','then'], ['condition_else','else']],
    match: [['target','图片'], ['per','阈值']],
    ocr:   [['target','图片'], ['match','match 引用'], ['per','阈值']],
    func:  [['func','方法'], ['args','参数']],
    condition: [['condition','条件'], ['condition_not','反向条件'],
                ['condition_then','then'], ['condition_else','else']],
    task:  [['settings','settings 引用']],
    context: [['context_get','读取'], ['context_default','默认值'], ['action','运算链'], ['context_key','存储']],
  };
  const fields = (byType[type] || []).concat(common.filter(f => !(byType[type]||[]).some(x => x[0] === f[0])));

  const html = fields.map(([k, label]) => {
    const val = detail[k] !== undefined && detail[k] !== null
      ? (Array.isArray(detail[k]) ? detail[k].join(',') : String(detail[k])) : '';
    const ref = ['action','condition','condition_not','condition_then','condition_else','match','settings','extend'].includes(k);
    const dl = ref ? `<datalist id="ref-${k}">${entityCandidates.map(c => `<option value="${c.key}">`).join('')}</datalist>` : '';
    return `<div class="field"><span class="key">${k}</span>
      <input data-field="${k}" data-orig="${val.replace(/"/g,'&quot;')}" value="${val.replace(/"/g,'&quot;')}" ${ref?'list="ref-'+k+'"':''}>
      ${dl}</div>`;
  }).join('');
  return `<div style="display:flex;gap:6px;margin-bottom:8px">
      <button onclick="addDraftEntity()">新增</button>
      <button onclick="duplicateEntity()">复制</button>
      <button onclick="deleteDraftEntity()" style="color:#ef5350">删除</button>
      <span style="margin-left:auto">type: <b>${type}</b></span></div>${html}`;
}
```

**改动现有 tap handler**：`cy.on('tap', 'node', ...)` 内的 `renderDetail(detail)` 改为 `renderEditForm(detail)`（保持 `renderDetail` 用于 flow 视图或其他只读场景）。新增函数：

```js
function renderEditForm(detail) {
  const name = detail.key;
  document.getElementById('detail-content').innerHTML = buildEntityForm(detail);
  document.getElementById('detail-content').dataset.key = name;
  // 绑定输入变更 -> 加入草稿（data-orig 记录初始值，仅记录有变化的字段）
  document.querySelectorAll('#detail-content input[data-field]').forEach(inp => {
    inp.addEventListener('change', () => {
      const key = document.getElementById('detail-content').dataset.key;
      const fields = {};
      document.querySelectorAll('#detail-content input[data-field]').forEach(i => {
        if (i.value.trim() !== '' && i.value.trim() !== i.dataset.orig) fields[i.dataset.field] = i.value.trim();
      });
      if (Object.keys(fields).length) pushDraft({type:'update', key, fields});
    });
  });
}

function pushDraft(op) {
  // 同 key 同类型合并（update 合并 fields）
  const idx = draftOps.findIndex(o => o.type === op.type && o.key === op.key);
  if (idx >= 0 && op.type === 'update') {
    draftOps[idx].fields = {...draftOps[idx].fields, ...op.fields};
  } else if (idx >= 0) {
    draftOps[idx] = op;
  } else {
    draftOps.push(op);
  }
  trackDirty(op.key);
}
```

- [ ] **Step 4: index.html —— 新增/复制/删除**

```js
async function addDraftEntity() {
  const key = prompt('新实体 key（如 my-click）');
  if (!key) return;
  pushDraft({type:'create', key, entity:{type:'click', target:'buttons\\xxx.png'}});
  showBanner(`草稿: 新增 ${key}（请在表单补全字段）`, 'ok');
}

async function duplicateEntity() {
  const key = document.getElementById('detail-content').dataset.key;
  if (!key) return;
  const detail = await (await fetch(`/api/entity/${encodeURIComponent(key)}?file=${encodeURIComponent(currentFile)}`)).json();
  const newKey = prompt('新实体 key', `${key}-copy`);
  if (!newKey) return;
  const entity = {};
  for (const k of Object.keys(detail)) {
    if (k === 'key' || detail[k] === '' || detail[k] === null || detail[k] === undefined) continue;
    entity[k] = Array.isArray(detail[k]) ? detail[k].join(',') : String(detail[k]);
  }
  pushDraft({type:'create', key:newKey, entity});
}

function deleteDraftEntity() {
  const key = document.getElementById('detail-content').dataset.key;
  if (!key || !confirm(`删除实体 ${key}？`)) return;
  pushDraft({type:'delete', key});
}
```

- [ ] **Step 5: index.html —— 错误横幅与定位**

```js
function showErrors(errors) {
  const list = errors.map(e =>
    `<div class="err" data-key="${e.key}">[${e.file}] ${e.key} · ${e.field}: ${e.message}</div>`).join('');
  document.getElementById('err-banner').innerHTML =
    `<div class="err-head">校验失败，未保存 <button onclick="hideErrors()">×</button></div>${list}`;
  document.getElementById('err-banner').style.display = 'block';
  document.querySelectorAll('#err-banner .err').forEach(el =>
    el.addEventListener('click', () => {
      const k = el.dataset.key;
      if (k && cy.getElementById(k).length) { cy.getElementById(k).addClass('error'); cy.center(cy.getElementById(k)); }
    }));
}
function hideErrors() { document.getElementById('err-banner').style.display = 'none'; }
```

- [ ] **Step 6: index.html —— 挂载与 CSS**

在现有 `loadGraph` 中（`data = await res.json()` 之后、`showAll()` 之前）插入：`baseHash = data.file_hash;`，并清空草稿状态。在页面初始化处（`initCy()` 附近）追加 `fetchEntities();`。改动后的 `loadGraph` 对应片段：

```js
async function loadGraph(filename) {
  currentFile = filename;
  try {
    const res = await fetch(`/api/graph?file=${encodeURIComponent(filename)}`);
    const data = await res.json();
    fullNodes = data.nodes;
    fullEdges = data.edges;
    baseHash = data.file_hash || null;      // 新增：保存时回传做冲突检测
    draftOps = []; dirtyKeys.clear();       // 新增：切换文件清空草稿
    cy.$('.dirty').removeClass('dirty');    // 新增
    hideErrors();                           // 新增
    refreshDraftBar();                      // 新增
    showAll();
    buildTaskList();
    document.getElementById('detail-content').innerHTML = '<div id="detail-empty">点击画布中的节点查看详情</div>';
  } catch (e) {
    console.error('Failed to load graph:', e);
  }
}
```

CSS 追加（`</style>` 前）：

```css
#draft-bar { position: fixed; left: 180px; right: 310px; bottom: 0; background:#0f3460;
  color:#eee; padding:6px 12px; font-size:12px; display:none; z-index:10; align-items:center; gap:8px; }
#err-banner { position: fixed; left: 180px; right: 310px; bottom: 36px; background:#3e2723;
  color:#ffcdd2; padding:8px 12px; font-size:12px; display:none; z-index:11; max-height:40vh; overflow-y:auto; }
#err-banner .err { cursor:pointer; padding:2px 0; }
#err-banner .err:hover { color:#fff; }
#detail-content input { width:100%; background:#1a1a2e; color:#e0e0e0; border:1px solid #0f3460;
  border-radius:3px; padding:3px 6px; font-size:12px; margin-top:2px; }
```

**节点脏标记/错误标记必须在 cytoscape stylesheet 中声明**（cytoscape 画布渲染不受 CSS 控制）。在 `initCy()` 的 `style` 数组末尾追加两个选择器：

```js
  { selector: 'node.dirty', style: { 'border-width': 3, 'border-color': '#ffd54f' } },
  { selector: 'node.error', style: { 'border-width': 3, 'border-color': '#ef5350' } },
```

（`trackDirty` / `showErrors` 已用 `addClass('dirty'/'error')`，直接生效。）

- [ ] **Step 7: 手动浏览器验证**

1. `uv run python -m taskView`，浏览器打开。
2. 点选节点 → 详情面板出现可编辑表单，字段按 type 分组。
3. 修改 `sleep` → 草稿栏出现"草稿 1 项 · 保存 · 放弃"，节点出现黄色脏边。
4. 点"新增"输入 key → 草稿 +1；点"复制"确认 → 草稿 +1。
5. 保存 → 图重排；`git diff jczx/Config/tasks/receive.txt` 检查写回格式与注释保留。
6. 构造引用错误（action 填不存在的 key）→ 保存 → 红色横幅列出错误，点击定位节点。
7. 点"放弃" → 草稿清空、脏标记消失。
8. 外部用编辑器改文件后再保存 → 409 提示重新加载。

- [ ] **Step 8: 提交（先请用户验证 Task 4 后再提交）**

```bash
git add taskView/static/index.html taskView/server.py
git commit -m ":sparkles: taskView 前端可视化编辑交互"
```

---

### Task 5: 收尾 —— 清理、README、端到端验证

**Files:**
- Modify: `taskView/README.md`
- Delete: `taskView/_dev_check.py`

**Interfaces:**
- Consumes: 全部前序任务产物

- [ ] **Step 1: 更新 taskView/README.md**

重写启动与功能两节：

```markdown
## 启动

```powershell
uv run python -m taskView
```

浏览器自动打开 `http://localhost:8000`。依赖由根 `pyproject.toml`（uv）管理，无需独立虚拟环境。

## 功能

- 选择并加载任意 `.txt` 配置文件，dagre 层次布局展示任务执行有向图，按 `type` 着色
- **可视化编辑**：点击节点以表单编辑字段（按 type 分组渲染），引用字段自动补全
- **实体管理**：新增 / 复制 / 删除，草稿暂存 + 显式保存（原子写回，保留注释与顺序）
- **严格校验**：保存前校验引用完整、重名、字段类型、占位符与资源存在，出错不写盘
- 导出 PNG / SVG，切换布局算法
```

- [ ] **Step 2: 端到端验证**

1. `uv run python -m taskView`，对真实配置执行 改值 / 新增 / 复制 / 删除 / 保存。
2. `git diff` 检查：行首注释保留、section 顺序稳定、`key: value` 格式正确、`action: /|%{simulate_times}` 未被切分。
3. 保存后 `uv run python -m jczx.jczxCli` 加载同一配置，确认 TUI 正常解析（任务列表出现改动后的任务）。

- [ ] **Step 3: 删除临时自检脚本**

```bash
git rm taskView/_dev_check.py
```

- [ ] **Step 4: 提交（先请用户验证 Task 5 后再提交）**

```bash
git add taskView/README.md
git commit -m ":memo: taskView 更新 README（uv 运行 + 可视化编辑）"
```

---

## Self-Review

- [ ] **Spec 覆盖核对**：
  - §4 ConfigEditor 行级 patch → Task 1
  - §5 变更集 / apply 原子提交 / base_hash 冲突保护 → Task 2/3
  - §6 严格校验（重名/引用/类型/占位符/type/资源/func）→ Task 2
  - §7 前端表单/自动补全/工具栏/草稿/脏标记/错误定位 → Task 4
  - §9 uv 运行 → Global Constraints + Task 5 README
  - §10 手动验证 + git diff 注释检查 + TUI 加载 → Task 5
- [ ] **占位符扫描**：无 TBD/TODO；所有代码步骤含具体实现。
- [ ] **类型一致**：`writes` 元素统一为 `(path, text)`；`file_hash` / `load_entity_pool` / `simulate_and_validate` 签名在 Task 1/2 定义、Task 3/4 引用一致；`ConfigEditor.lines` 只读属性已补。
