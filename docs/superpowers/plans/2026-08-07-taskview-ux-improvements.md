# taskView 前端体验改进实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 改进 taskView 编辑器的 6 个体验问题：字段按 type 完整展示、实体引用标签式输入、草稿实体下拉、单/多实体字段输入、清空删字段、草稿 action 实时连线（含跨文件链路）。

**Architecture:** 前端 `index.html` 重构 `buildEntityForm`（字段分类 + 实体引用输入组件），新增草稿图更新 `updateDraftGraph()`；后端 `editor.py` 支持清空字段删除 option 行（`ConfigEditor.delete_option` + 写回空值删除）。

**Tech Stack:** Python 3.14 · FastAPI · Cytoscape.js（CDN）。依赖根 pyproject.toml（uv）。

## Global Constraints

- **无测试套件**：AGENTS.md 禁止 pytest/ruff/mypy。后端用临时脚本（纯 assert，`uv run python`）；前端 `node --check`（`D:/Software/Node/node.exe`）+ playwright 回归。
- **uv 运行**：`uv run python -m taskView`。
- **零侵入**：不修改 `jczx/` 下任何文件、不修改生产配置（测试限 `tasks/test.txt`，产物 `git checkout` 恢复）。
- **只改**：`taskView/static/index.html`、`taskView/editor.py`。不改 `graph_builder.py`/`server.py`（#6 用现有 `/api/flow`、`/api/entity`）。
- **git 提交**：功能须经用户验证后再提交；格式 `[emoji: 中文信息]`。

---

## 文件结构

| 文件 | 职责 | 变更 |
|------|------|------|
| `taskView/editor.py` | #5 清空删字段：`ConfigEditor.delete_option` + 写回空值删除 | Modify |
| `taskView/static/index.html` | #1-#4 表单重构、#5 空值提交、#6 图实时连线 | Modify |

---

## 接口契约（跨任务引用）

```python
# ---- taskView/editor.py ----
# ConfigEditor 新增方法：
def delete_option(self, key: str, option: str) -> None:
    """删除指定 option 行（不存在则 no-op），重建索引。"""
```

前端 `index.html`：
- `getDraftCandidates()`：实体引用候选 = `entityCandidates` + draftOps 中 create 的实体 key
- `updateDraftGraph()`：草稿态图更新（Task 3），pushDraft 后调用

---

### Task 1: 后端清空删字段（#5）

**Files:**
- Modify: `taskView/editor.py`
- Test: 临时脚本

**Interfaces:**
- Consumes: `ConfigEditor`（update_value/add_option）、`simulate_and_validate` 写回循环
- Produces: `ConfigEditor.delete_option`；写回对空字符串值删除 option 行

- [ ] **Step 1: 写临时自检脚本（断言 delete_option 与空值写回）**

```python
"""临时自检脚本。uv run python taskView/_dev_check.py"""
import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.editor import ConfigEditor

SAMPLE = "[e1]\ntype: click\nname: 测试\ntarget: buttons\\home.png\nsleep: 1\n"

def _make():
    fd, p = tempfile.mkstemp(suffix=".txt"); os.close(fd)
    with open(p, "w", encoding="utf-8") as f: f.write(SAMPLE)
    return p

def test_delete_option():
    p = _make(); ed = ConfigEditor(p); ed.load()
    ed.delete_option("e1", "sleep")
    assert "sleep" not in ed.text, ed.text
    os.unlink(p)

def test_delete_option_missing_noop():
    p = _make(); ed = ConfigEditor(p); ed.load()
    ed.delete_option("e1", "nonexistent")  # 不应抛错
    assert "sleep: 1" in ed.text
    os.unlink(p)

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn): fn(); print(f"PASS {name}")
    print("ALL PASS")
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python taskView/_dev_check.py`
Expected: FAIL（`delete_option` 未定义）

- [ ] **Step 3: 实现 `ConfigEditor.delete_option`**

`taskView/editor.py` 的 `ConfigEditor` 类（`delete_entity` 后）添加：

```python
    def delete_option(self, key: str, option: str) -> None:
        """删除指定 option 行（不存在则 no-op），重建索引。"""
        ent = self._entity(key)
        for i in ent.option_lines:
            m = _OPTION_RE.match(self._lines[i])
            if m and m.group("key").strip() == option:
                del self._lines[i]
                self._reindex()
                return
        # option 不存在：no-op（可能是 extend 继承字段或未配置）
```

- [ ] **Step 4: 写回循环空值删除**

`simulate_and_validate` 写回循环（update 分支）改为：字段值为**空字符串**时删除 option 行，否则 update/add：

```python
            elif chg["op"] == "update":
                for field, value in chg["fields"].items():
                    if value == "":
                        ed.delete_option(key, field)   # 清空 → 删除字段行
                    else:
                        try:
                            ed.update_value(key, field, value)
                        except ValueError:
                            ed.add_option(key, field, value)
```

**`_apply_field` 对空串值**：当前 `setattr` 对 `float('')` 报错。改为空串值跳过类型转换（存原样），不报类型错：

```python
def _apply_field(ent, field, value, errors):
    if field not in ent.__dataclass_fields__:
        # settings/setting 专有字段放行（既有逻辑）...
        ...
    try:
        if value == "":
            super(BaseEntity, ent).__setattr__(field, "")   # 空串不类型转换（表示清空删除）
        else:
            setattr(ent, field, value)
    except Exception as e:
        errors.append(...)
```

> 说明：`super(BaseEntity, ent).__setattr__` 绕过 `JczxSectionEntity.__setattr__` 的类型转换，直接存空串。写回时空值走 delete_option。若 `field` 是 dataclass 字段，`super().__setattr__` 同样有效。

- [ ] **Step 5: 运行自检 + 服务冒烟**

Run: `uv run python taskView/_dev_check.py` → ALL PASS；`uv run python -m taskView &` 后 curl `/api/file/tasks/test.txt/apply` 提交 `{"update", "fields": {"sleep": ""}}` 断言 test.txt 中 sleep 行被删除（测后 git checkout 恢复）。

- [ ] **Step 6: 提交（先请用户验证 Task 1）**

```bash
git add taskView/editor.py taskView/_dev_check.py
git commit -m ":sparkles: taskView 后端：清空字段删除 option 行（delete_option）"
```

---

### Task 2: 前端字段分组补全 + 实体引用输入组件（#1/#2/#3/#4）

**Files:**
- Modify: `taskView/static/index.html`
- Test: `node --check` + playwright

**Interfaces:**
- Consumes: `entityCandidates`、`draftOps`（草稿 create 候选）、`buildEntityForm`/`renderEditForm`
- Produces: 实体引用输入组件（多实体标签式/单实体下拉）、`getDraftCandidates()`

- [ ] **Step 1: 字段分组补全（#1）**

`buildEntityForm` 的 `common` 补：

```js
  const common = [
    ['name','显示名'], ['desc','备注'], ['action','action 链(引用)'], ['times','次数'],
    ['extend','继承'], ['view','显示(view)'], ['sleep','sleep'], ['pre_sleep','pre_sleep'],
    ['max_wait','max_wait'], ['wait_target','wait_target'], ['wait_target_per','wait_target_per'],
    ['testFor_before','testFor_before'], ['testFor_after','testFor_after'],
    ['testFor_max_wait','testFor_max_wait'], ['testFor_pre_sleep','testFor_pre_sleep'],
    ['testFor_sleep','testFor_sleep'], ['testFor_per','testFor_per'],
    ['context_key','context_key'], ['context_type','context_type'], ['context_default_type','context_default_type'],
    ['screen_cache_ttl','screen_cache_ttl'], ['log','log'], ['log_level','log_level'],
  ];
```

`byType` 补 dynamic + click 的 wait_sec + context 的 context_default_type：

```js
  const byType = {
    click: [['target','图片'], ['per','阈值'], ['pos','坐标'], ['match','match 引用'],
            ['index','index'], ['break_point','break_point'], ['wait_sec','wait_sec'],
            ['condition','condition'], ['condition_not','condition_not'],
            ['condition_then','then'], ['condition_else','else']],
    match: [['target','图片'], ['per','阈值']],
    ocr:   [['target','图片'], ['match','match 引用'], ['per','阈值']],
    func:  [['func','方法'], ['target','参数'], ['args','参数']],
    condition: [['condition','条件'], ['condition_not','反向条件'],
                ['condition_then','then'], ['condition_else','else']],
    task:  [['settings','settings 引用']],
    context: [['context_get','读取'], ['context_default','默认值'], ['context_default_type','输入类型'],
              ['action','运算链'], ['context_key','存储'], ['context_type','输出类型']],
    dynamic: [['action','循环源']],
    settings: [['fields','fields 引用']],
    setting: [['setting_type','控件类型'], ['label','标签'], ['desc','说明'], ['options','选项'],
              ['default','默认值'], ['min','最小'], ['max','最大']],
  };
```

- [ ] **Step 2: 字段分类常量**

```js
  // 多实体引用（list 逗号串，标签式）：action/condition_then/condition_else/wait_sec
  const MULTI_REF_FIELDS = ['action', 'condition_then', 'condition_else', 'wait_sec'];
  // 单实体引用（str 单 key，下拉/输入）：match/condition/condition_not/extend/settings
  const SINGLE_REF_FIELDS = ['match', 'condition', 'condition_not', 'extend', 'settings'];
  // list 非引用（逗号串普通输入）：args/options/fields/pos
  const LIST_FIELDS = ['args', 'options', 'fields', 'pos'];
```

- [ ] **Step 3: 草稿候选函数 `getDraftCandidates()`**

```js
function getDraftCandidates() {
  const drafts = draftOps.filter(o => o.type === 'create').map(o => o.key);
  return entityCandidates.concat(drafts.map(k => ({ key: k, label: k, type: 'draft', draft: true })));
}
```

- [ ] **Step 4: 实体引用输入组件渲染（#2/#3/#4）**

`buildEntityForm` 的字段渲染按分类分发：

```js
  const html = fields.map(([k, label]) => {
    const val = detail[k] !== undefined && detail[k] !== null
      ? (Array.isArray(detail[k]) ? detail[k].join(',') : String(detail[k])) : '';
    const escVal = val === '' ? '' : escAttr(val);
    const cands = getDraftCandidates();
    if (MULTI_REF_FIELDS.includes(k)) {
      // 标签式：标签区 + 输入框（datalist 提供候选）
      const tags = val ? val.split(',').filter(Boolean) : [];
      const tagHtml = tags.map(t =>
        `<span class="ref-tag" data-field="${k}" data-key="${escAttr(t)}">${esc(t)} <b class="ref-del">×</b></span>`).join('');
      const dl = `<datalist id="ref-${k}">${cands.map(c => `<option value="${escAttr(c.key)}">`).join('')}</datalist>`;
      return `<div class="field"><span class="key">${k}</span>
        <div class="ref-tags" data-field="${k}">${tagHtml}</div>
        <input data-field="${k}" data-multi="1" data-orig="${escVal}" list="ref-${k}" placeholder="输入实体 key，回车/选择添加">
        ${dl}</div>`;
    }
    if (SINGLE_REF_FIELDS.includes(k)) {
      const dl = `<datalist id="ref-${k}">${cands.map(c => `<option value="${escAttr(c.key)}">`).join('')}</datalist>`;
      return `<div class="field"><span class="key">${k}</span>
        <input data-field="${k}" data-single="1" data-orig="${escVal}" value="${escVal}" list="ref-${k}">
        ${dl}</div>`;
    }
    if (LIST_FIELDS.includes(k)) {
      return `<div class="field"><span class="key">${k}</span>
        <input data-field="${k}" data-orig="${escVal}" value="${escVal}">${dl_none}</div>`;
    }
    return `<div class="field"><span class="key">${k}</span>
      <input data-field="${k}" data-orig="${escVal}" value="${escVal}">
      ${dl_none}</div>`;
  }).join('');
```

（`dl_none` 为空串，普通字段无 datalist。）

- [ ] **Step 5: renderEditForm 绑定扩展（多实体标签式交互）**

`renderEditForm` 输入绑定循环扩展，处理多实体标签的添加/删除：

```js
  // 多实体字段：输入框回车/change 添加标签；标签 × 删除
  document.querySelectorAll('#detail-content input[data-multi]').forEach(inp => {
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); appendMultiTag(inp); }
    });
    inp.addEventListener('blur', () => appendMultiTag(inp));   // 失焦提交当前输入
  });
  document.querySelectorAll('#detail-content .ref-del').forEach(del => {
    del.addEventListener('click', () => {
      const tag = del.closest('.ref-tag');
      const field = tag.dataset.field, key = tag.dataset.key;
      tag.remove();
      syncMultiField(field);
    });
  });

function appendMultiTag(inp) {
  const text = inp.value.trim();
  if (!text) return;
  const tagsBox = inp.closest('.field').querySelector('.ref-tags');
  tagsBox.insertAdjacentHTML('beforeend',
    `<span class="ref-tag" data-field="${inp.dataset.field}" data-key="${escAttr(text)}">${esc(text)} <b class="ref-del">×</b></span>`);
  inp.value = '';
  syncMultiField(inp.dataset.field);
}

function syncMultiField(field) {
  const box = document.querySelector(`.ref-tags[data-field="${field}"]`);
  const keys = [...box.querySelectorAll('.ref-tag')].map(t => t.dataset.key);
  const inp = document.querySelector(`#detail-content input[data-field="${field}"][data-multi]`);
  inp.value = keys.join(',');
  inp.dispatchEvent(new Event('change'));   // 走现有草稿收集逻辑
}
```

**现有 change 收集**：`renderEditForm` 的通用收集循环（`input[data-field], select[data-field]`）保持——多实体字段 value 是 join 后的逗号串，change 时收集。data-orig 比较时，多实体用"初始标签 join"作为 orig。

- [ ] **Step 6: CSS（标签样式）**

追加：

```css
#detail-content .ref-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
#detail-content .ref-tag { background: #0f3460; color: #ccc; padding: 2px 6px; border-radius: 3px; font-size: 11px; display: inline-flex; align-items: center; gap: 4px; }
#detail-content .ref-del { cursor: pointer; color: #e94560; font-weight: bold; }
```

- [ ] **Step 7: 验证**

`node --check`；playwright：选中 test → action 显示标签式（标签 + 输入框）；输入 `goto-home` 回车 → 标签添加；点 × 删除；草稿新增实体后 → 下拉候选含草稿实体；type 切到 dynamic → 表单含 action 循环源。

- [ ] **Step 8: 提交（先请用户验证 Task 2）**

```bash
git add taskView/static/index.html
git commit -m ":sparkles: taskView 表单：字段分组补全 + 实体引用标签式输入 + 草稿实体候选"
```

---

### Task 3: 前端空值提交 + 图实时连线（#5 前端 + #6）

**Files:**
- Modify: `taskView/static/index.html`
- Test: `node --check` + playwright

**Interfaces:**
- Consumes: `pushDraft`、`cy`、`/api/flow`、`draftOps`、`currentFile`
- Produces: `updateDraftGraph()`（草稿态图实时更新 + 跨文件链路）

- [ ] **Step 1: 空值提交（#5 前端）**

多实体字段清空（无标签）→ 提交空串（`syncMultiField` 已做，无标签时 join=''）。单实体清空 → 提交 ''。后端 Task 1 已支持空值删除 option 行。**确认**：现有 change 收集对空值字段——收集循环 `if (i.value !== i.dataset.orig) fields[...] = i.value`，空值也会进 fields（后端删除）。已验证。

- [ ] **Step 2: 草稿态样式（#6）**

cytoscape style 加：

```js
  { selector: 'node.draft', style: { 'border-style': 'dashed', 'opacity': 0.6 } },
  { selector: 'edge.draft', style: { 'line-style': 'dashed', 'opacity': 0.5 } },
```

- [ ] **Step 3: `updateDraftGraph()`（#6 核心）**

新增函数（在 pushDraft 附近）：

```js
const draftGraph = { nodes: new Set(), edges: new Set() };

async function updateDraftGraph() {
  // 清除旧草稿态
  draftGraph.nodes.forEach(id => { const n = cy.getElementById(id); if (n.length) n.remove(); });
  draftGraph.edges.forEach(id => { const e = cy.getElementById(id); if (e.length) e.remove(); });
  draftGraph.nodes.clear(); draftGraph.edges.clear();

  // 遍历草稿，收集引用关系（source 实体 → target 引用）
  const refs = [];   // {source, target}
  for (const op of draftOps) {
    if (op.type !== 'create' && op.type !== 'update') continue;
    const fields = op.type === 'create' ? op.entity : op.fields;
    for (const f of ['action', 'condition_then', 'condition_else']) {
      const v = fields[f];
      if (!v) continue;
      for (const t of String(v).split(',').map(s => s.trim()).filter(Boolean)) {
        refs.push({ source: op.key, target: t });
      }
    }
  }

  // 对每个引用，确保 target 存在（跨文件展开链路），建边
  for (const { source, target } of refs) {
    const srcNode = findNode(source);
    if (!srcNode.length) continue;
    let tgtNode = findNode(target);
    if (!tgtNode.length) {
      // 跨文件：尝试加载链路
      const res = await fetch(`/api/flow?file=${encodeURIComponent(currentFile)}&task=${encodeURIComponent(target)}`);
      if (res.ok) {
        const tree = await res.json();
        for (const n of tree.nodes || []) {
          if (!findNode(n.data.id).length) {
            cy.add({ data: { ...n.data, draft: true }, classes: (n.classes || '') + ' draft' });
            draftGraph.nodes.add(n.data.id);
          }
        }
        for (const e of tree.edges || []) {
          const eid = `draft-${e.data.id}`;
          if (!cy.getElementById(eid).length) {
            cy.add({ data: { ...e.data, id: eid }, classes: (e.classes || '') + ' draft' });
            draftGraph.edges.add(eid);
          }
        }
      }
    }
    const tgt = findNode(target);
    if (tgt.length) {
      const eid = `draft-${source}→${target}`;
      if (!cy.getElementById(eid).length) {
        cy.add({ data: { id: eid, source, target, label: '草稿' }, classes: 'draft action' });
        draftGraph.edges.add(eid);
      }
    }
  }
}
```

- [ ] **Step 4: pushDraft 后调用 + 保存/放弃清理**

`pushDraft` 末尾（各视图分支后）调用 `updateDraftGraph()`（async，不 await）：

```js
  updateDraftGraph();
```

`saveAll` 成功分支与 `discardAll`：`loadGraph` 已重载正式图（草稿态图被替换）；`loadGraph` 中补充清空 `draftGraph` 集合：

```js
// loadGraph 内（draftOps=[] 附近）：
draftGraph.nodes.clear(); draftGraph.edges.clear();
```

- [ ] **Step 5: 验证**

`node --check`；playwright：
- #5：清空 action（删所有标签）→ 保存 → test.txt 中 action 行被删除（git diff）
- #6：选中 test → action 添加 `goto-home` → 图上实时出现 goto-home 节点 + 边 + 其链路（跨文件）；删除该标签 → 链路移除；保存 → 正式图重载；放弃 → 草稿态图清除

- [ ] **Step 6: 提交（先请用户验证 Task 3）**

```bash
git add taskView/static/index.html
git commit -m ":sparkles: taskView 图：草稿 action 实时连线 + 跨文件链路 + 空值提交"
```

---

## Self-Review

- [ ] **Spec 覆盖核对**：
  - §3 #1 字段分组 → Task 2 Step 1
  - §4 #2/#3/#4 引用输入组件 → Task 2 Step 2-6
  - §5 #5 清空删字段 → Task 1（后端）+ Task 3 Step 1（前端）
  - §6 #6 图实时连线 → Task 3 Step 2-4
- [ ] **占位符扫描**：无 TBD/TODO；每步含具体代码。
- [ ] **类型一致**：`delete_option`/`updateDraftGraph`/`getDraftCandidates` 签名跨任务一致；`MULTI_REF_FIELDS`/`SINGLE_REF_FIELDS` 常量在 Task 2 定义 Task 3 复用。
