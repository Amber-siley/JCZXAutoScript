# taskView 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 构建 taskView 子项目，通过 FastAPI + Cytoscape.js 静态解析并可视化展示配置文件中的任务执行路径

**架构：** 复用于 `jczx/` 的 TxtConfig + JczxSectionEntity 解析层，graph_builder 将实体池转换为 Cytoscape.js 兼容的节点/边 JSON，FastAPI 提供 3 个 REST 端点，单页 HTML 渲染交互式有向图

**技术栈：** Python 3.11+ · FastAPI · uvicorn · TxtConfig · Cytoscape.js (CDN) · cytoscape-dagre (CDN)

---

## 文件结构

```
taskView/                    ← 新建
├── __init__.py              ← 空文件
├── __main__.py              ← uvicorn 启动 + 自动打开浏览器
├── server.py                ← FastAPI app + 路由
├── graph_builder.py         ← 配置解析 → 图数据 JSON
└── static/
    └── index.html           ← Cytoscape.js 单页应用
```

---

### Task 1: 项目脚手架

**文件：**
- 创建: `taskView/__init__.py`
- 创建: `taskView/__main__.py`
- 创建: `taskView/static/` (目录)

- [ ] **Step 1: 创建目录和空 __init__.py**

```powershell
New-Item -ItemType Directory -Force -Path "taskView\static"
New-Item -ItemType File -Force -Path "taskView\__init__.py"
```

- [ ] **Step 2: 编写 __main__.py 入口**

```python
import uvicorn
import webbrowser
import threading
import os
import sys


def open_browser():
    webbrowser.open("http://localhost:8000")


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    threading.Timer(1.0, open_browser).start()
    uvicorn.run(
        "taskView.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 验证可启动（预期先报错 server 模块不存在）**

```powershell
python -m taskView
```

- [ ] **Step 4: 提交**

```bash
git add taskView/__init__.py taskView/__main__.py
git commit -m "feat(taskView): add project scaffold with entry point"
```

---

### Task 2: 图构建器 graph_builder.py

**文件：**
- 创建: `taskView/graph_builder.py`

- [ ] **Step 1: 编写 graph_builder.py**

```python
import os
from typing import Any

from jczx.CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig
from jczx.configEntity import JczxSectionEntity, SectionType


CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "jczx", "Config"
)


def list_config_files() -> list[str]:
    files = []
    if os.path.isdir(CONFIG_DIR):
        for name in os.listdir(CONFIG_DIR):
            if name.endswith(".txt"):
                files.append(name)
    files.sort()
    return files


def _resolve_extends(configs: dict[str, JczxSectionEntity]) -> None:
    default_entity = JczxSectionEntity()
    for key, entity in configs.items():
        if not entity.extend:
            continue
        parent = configs.get(entity.extend)
        if not parent:
            continue
        for field_name in entity.__dataclass_fields__:
            if field_name == "extend":
                continue
            child_val = getattr(entity, field_name)
            if child_val == getattr(default_entity, field_name):
                setattr(entity, field_name, getattr(parent, field_name))


def build_graph(filename: str) -> dict[str, list[dict[str, Any]]]:
    filepath = os.path.join(CONFIG_DIR, filename)
    if not os.path.isfile(filepath):
        return {"nodes": [], "edges": []}

    config = TxtConfig(filepath)
    configs = config.trans_entity_dict(JczxSectionEntity)
    _resolve_extends(configs)

    for key, entity in configs.items():
        entity.only_key = key

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    def _add_node(entity: JczxSectionEntity) -> str:
        nid = entity.only_key
        if nid in seen_node_ids:
            return nid
        seen_node_ids.add(nid)
        nodes.append({
            "data": {
                "id": nid,
                "label": entity.name or entity.desc or nid,
                "type": entity.type or "",
                "desc": entity.desc or "",
                "func": entity.func or "",
                "target": entity.target or "",
                "sleep": entity.sleep,
                "per": entity.per,
                "times": entity.times,
                "max_wait": entity.max_wait,
                "break_point": entity.break_point,
            },
            "classes": entity.type or "",
        })
        return nid

    def _add_edge(source_id: str, target_id: str, label: str, classes: str):
        if not target_id:
            return
        eid = f"{source_id}→{target_id}::{label}"
        if eid in seen_edge_ids:
            return
        seen_edge_ids.add(eid)
        edges.append({
            "data": {
                "id": eid,
                "source": source_id,
                "target": target_id,
                "label": label,
            },
            "classes": classes,
        })

    for key, entity in configs.items():
        _add_node(entity)

    for key, entity in configs.items():
        src = entity.only_key

        for target in entity.action:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "action", "action")

        if entity.condition and entity.condition in configs:
            _add_node(configs[entity.condition])
            _add_edge(src, entity.condition, "condition", "condition")
        if entity.condition_not and entity.condition_not in configs:
            _add_node(configs[entity.condition_not])
            _add_edge(src, entity.condition_not, "condition_not", "condition_not")

        for target in entity.condition_then:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "condition_then", "condition_then")
        for target in entity.condition_else:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "condition_else", "condition_else")

        if entity.extend and entity.extend in configs:
            _add_edge(src, entity.extend, "extend", "extend")

        if entity.type == SectionType.TASK.value and getattr(entity, "settings", None):
            settings_key = getattr(entity, "settings", "")
            if settings_key and settings_key in configs:
                _add_node(configs[settings_key])
                _add_edge(src, settings_key, "settings", "settings")

    return {"nodes": nodes, "edges": edges}


def get_entity_detail(filename: str, entity_name: str) -> dict[str, Any] | None:
    filepath = os.path.join(CONFIG_DIR, filename)
    if not os.path.isfile(filepath):
        return None

    config = TxtConfig(filepath)
    configs = config.trans_entity_dict(JczxSectionEntity)
    _resolve_extends(configs)

    if entity_name not in configs:
        return None

    entity = configs[entity_name]
    entity.only_key = entity_name
    return {
        "key": entity_name,
        "type": entity.type or "",
        "name": entity.name or "",
        "desc": entity.desc or "",
        "func": entity.func or "",
        "target": entity.target or "",
        "action": entity.action,
        "args": entity.args,
        "pos": entity.pos,
        "pre_sleep": entity.pre_sleep,
        "sleep": entity.sleep,
        "per": entity.per,
        "max_wait": entity.max_wait,
        "wait_sec": entity.wait_sec,
        "condition": entity.condition or "",
        "condition_not": entity.condition_not or "",
        "condition_then": entity.condition_then,
        "condition_else": entity.condition_else,
        "break_point": entity.break_point,
        "extend": entity.extend or "",
        "times": entity.times,
    }
```

- [ ] **Step 2: 验证 graph_builder 可独立运行**

```powershell
python -c "from taskView.graph_builder import list_config_files, build_graph; files = list_config_files(); print('Config files:', files); if files: g = build_graph(files[0]); print('Nodes:', len(g['nodes']), 'Edges:', len(g['edges']))"
```

- [ ] **Step 3: 提交**

```bash
git add taskView/graph_builder.py
git commit -m "feat(taskView): add graph builder for config file parsing"
```

---

### Task 3: FastAPI 服务 server.py

**文件：**
- 创建: `taskView/server.py`

- [ ] **Step 1: 编写 server.py**

```python
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from .graph_builder import list_config_files, build_graph, get_entity_detail

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="taskView", version="1.0.0")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/files")
async def api_files():
    return list_config_files()


@app.get("/api/graph")
async def api_graph(file: str = Query(..., description="Config filename, e.g. MainMenu.txt")):
    result = build_graph(file)
    if not result["nodes"] and not result["edges"]:
        raise HTTPException(status_code=404, detail=f"File not found or empty: {file}")
    return result


@app.get("/api/entity/{name}")
async def api_entity(name: str, file: str = Query(..., description="Config filename")):
    detail = get_entity_detail(file, name)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {name}")
    return detail
```

- [ ] **Step 2: 安装 FastAPI 和 uvicorn（如果尚未安装）**

```powershell
.\sde\Scripts\activate; pip install fastapi uvicorn
```

- [ ] **Step 3: 启动服务验证 3 个端点**

启动服务：
```powershell
python -m taskView
```

然后用 curl 或浏览器验证：
- `http://localhost:8000/` → 应返回 index.html（此时文件尚不存在会 404，但路由应生效）
- `http://localhost:8000/api/files` → 应返回 JSON 数组，如 `["Config.txt", "MainMenu.txt"]`
- `http://localhost:8000/api/graph?file=MainMenu.txt` → 应返回 `{"nodes": [...], "edges": [...]}`
- `http://localhost:8000/api/entity/launch-game?file=MainMenu.txt` → 应返回实体详情 JSON

- [ ] **Step 4: 提交**

```bash
git add taskView/server.py
git commit -m "feat(taskView): add FastAPI server with graph and entity endpoints"
```

---

### Task 4: 前端 Cytoscape.js 页面

**文件：**
- 创建: `taskView/static/index.html`

- [ ] **Step 1: 编写 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>taskView — 任务执行流程图</title>
<script src="https://unpkg.com/cytoscape@3.30.4/dist/cytoscape.min.js"></script>
<script src="https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"></script>
<script src="https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"></script>
<script src="https://unpkg.com/cytoscape-svg@1.6.0/cytoscape-svg.js"></script>
<script src="https://unpkg.com/canvas-toBlob@1.0.0/canvas-toBlob.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #ccc; display: flex; height: 100vh; overflow: hidden; }

#sidebar { width: 220px; background: #16213e; display: flex; flex-direction: column; border-right: 1px solid #0f3460; flex-shrink: 0; }
#sidebar h2 { padding: 12px; font-size: 16px; color: #e94560; border-bottom: 1px solid #0f3460; }
#sidebar .section { padding: 10px 12px; border-bottom: 1px solid #0f3460; }
#sidebar .section h3 { font-size: 12px; color: #888; margin-bottom: 6px; text-transform: uppercase; }
#file-list { list-style: none; max-height: 200px; overflow-y: auto; }
#file-list li { padding: 6px 8px; cursor: pointer; border-radius: 3px; font-size: 13px; margin: 2px 0; }
#file-list li:hover { background: #0f3460; }
#file-list li.active { background: #e94560; color: #fff; }
#stats { font-size: 12px; margin-top: auto; padding: 10px 12px; border-top: 1px solid #0f3460; }
.layout-switch { display: flex; gap: 4px; flex-wrap: wrap; }
.layout-switch button { padding: 4px 8px; border: 1px solid #0f3460; background: #1a1a2e; color: #ccc; border-radius: 3px; cursor: pointer; font-size: 11px; }
.layout-switch button.active { background: #e94560; border-color: #e94560; color: #fff; }
.export-btns { display: flex; gap: 4px; }
.export-btns button { padding: 4px 10px; border: 1px solid #0f3460; background: #1a1a2e; color: #ccc; border-radius: 3px; cursor: pointer; font-size: 11px; }
.export-btns button:hover { background: #0f3460; }

#cy { flex: 1; min-width: 0; }

#detail { width: 260px; background: #16213e; border-left: 1px solid #0f3460; overflow-y: auto; flex-shrink: 0; }
#detail h2 { padding: 12px; font-size: 16px; color: #e94560; border-bottom: 1px solid #0f3460; position: sticky; top: 0; background: #16213e; }
#detail-content { padding: 12px; font-size: 13px; line-height: 1.7; }
#detail-content .key { color: #888; }
#detail-content .val { color: #e0e0e0; word-break: break-all; }
#detail-content .field { margin-bottom: 8px; }
#detail-content .tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; margin: 1px 2px; background: #0f3460; }
#detail-content .type-tag { background: #e94560; color: #fff; font-weight: bold; }
#detail-empty { padding: 40px 20px; text-align: center; color: #555; font-size: 13px; }
</style>
</head>
<body>

<div id="sidebar">
  <h2>taskView</h2>
  <div class="section">
    <h3>配置文件</h3>
    <ul id="file-list"><li>加载中…</li></ul>
  </div>
  <div class="section">
    <h3>布局</h3>
    <div class="layout-switch" id="layout-btns">
      <button data-layout="dagre" class="active">dagre</button>
      <button data-layout="breadthfirst">bfs</button>
      <button data-layout="fcose">fcose</button>
    </div>
  </div>
  <div class="section">
    <h3>导出</h3>
    <div class="export-btns">
      <button id="btn-png">PNG</button>
      <button id="btn-svg">SVG</button>
    </div>
  </div>
  <div id="stats">节点 0 · 边 0</div>
</div>

<div id="cy"></div>

<div id="detail">
  <h2>节点详情</h2>
  <div id="detail-content"><div id="detail-empty">点击画布中的节点查看详情</div></div>
</div>

<script>
let cy;
let currentFile = null;
let currentLayout = 'dagre';

const NODE_STYLES = {
  'task':     { 'background-color': '#42a5f5', 'border-color': '#1e88e5', 'shape': 'round-rectangle', 'text-outline-color': '#42a5f5' },
  'func':     { 'background-color': '#66bb6a', 'border-color': '#43a047', 'shape': 'ellipse', 'text-outline-color': '#66bb6a' },
  'click':    { 'background-color': '#ffa726', 'border-color': '#fb8c00', 'shape': 'ellipse', 'text-outline-color': '#ffa726' },
  'dynamic':  { 'background-color': '#ab47bc', 'border-color': '#8e24aa', 'shape': 'ellipse', 'text-outline-color': '#ab47bc' },
  'settings': { 'background-color': '#78909c', 'border-color': '#546e7a', 'shape': 'round-rectangle', 'text-outline-color': '#78909c' },
  'setting':  { 'background-color': '#78909c', 'border-color': '#546e7a', 'shape': 'round-rectangle', 'text-outline-color': '#78909c' },
};

const EDGE_STYLES = {
  'action':          { 'line-style': 'solid',  'line-color': '#888', 'target-arrow-color': '#888', 'target-arrow-shape': 'triangle' },
  'condition':       { 'line-style': 'dashed', 'line-color': '#4fc3f7', 'target-arrow-color': '#4fc3f7', 'target-arrow-shape': 'triangle' },
  'condition_not':   { 'line-style': 'dashed', 'line-color': '#4fc3f7', 'target-arrow-color': '#4fc3f7', 'target-arrow-shape': 'triangle' },
  'condition_then':  { 'line-style': 'dashed', 'line-color': '#66bb6a', 'target-arrow-color': '#66bb6a', 'target-arrow-shape': 'triangle' },
  'condition_else':  { 'line-style': 'dotted', 'line-color': '#ef5350', 'target-arrow-color': '#ef5350', 'target-arrow-shape': 'triangle' },
  'extend':          { 'line-style': 'dashed', 'line-color': '#555', 'target-arrow-shape': 'none' },
  'settings':        { 'line-style': 'solid',  'line-color': '#555', 'target-arrow-shape': 'none' },
};

function initCy() {
  cy = cytoscape({
    container: document.getElementById('cy'),
    style: [
      { selector: 'node', style: { 'label': 'data(label)', 'font-size': '12px', 'color': '#fff', 'text-valign': 'center', 'text-halign': 'center', 'width': 'label', 'height': 'label', 'padding': '8px', 'text-wrap': 'wrap', 'text-max-width': '120px', 'border-width': 2 } },
      ...Object.entries(NODE_STYLES).map(([cls, sty]) => ({ selector: `node.${cls}`, style: sty })),
      { selector: 'node:selected', style: { 'border-color': '#e94560', 'border-width': 3 } },
      { selector: 'edge', style: { 'width': 1.5, 'curve-style': 'bezier', 'font-size': '10px', 'color': '#888', 'text-background-color': '#1a1a2e', 'text-background-opacity': 0.8, 'text-background-padding': '2px', 'text-rotation': 'autorotate' } },
      ...Object.entries(EDGE_STYLES).map(([cls, sty]) => ({ selector: `edge.${cls}`, style: sty })),
    ],
    layout: { name: currentLayout, rankDir: 'LR', spacingFactor: 1.2 },
    wheelSensitivity: 0.3,
    minZoom: 0.1,
    maxZoom: 3,
  });

  cy.on('tap', 'node', async function (evt) {
    const node = evt.target;
    const entityName = node.data('id');
    if (!currentFile || !entityName) return;
    try {
      const res = await fetch(`/api/entity/${encodeURIComponent(entityName)}?file=${encodeURIComponent(currentFile)}`);
      const detail = await res.json();
      renderDetail(detail);
    } catch (e) {
      document.getElementById('detail-content').innerHTML = '<div id="detail-empty">加载详情失败</div>';
    }
  });

  cy.on('tap', function (evt) {
    if (evt.target === cy) {
      document.getElementById('detail-content').innerHTML = '<div id="detail-empty">点击画布中的节点查看详情</div>';
    }
  });
}

function renderDetail(d) {
  const fields = [
    ['类型', `<span class="tag type-tag">${esc(d.type)}</span>`],
    ['名称', esc(d.name || d.key)],
    ['描述', esc(d.desc)],
    ['方法', esc(d.func)],
    ['目标', esc(d.target)],
    ['action', d.action && d.action.length ? d.action.map(a => `<span class="tag">${esc(a)}</span>`).join('') : '—'],
    ['args', d.args && d.args.length ? d.args.map(a => `<span class="tag">${esc(a)}</span>`).join('') : '—'],
    ['condition', esc(d.condition)],
    ['condition_not', esc(d.condition_not)],
    ['condition_then', d.condition_then && d.condition_then.length ? d.condition_then.map(a => `<span class="tag">${esc(a)}</span>`).join('') : '—'],
    ['condition_else', d.condition_else && d.condition_else.length ? d.condition_else.map(a => `<span class="tag">${esc(a)}</span>`).join('') : '—'],
    ['extend', esc(d.extend)],
    ['sleep', `${d.sleep}s`],
    ['pre_sleep', `${d.pre_sleep}s`],
    ['per', d.per],
    ['max_wait', `${d.max_wait}s`],
    ['break_point', esc(d.break_point)],
    ['times', d.times],
  ];
  let html = `<div style="margin-bottom:8px;font-weight:bold;color:#e94560;">${esc(d.key)}</div>`;
  for (const [label, val] of fields) {
    if (!val || val === '—' || val === '') continue;
    html += `<div class="field"><span class="key">${label}:</span> <span class="val">${val}</span></div>`;
  }
  document.getElementById('detail-content').innerHTML = html || '<div id="detail-empty">无额外信息</div>';
}

function esc(s) { if (!s && s !== 0) return '—'; const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML; }

async function loadFiles() {
  try {
    const res = await fetch('/api/files');
    const files = await res.json();
    const list = document.getElementById('file-list');
    list.innerHTML = files.map(f => `<li data-file="${esc(f)}">${esc(f)}</li>`).join('');
    list.querySelectorAll('li').forEach(li => {
      li.addEventListener('click', () => {
        list.querySelectorAll('li').forEach(l => l.classList.remove('active'));
        li.classList.add('active');
        loadGraph(li.dataset.file);
      });
    });
    if (files.length > 0) {
      const first = list.querySelector('li');
      first.classList.add('active');
      loadGraph(files[0]);
    }
  } catch (e) {
    document.getElementById('file-list').innerHTML = '<li>加载失败</li>';
  }
}

async function loadGraph(filename) {
  currentFile = filename;
  try {
    const res = await fetch(`/api/graph?file=${encodeURIComponent(filename)}`);
    const data = await res.json();
    cy.json({ elements: { nodes: data.nodes, edges: data.edges } });
    cy.layout({ name: currentLayout, rankDir: 'LR', spacingFactor: 1.2 }).run();
    document.getElementById('stats').textContent = `节点 ${data.nodes.length} · 边 ${data.edges.length}`;
    document.getElementById('detail-content').innerHTML = '<div id="detail-empty">点击画布中的节点查看详情</div>';
  } catch (e) {
    console.error('Failed to load graph:', e);
  }
}

document.getElementById('layout-btns').addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  document.querySelectorAll('#layout-btns button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentLayout = btn.dataset.layout;
  if (cy) cy.layout({ name: currentLayout, rankDir: 'LR', spacingFactor: 1.2 }).run();
});

document.getElementById('btn-png').addEventListener('click', () => {
  if (!cy) return;
  const png64 = cy.png({ scale: 2, full: true, bg: '#1a1a2e' });
  const a = document.createElement('a');
  a.download = (currentFile || 'graph') + '.png';
  a.href = png64;
  a.click();
});

document.getElementById('btn-svg').addEventListener('click', () => {
  if (!cy) return;
  const svgContent = cy.svg({ scale: 1, full: true });
  const blob = new Blob([svgContent], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.download = (currentFile || 'graph') + '.svg';
  a.href = url;
  a.click();
  URL.revokeObjectURL(url);
});

initCy();
loadFiles();
</script>
</body>
</html>
```

- [ ] **Step 2: 启动服务并验证页面渲染**

```powershell
python -m taskView
```

打开浏览器访问 `http://localhost:8000`，验证：
- 左侧文件列表显示 `MainMenu.txt`、`Config.txt` 等
- 画布渲染有向图（dagre 布局）
- 点击节点 → 右侧显示详情
- 切换布局、导出 PNG/SVG

- [ ] **Step 3: 提交**

```bash
git add taskView/static/index.html
git commit -m "feat(taskView): add Cytoscape.js frontend with dagre layout and export"
```

---

### Task 5: 集成验证

- [ ] **Step 1: 全量启动验证**

```powershell
Start-Process -FilePath "python" -ArgumentList "-m", "taskView" -NoNewWindow
```

在浏览器中确认：
1. 首页加载，左侧文件列表显示配置文件
2. 默认加载 `MainMenu.txt`，画布显示有向图
3. 节点按 type 着色正确
4. 边有不同线型和标签
5. 点击节点，右侧详情面板显示完整字段
6. 切换 dagre → bfs → fcose → dagre，布局正常切换
7. 点击 PNG 导出，下载有效图片
8. 点击 SVG 导出，下载有效矢量图
9. 切换到 `Config.txt`，页面正常渲染

- [ ] **Step 2: 提交**

```bash
git add taskView/
git commit -m "chore(taskView): integration verification complete"
```
