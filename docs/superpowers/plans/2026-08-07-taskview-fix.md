# taskView 测试问题修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 taskView 前端测试发现的 7 个问题（type 可编辑 / settings 字段 / 新建节点 404 / 跨文件引用边 / 默认 target / flow 跨文件字段 / flow 状态反馈）。

**Architecture:** 后端 `graph_builder.py` 增强（全局实体池 + entity_file 映射，支持跨文件引用边、flow 节点带来源文件、detail 补 settings 字段）；前端 `index.html` 修复表单渲染（type 下拉、settings 分组）与交互（跳过新建节点 fetch、默认 target 留空、tap 用来源文件、flow 节点 `#N` 查找兼容）。

**Tech Stack:** Python 3.14 · FastAPI · 前端 Cytoscape.js（CDN）。依赖由根 pyproject.toml（uv）管理。

## Global Constraints

- **无测试套件**：AGENTS.md 禁止 pytest/ruff/mypy。后端用临时脚本 `taskView/_dev_check.py`（纯 assert，`uv run python` 执行，验证后删除）；前端用 `node --check` 语法验证 + playwright 回归。
- **uv 运行**：`uv run python -m taskView`。
- **零侵入**：不修改 `jczx/` 下任何文件、不修改生产配置（测试限 `tasks/test.txt`，产物用 `git checkout` 恢复）。
- **只改**：`taskView/graph_builder.py`、`taskView/static/index.html`。不改 `editor.py`/`server.py`。
- **git 提交**：功能须经用户验证后再提交；格式 `[emoji: 中文信息]`。

---

## 文件结构

| 文件 | 职责 | 变更 |
|------|------|------|
| `taskView/graph_builder.py` | #4 跨文件引用边、#6 flow 节点 file、#2 detail 补 settings 字段 | Modify |
| `taskView/static/index.html` | #1/#2 表单渲染、#3/#5/#6/#7 交互 | Modify |

---

## 接口契约（跨任务引用）

```python
# ---- taskView/graph_builder.py ----
def _load_all_files() -> tuple[dict[str, JczxSectionEntity], dict[str, str]]:
    """返回 (configs, entity_file)。entity_file: 实体 key -> 来源文件绝对路径。
    现有调用方（get_entity_detail / build_flow_tree）改为 `configs, entity_file = _load_all_files()`。"""
```

前端 `index.html`：
- `fullNodes`（现有全局）：当前图数据。判断实体是否已保存：`fullNodes.some(n => n.data.id === key)`。
- flow 节点 `data.file`：实体来源文件（Task 1 提供），tap handler 用 `node.data('file') || currentFile`。

---

### Task 1: 后端 graph_builder.py（#4 跨文件引用边、#6 file 字段、#2 detail 补字段）

**Files:**
- Modify: `taskView/graph_builder.py`
- Test: `taskView/_dev_check.py`（临时）

**Interfaces:**
- Consumes: 现有 `_load_one`/`_resolve_extends`/`_load_all_entities`/`build_graph`/`build_flow_tree`/`get_entity_detail`
- Produces: `_load_all_files()` 返回 `(configs, entity_file)`；build_graph 跨文件节点；flow 节点 `data.file`；detail 补 settings 字段

- [ ] **Step 1: 写临时自检脚本（断言后端新行为）**

创建 `taskView/_dev_check.py`：

```python
"""临时自检脚本（非 pytest）。uv run python taskView/_dev_check.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.graph_builder import (_load_all_files, build_graph, build_flow_tree, get_entity_detail)

def test_load_all_files_returns_entity_file():
    configs, efile = _load_all_files()
    assert len(configs) > 100, "应加载全部实体"
    assert "test" in efile or "click-center" in efile
    assert all(k in efile for k in configs), "每个实体应有来源文件"

def test_build_graph_cross_file_edge():
    # test.txt 的 test.action 引用 get-combat-power/context-check（MainMenu）
    g = build_graph("tasks/test.txt")
    ids = [n["data"]["id"] for n in g["nodes"]]
    assert "get-combat-power" in ids or "context-check" in ids, "跨文件引用实体应出现在节点"
    edges = [e["data"] for e in g["edges"]]
    assert any(e["source"] == "test" and e["target"] in ("get-combat-power", "context-check") for e in edges), "应有跨文件引用边"

def test_flow_node_has_file():
    tree = build_flow_tree("tasks/test.txt", "test")
    nodes = tree["nodes"]
    assert nodes, "flow 树应非空"
    assert any("file" in n["data"] for n in nodes), "flow 节点应带 file 字段"

def test_detail_has_settings_fields():
    d = get_entity_detail("tasks/test.txt", "test")
    for f in ("fields", "setting_type", "label", "options", "default", "min", "max"):
        assert f in d, f"detail 应含 {f}"

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python taskView/_dev_check.py`
Expected: FAIL（`_load_all_files` 返回 dict 非 tuple；跨文件边/flow file/detail settings 均缺失）

- [ ] **Step 3: 实现 `_load_all_files()` 返回 entity_file**

`graph_builder.py` 修改：

```python
def _load_one(path: str, all_configs: dict[str, JczxSectionEntity], seen: set[str],
              entity_file: dict[str, str] | None = None) -> None:
    if not os.path.isfile(path) or path in seen:
        return
    seen.add(path)
    config = TxtConfig(path)
    configs = config.trans_entity_dict(JczxSectionEntity)
    for key, entity in list(configs.items()):
        if key in all_configs:
            raise ValueError(f"Duplicate section '{key}' in {path}")
        all_configs[key] = entity
        if entity_file is not None:
            entity_file[key] = path
        if entity.type == "file":
            sub_path = os.path.join(os.path.dirname(path),
                                    (getattr(entity, "target", "") or "").replace("/", os.sep))
            _load_one(sub_path, all_configs, seen, entity_file)


def _load_all_files() -> tuple[dict[str, JczxSectionEntity], dict[str, str]]:
    all_configs: dict[str, JczxSectionEntity] = {}
    entity_file: dict[str, str] = {}
    seen: set[str] = set()
    main_menu_path = os.path.join(CONFIG_DIR, "MainMenu.txt")
    _load_one(main_menu_path, all_configs, seen, entity_file)
    _resolve_extends(all_configs)
    for key, entity in all_configs.items():
        entity.only_key = key
    return all_configs, entity_file
```

**适配现有调用方**：
- `get_entity_detail`：`configs = _load_all_files()` → `configs, _ = _load_all_files()`
- `build_flow_tree`：`configs = _load_all_files()` → `configs, entity_file = _load_all_files()`；`_node()` 的 `data` 加 `"file": entity_file.get(base, "")`（base = `uid.split("#")[0]`）。

- [ ] **Step 4: 实现 build_graph 跨文件引用边（#4）**

`build_graph` 开头加载全局池，并加跨文件节点 helper：

```python
def build_graph(filename: str) -> dict[str, list[dict[str, Any]]]:
    try:
        configs = _load_all_entities(filename)
    except (ValueError, FileNotFoundError):
        return {"nodes": [], "edges": []}
    global_configs, entity_file = _load_all_files()   # 全局池：判断跨文件引用

    condition_keys = _find_condition_entities(configs)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    def _add_node(entity, nid=None) -> str:
        nid = nid or entity.only_key
        if nid in seen_node_ids:
            return nid
        seen_node_ids.add(nid)
        classes = entity.type or ""
        if nid in condition_keys or entity.type == "condition":
            classes = (classes + " condition-entity").strip()
        if entity.break_point == "on":
            classes = (classes + " breakpoint").strip()
        if entity.type == "file":
            classes = (classes + " file-entity").strip()
        nodes.append({
            "data": {
                "id": nid, "label": entity.name or entity.desc or nid, "type": entity.type or "",
                "desc": entity.desc or "", "func": entity.func or "", "target": entity.target or "",
                "sleep": entity.sleep, "per": entity.per, "times": entity.times,
                "max_wait": entity.max_wait, "break_point": entity.break_point,
                "has_test_after": bool(getattr(entity, "testFor_after", "")),
                "has_test_before": bool(getattr(entity, "testFor_before", "")),
                "testFor_max_wait": getattr(entity, "testFor_max_wait", 0) or 0,
                "context_key": getattr(entity, "context_key", "") or "",
                "wait_target": getattr(entity, "wait_target", "") or "",
                "wait_target_per": getattr(entity, "wait_target_per", 0.8) or 0.8,
            },
            "classes": classes,
        })
        return nid

    def _add_external_node(key: str, label_hint: str) -> str:
        """跨文件引用实体节点（当前文件外），标注来源文件。"""
        if key in seen_node_ids:
            return key
        seen_node_ids.add(key)
        ent = global_configs[key]
        nodes.append({
            "data": {
                "id": key, "label": ent.name or ent.desc or key, "type": ent.type or "",
                "desc": ent.desc or "", "func": ent.func or "", "target": ent.target or "",
                "sleep": ent.sleep, "per": ent.per, "times": ent.times,
                "max_wait": ent.max_wait, "break_point": ent.break_point,
                "file": entity_file.get(key, ""),
            },
            "classes": (ent.type or "") + " external",
        })
        return key

    def _resolve_ref(ref: str, src: str, label: str, classes: str) -> None:
        """引用解析：当前文件实体 → 普通节点；跨文件 → external 节点。"""
        if not ref or ref in seen_edge_ids:
            return
        eid = f"{src}→{ref}::{classes}"
        if eid in seen_edge_ids:
            return
        if ref in configs:
            _add_node(configs[ref])
        elif ref in global_configs:
            _add_external_node(ref, "")
        else:
            return
        seen_edge_ids.add(eid)
        edges.append({"data": {"id": eid, "source": src, "target": ref, "label": label}, "classes": classes})

    def _add_edge(source_id: str, target_id: str, label: str, classes: str):
        if not target_id:
            return
        eid = f"{source_id}→{target_id}::{classes}"
        if eid in seen_edge_ids:
            return
        seen_edge_ids.add(eid)
        edges.append({"data": {"id": eid, "source": source_id, "target": target_id, "label": label}, "classes": classes})

    for key, entity in configs.items():
        _add_node(entity)

    for key, entity in configs.items():
        src = entity.only_key
        for idx, target in enumerate(entity.action):
            _resolve_ref(target, src, chr(0x2460 + min(idx, 19)) if len(entity.action) > 1 else "", "action")
        if entity.condition:
            _resolve_ref(entity.condition, src, "条件", "condition")
        if entity.condition_not:
            _resolve_ref(entity.condition_not, src, "条件", "condition_not")
        for target in entity.condition_then:
            _resolve_ref(target, src, "是", "condition_then")
        for target in entity.condition_else:
            _resolve_ref(target, src, "否", "condition_else")
        if entity.extend:
            _resolve_ref(entity.extend, src, "继承", "extend")
        if entity.type == SectionType.TASK.value and getattr(entity, "settings", None):
            sk = getattr(entity, "settings", "")
            if sk and sk in configs:
                _add_node(configs[sk]); _add_edge(src, sk, "设置", "settings")
            elif sk and sk in global_configs:
                _add_external_node(sk, ""); _add_edge(src, sk, "设置", "settings")

    # 占位符引用（@{} ${} 等）沿用现有逻辑，仅对 configs 内实体建边；跨文件占位符不建边
    for key, entity in configs.items():
        src = entity.only_key
        texts = []
        if entity.target: texts.append(entity.target)
        for lst in (entity.args, entity.action, entity.condition_then,
                     entity.condition_else, entity.wait_sec):
            if lst: texts.extend(lst)
        if entity.condition: texts.append(entity.condition)
        if entity.condition_not: texts.append(entity.condition_not)
        log_v = getattr(entity, "log", "") or ""
        if log_v: texts.append(log_v)
        wt = getattr(entity, "wait_target", "") or ""
        if wt: texts.append(wt)
        for text in texts:
            if not isinstance(text, str): continue
            for m in _RE_EXEC.findall(text):
                if m in configs:
                    _add_node(configs[m]); _add_edge(src, m, f"@{{{m}}}", "execute")
            for m in _RE_CFG.findall(text):
                if m in configs:
                    _add_node(configs[m]); _add_edge(src, m, f"${{{m}}}", "config")
            for m in _RE_CTX.findall(text):
                ref_key = m.split()[0].rstrip(">")
                for ck in configs:
                    if getattr(configs[ck], "context_key", "") == ref_key:
                        _add_node(configs[ck]); _add_edge(src, ck, f"%{{{m}}}", "context")
            for m in _RE_EXPR.findall(text):
                for word in re.findall(r'\b([a-zA-Z][\w-]+)\b', m):
                    if word in configs:
                        _add_node(configs[word]); _add_edge(src, word, f"&{{{word}}}", "expression")

    return {"nodes": nodes, "edges": edges}
```

> 说明：`_resolve_ref` 统一处理 action/condition/then/else/extend 的引用（当前文件 → 普通节点，跨文件 → external 节点）。原 `_add_edge` 保留供 settings/占位符使用。**跨文件引用不递归扩展**（external 节点的引用不处理）。

- [ ] **Step 5: 实现 get_entity_detail 补 settings 字段（#2）**

`get_entity_detail` 返回 dict 追加：

```python
    detail["fields"] = getattr(entity, "fields", []) or []
    detail["setting_type"] = getattr(entity, "setting_type", "") or ""
    detail["label"] = getattr(entity, "label", "") or ""
    detail["options"] = getattr(entity, "options", []) or []
    detail["default"] = getattr(entity, "default", "") or ""
    detail["min"] = getattr(entity, "min", None)
    detail["max"] = getattr(entity, "max", None)
    detail["explicit"] = explicit
    return detail
```

- [ ] **Step 6: 运行自检确认通过**

Run: `uv run python taskView/_dev_check.py`
Expected: `ALL PASS`（4 项）

- [ ] **Step 7: 服务冒烟 + 提交（先请用户验证 Task 1）**

```bash
uv run python -m taskView &
curl -s "http://localhost:8000/api/graph?file=tasks/test.txt" | python -c "import sys,json; d=json.load(sys.stdin); print('nodes:', [n['data']['id'] for n in d['nodes']])"
git add taskView/graph_builder.py taskView/_dev_check.py
git commit -m ":sparkles: taskView 后端：跨文件引用边/flow 节点来源/detail settings 字段"
```

---

### Task 2: 前端表单渲染（#1 type 下拉、#2 settings/setting 字段分组）

**Files:**
- Modify: `taskView/static/index.html`
- Test: `node --check` + playwright

**Interfaces:**
- Consumes: `get_entity_detail` 新增字段（Task 1）；`renderEditForm` 绑定循环（扩展 select）
- Produces: type 下拉 change 入 op；settings/setting 专有字段输入框

- [ ] **Step 1: 语法基线**

提取内联 JS 用 `node --check` 确认当前无语法错误。

- [ ] **Step 2: 实现 #1 type 下拉**

`buildEntityForm` 工具栏的 `type: <b>${esc(type)}</b>` 替换为下拉：

```js
const TYPE_OPTIONS = ['task', 'func', 'click', 'dynamic', 'match', 'ocr', 'context', 'condition', 'settings', 'setting', 'file'];
// 在 buildEntityForm 的 return 中：
return `<div style="display:flex;gap:6px;margin-bottom:8px">
      <button onclick="addDraftEntity()">新增</button>
      <button onclick="duplicateEntity()">复制</button>
      <button onclick="deleteDraftEntity()" style="color:#ef5350">删除</button>
      <span style="margin-left:auto">type: <select data-field="type">${TYPE_OPTIONS.map(t => `<option value="${t}" ${t === type ? 'selected' : ''}>${t}</option>`).join('')}</select></span>
    </div>${html}`;
```

`renderEditForm` 的输入绑定循环选择器扩展（`input` → `input, select`），change 收集统一走现有逻辑：

```js
document.querySelectorAll('#detail-content input[data-field], #detail-content select[data-field]').forEach(inp => {
  inp.addEventListener('change', () => { /* 现有字段收集逻辑不变 */ });
});
```

- [ ] **Step 3: 实现 #2 settings/setting 字段分组**

`buildEntityForm` 的 `byType` 追加：

```js
  const byType = {
    click: [...], match: [...], ocr: [...], func: [...], condition: [...], task: [...], context: [...],
    settings: [['fields', 'fields 引用']],
    setting: [['setting_type', '控件类型'], ['label', '标签'], ['desc', '说明'],
              ['options', '选项'], ['default', '默认值'], ['min', '最小'], ['max', '最大']],
  };
```

`fields`/`options` 是 list 字段，表单渲染用逗号串（现有 `buildEntityForm` 已对 `Array.isArray(detail[k])` 做 `join(',')`）；`fields` 加入引用 datalist（`ref-fields` 字段名需在引用列表中）。

- [ ] **Step 4: 语法验证 + 前端渲染检查**

Run: `python -c "提取script" && node --check`；启动服务，playwright 打开页面选中 `test`，确认 type 下拉存在；临时在 test.txt 加 settings/setting 实体后确认专有字段渲染（测后恢复）。

- [ ] **Step 5: 提交（先请用户验证 Task 2）**

```bash
git add taskView/static/index.html
git commit -m ":sparkles: taskView 表单：type 下拉 + settings/setting 字段分组"
```

---

### Task 3: 前端交互修复（#3 跳过 fetch、#5 target 留空、#6 tap file、#7 #N 查找）

**Files:**
- Modify: `taskView/static/index.html`
- Test: `node --check` + playwright

**Interfaces:**
- Consumes: `fullNodes`（判断已保存）、flow 节点 `data.file`（Task 1）
- Produces: 新建节点不 fetch、新增无默认 target、tap 用来源文件、flow 节点标脏/标红

- [ ] **Step 1: 实现 #3 跳过新建节点 fetch + #6 用来源文件**

`cy.on('tap', 'node', ...)` handler 改造：

```js
cy.on('tap', 'node', async function (evt) {
    const node = evt.target;
    const entityName = node.data('id');
    const lookupName = entityName.replace(/#\d+$/, '');
    if (!currentFile || !entityName) return;
    if (!detailVisible) toggleDetail();
    document.getElementById('detail-content').innerHTML = '<div id="detail-empty">加载中…</div>';
    // #6: flow 节点带来源文件（data.file），graph 节点回退 currentFile
    const detailFile = node.data('file') || currentFile;
    // #3: 新建节点（不在当前图数据 fullNodes）不 fetch，避免 404 噪音
    const isSaved = fullNodes.some(n => n.data.id === lookupName);
    let detail;
    if (isSaved) {
      try {
        const res = await fetch(`/api/entity/${encodeURIComponent(lookupName)}?file=${encodeURIComponent(detailFile)}`);
        if (res.ok) {
          detail = await res.json();
        } else {
          const typeCls = ['task','func','click','match','ocr','condition','context','dynamic','settings','setting','file']
            .find(c => node.hasClass(c)) || 'click';
          detail = { key: lookupName, type: typeCls, desc: '未保存的新实体（草稿，保存后写入配置）' };
        }
      } catch (e) {
        document.getElementById('detail-content').innerHTML = '<div id="detail-empty">加载详情失败</div>';
        return;
      }
    } else {
      const typeCls = ['task','func','click','match','ocr','condition','context','dynamic','settings','setting','file']
        .find(c => node.hasClass(c)) || 'click';
      detail = { key: lookupName, type: typeCls, desc: '未保存的新实体（草稿，保存后写入配置）' };
    }
    renderEditForm(detail);
  });
```

- [ ] **Step 2: 实现 #5 新增默认 target 留空**

`addDraftEntity`：

```js
async function addDraftEntity() {
  const key = prompt('新实体 key（如 my-click）');
  if (!key) return;
  pushDraft({ type: 'create', key, entity: { type: 'click' } });   // 不再默认 buttons\xxx.png
  showBanner(`草稿: 新增 ${key}（请在表单补全字段）`, 'ok');
}
```

- [ ] **Step 3: 实现 #7 flow 节点查找兼容 #N**

`trackDirty` 与乐观更新 delete/update 分支的节点查找统一为 helper：

```js
function findNode(key) {
  const exact = cy.getElementById(key);
  if (exact.length) return exact;
  return cy.$(`[id^="${key}#"]`);   // flow 节点 id 形如 key#N
}
```

`trackDirty`：

```js
function trackDirty(key) {
  dirtyKeys.add(key);
  const n = findNode(key);
  if (n.length) n.addClass('dirty');
  refreshDraftBar();
}
```

乐观更新 delete/update 分支的 `cy.getElementById(key)` 改为 `findNode(key)`（delete 标红、update 去 deleted 恢复）。

- [ ] **Step 4: 语法验证 + playwright 回归**

Run: `node --check`；启动服务，playwright 验证：
- #3：新增实体 → 选中 → console 无 `/api/entity` 404
- #5：新增 → 保存不再被 target 误拦（空 target 跳过图片校验）
- #6：flow 视图选中 `get-combat-power#1` → 表单 func 字段有值
- #7：flow 视图改字段 → 节点标黄；删除 → 标红

- [ ] **Step 5: 提交（先请用户验证 Task 3）**

```bash
git add taskView/static/index.html
git commit -m ":sparkles: taskView 交互：跳过新建节点 fetch/默认 target 留空/flow 来源文件/节点查找兼容"
```

---

## Self-Review

- [ ] **Spec 覆盖核对**：
  - §3.1 #1 type 下拉 → Task 2 Step 2
  - §3.2 #2 settings 字段 → Task 2 Step 3（+ Task 1 Step 5 detail 补字段）
  - §3.3 #3 跳过 fetch → Task 3 Step 1
  - §3.4 #5 target 留空 → Task 3 Step 2
  - §3.5 #7 #N 查找 → Task 3 Step 3
  - §3.6 #6 tap file → Task 3 Step 1（+ Task 1 Step 3/4 flow 节点 file）
  - §4.1 #4 跨文件引用边 → Task 1 Step 4
- [ ] **占位符扫描**：无 TBD/TODO；每步含具体代码。
- [ ] **类型一致**：`_load_all_files()` 返回 `(configs, entity_file)` 在 Task 1 定义，`build_flow_tree`/`get_entity_detail` 调用适配；前端 `findNode`/`detailFile`/`isSaved` 在 Task 3 定义一致。
