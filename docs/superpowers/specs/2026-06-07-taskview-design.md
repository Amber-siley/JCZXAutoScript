# taskView — 配置文件执行路径可视化工具

**日期：** 2026-06-07  
**状态：** 已设计，待实现

## 1. 概述

taskView 是一个面向开发者的独立子项目，用于可视化展示 JCZX 配置文件（TxtConfig 格式）中定义的自动化任务执行路径与分支。展示形式类似程序流程图。

不影响原项目的任何运行逻辑，仅通过 `import` 读取原项目模块。

## 2. 核心决策

| 决策 | 选择 |
|------|------|
| 可视化模式 | 静态解析（不涉及实际运行） |
| 后端 | Python FastAPI |
| 前端 | 单页 HTML + Cytoscape.js（CDN 加载，零 npm 构建） |
| 启动方式 | `python -m taskView` → 启动 HTTP 服务 → 自动打开浏览器 |
| 图布局 | dagre（层次有向无环图布局） |
| 搜索/过滤 | 不需要 |
| 导出图片 | 需要（PNG + SVG） |

## 3. 文件结构

```
taskView/             # 根目录下新建
├── __init__.py
├── __main__.py       # 入口：uvicorn.run() + webbrowser.open()
├── server.py         # FastAPI app + 路由
├── graph_builder.py  # 读取配置 → 构建节点 + 边 JSON
└── static/
    └── index.html    # Cytoscape.js 单页应用
```

共 4 个 Python 文件 + 1 个 HTML 文件。完全不修改 `jczx/` 目录下任何现有文件。

## 4. 数据模型

### 4.1 节点 (Node)

```json
{
  "data": {
    "id": "launch-game",
    "label": "启动游戏",
    "type": "task",
    "parent": null,
    "desc": "主入口任务",
    "sleep": 0.0,
    "per": 0.8,
    "times": 1
  },
  "classes": "task"
}
```

| 字段 | 来源 | 说明 |
|------|------|------|
| `id` | section 名 | 唯一标识 |
| `label` | `entity.name` | 显示文本 |
| `type` | `entity.type` | task/func/click/dynamic/settings |
| `parent` | 保留 | 用于复合节点 |
| `desc` | `entity.desc` | 描述 |
| 其他 | entity 对应字段 | 供详情面板使用 |

### 4.2 边 (Edge)

```json
{
  "data": {
    "id": "launch-game→launch-game-plan",
    "source": "launch-game",
    "target": "launch-game-plan",
    "label": "action"
  },
  "classes": "action"
}
```

**边的来源映射：**

| 源字段 | 边标签 | 线型 |
|--------|--------|------|
| `action[]` | "action" | 实线 + 箭头 |
| `condition` / `condition_not` | "condition" | 虚线 + 箭头 |
| `condition_then[]` | "condition_then" | 虚线 + 箭头 |
| `condition_else[]` | "condition_else" | 点线（更疏）+ 箭头 |
| `extend` | "extend" | 灰色虚线，无箭头 |
| `settings` | "settings" | 灰色实线，无箭头 |

## 5. API 设计

基路径：`http://localhost:8000`

| 方法 | 路径 | 返回 | 说明 |
|------|------|------|------|
| `GET` | `/api/files` | `["MainMenu.txt", "Config.txt", ...]` | 列出 `jczx/Config/` 下所有 `.txt` |
| `GET` | `/api/graph?file=MainMenu.txt` | `{nodes: [...], edges: [...]}` | 完整图数据 |
| `GET` | `/api/entity/{name}?file=MainMenu.txt` | `{...}` | 单个实体完整字段 |

## 6. 视觉规范

### 6.1 节点颜色

| type | 颜色 | 形状 |
|------|------|------|
| `task` | `#42a5f5` 蓝色 | 圆角矩形 |
| `func` | `#66bb6a` 绿色 | 胶囊形（大圆角） |
| `click` | `#ffa726` 橙色 | 胶囊形 |
| `dynamic` | `#ab47bc` 紫色 | 胶囊形 |
| `settings` | `#78909c` 灰色 | 圆角矩形 |

### 6.2 边样式

- **action**：实线 + 箭头（`#888`）
- **condition**：虚线 + 箭头（`#4fc3f7` 浅蓝）
- **condition_then**：虚线 + 箭头（`#66bb6a` 绿色）
- **condition_else**：点线 + 箭头（`#ef5350` 红色）
- **extend**：灰色虚线，无箭头
- **settings**：灰色实线，无箭头

### 6.3 布局

默认 dagre 层次布局，方向 LR（左到右）。同时提供 breadthfirst 和 fcose 作为切换选项。

## 7. UI 布局（三栏式）

```
┌───────────┬──────────────────────────┬────────────┐
│  侧栏     │                          │  详情面板   │
│  (220px)  │    Cytoscape.js 画布     │  (240px)   │
│           │                          │            │
│ 文件列表  │   可拖拽 / 滚轮缩放      │ 选中节点   │
│ 统计信息  │   dagre 布局渲染         │ 完整字段   │
│ 布局切换  │                          │            │
│ 导出按钮  │                          │            │
└───────────┴──────────────────────────┴────────────┘
```

## 8. 交互清单

- 拖拽节点
- 滚轮缩放画布
- 点击节点 → 右侧显示详情
- 悬停边 → tooltip 显示类型
- 切换布局算法（dagre / breadthfirst / fcose）
- 切换配置文件（左侧文件列表）
- 导出 PNG / SVG
- 重新加载当前文件

## 9. 依赖

| 依赖 | 来源 | 说明 |
|------|------|------|
| FastAPI | SDE 虚拟环境（需安装） | 后端框架 |
| uvicorn | SDE 虚拟环境（需安装） | ASGI 服务器 |
| cytoscape | CDN (unpkg) | 图渲染核心 |
| cytoscape-dagre | CDN (unpkg) | dagre 布局扩展 |
| cytoscape-svg | CDN (unpkg) | SVG 导出扩展 |
| canvas-toBlob | CDN | PNG 导出辅助 |

## 10. 实现要点

1. **复用原项目模块**：`from jczx.CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig` 和 `from jczx.configEntity import JczxSectionEntity` 和 `from jczx.taskManage import TaskManage`
2. **零侵入**：`taskView/` 是完全独立的目录，不修改 `jczx/` 下任何文件
3. **graph_builder.py** 核心逻辑：读取配置文件 → 构建实体池 → 遍历每个实体，提取 action/condition/condition_then/condition_else/extend/settings → 生成 nodes 数组 + edges 数组
4. **自动打开浏览器**：`__main__.py` 中 `threading.Timer(1.0, lambda: webbrowser.open('http://localhost:8000')).start()`
5. **CORS**：不需要（同源单页应用，静态文件由 FastAPI 直接 serve）
