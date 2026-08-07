# taskView

交错战线手游自动化脚本 — 配置文件执行路径可视化工具。

解析 `jczx/Config/*.txt` 中的任务定义，以程序流程图形式展示 section 之间的 `action` / `condition` / `extend` 链路。

## 启动

```powershell
uv run python -m taskView
```

浏览器自动打开 `http://localhost:8000`。依赖由根 `pyproject.toml`（uv）管理，无需独立虚拟环境。

## 功能

- 选择并加载任意 `.txt` 配置文件，dagre 层次布局展示任务执行有向图，按 `type` 着色区分（task / func / click / dynamic / settings）
- 边按链接类型区分线型和颜色（action 实线、condition 虚线、extend 点线等）
- 拖拽节点、滚轮缩放画布；点击节点查看完整字段详情，右侧面板可折叠
- 切换布局算法（dagre / breadthfirst / fcose）；导出 PNG / SVG
- **可视化编辑**：点击节点以表单编辑字段（按 type 分组渲染），引用字段自动补全
- **实体管理**：新增 / 复制 / 删除，草稿暂存 + 显式保存（原子写回，保留注释与顺序）
- **严格校验**：保存前校验引用完整、重名、字段类型、占位符与资源存在，出错不写盘

## 结构

```
taskView/
├── __main__.py          # 入口：uvicorn + 自动打开浏览器
├── server.py            # FastAPI 路由
├── graph_builder.py     # 解析 TxtConfig → 节点/边 JSON
└── static/
    └── index.html       # Cytoscape.js 前端
```

## 依赖

- Python 3.11+ · FastAPI · uvicorn
- 复用 `jczx/` 下的 `TxtConfig`、`JczxSectionEntity`、`TaskManage`
- 前端 CDN：Cytoscape.js + dagre + cytoscape-dagre + cytoscape-fcose + cytoscape-svg
