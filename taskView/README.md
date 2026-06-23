# taskView

交错战线手游自动化脚本 — 配置文件执行路径可视化工具。

解析 `jczx/Config/*.txt` 中的任务定义，以程序流程图形式展示 section 之间的 `action` / `condition` / `extend` 链路。

## 启动

```powershell
.\sde\Scripts\activate
python -m taskView
```

浏览器自动打开 `http://localhost:8000`。

## 功能

- 选择并加载任意 `.txt` 配置文件
- dagre 层次布局展示任务执行有向图，按 `type` 着色区分（task / func / click / dynamic / settings）
- 边按链接类型区分线型和颜色（action 实线、condition 虚线、extend 点线等）
- 拖拽节点、滚轮缩放画布
- 点击节点查看完整字段详情，右侧面板可折叠
- 切换布局算法（dagre / breadthfirst / fcose）
- 导出 PNG / SVG

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
