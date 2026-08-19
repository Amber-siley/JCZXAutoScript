# taskView 需求文档（重实现依据）

> 本文件是 taskView 子项目的**唯一需求依据**，供后续重新实现使用。
> 原实现位于 `taskView/`（将被删除）。历史设计/测试细节保留在 `docs/superpowers/specs/2026-0*-taskview-*.md` 供追溯。
> **日期：** 2026-08-15

---

## 1. 项目定位与背景

面向开发者的**配置可视化 + 可视化编辑器**，用于交错战线自动化脚本的 TxtConfig 配置文件。

- **背景问题**：手动编辑 `jczx/Config/MainMenu.txt` 与 `jczx/Config/tasks/*.txt` 高度重复（克隆相似实体、改 `target`/`action`/`sleep` 等），配置写错会破坏自动化运行。
- **定位**：独立子项目，**不参与自动化运行**，对 `jczx/` **零侵入**（仅 `import` 复用模块）。
- **可视化模式**：静态解析，不涉及实际运行。

## 2. 目标与非目标

### 目标
1. **只读流程图可视化**：解析配置中 section 之间的 `action`/`condition`/`extend`/`settings`/占位符链路，以程序流程图展示。
2. **可视化配置编辑**：表单 + 图联动，完成实体字段编辑、实体增删复制重命名、图结构编辑。
3. **严格校验**：保存前校验引用/类型/资源/占位符，出错不写盘。
4. **写回保真**：保留注释、空行、顺序与 EOL（CRLF/LF）。

### 非目标
- 不提供任务向导（模板化生成整串实体）。
- 不编辑 `Config.txt`（全局设置）与 `Queues.txt`（队列）。
- 不做图上拖拽连线（编辑走表单，保存后图自动重排）。
- 不提供撤销/重做历史（草稿 + 显式保存已提供反悔入口）。

## 3. 运行方式与环境

```powershell
uv run python -m taskView     # 依赖由根 pyproject.toml（uv）管理，无独立虚拟环境
```
- 后端：FastAPI + uvicorn，`127.0.0.1:8000`，启动 1 秒后自动打开浏览器。
- 前端：单页 `index.html` + **Cytoscape.js**（CDN 加载，零 npm 构建），扩展：dagre / cytoscape-dagre / cytoscape-fcose / cytoscape-svg。
- 复用 jczx 模块：`TxtConfig`、`JczxSectionEntity`、`JczxSettingEntity`、`SectionType`、`JCZXGaming`（仅校验 `func` 方法存在时用到）。

## 4. 架构与模块

```
taskView/
├── __main__.py          # 入口：uvicorn.run() + webbrowser.open()
├── server.py            # FastAPI 路由（约 107 行）
├── graph_builder.py     # 解析配置 → 节点/边 JSON（约 518 行）
├── editor.py            # ConfigEditor 行级 patch 写回 + 严格校验（约 530 行）
└── static/
    └── index.html       # Cytoscape.js 前端（约 1334 行）
```

## 5. 数据模型

### 节点（Node）
```json
{ "data": { "id": "launch-game", "label": "启动游戏", "type": "task",
            "desc": "", "sleep": 0.0, "per": 0.8, "times": 1, ... }, "classes": "task" }
```
- `id` = section 名；`label` = `name`/`desc`/id 兜底；`type` = 实体类型。
- `classes` 扩展：`condition-entity`（条件引用方或被引用方）、`breakpoint`、`file-entity`、`external`（跨文件引用节点，标注来源文件）。

### 边（Edge）
| 源字段 | 边标签 | 线型 |
|--------|--------|------|
| `action[]` | 序号/空 | 实线 + 箭头 |
| `condition` / `condition_not` | 条件 | 虚线 + 箭头 |
| `condition_then[]` | 是 | 虚线 + 箭头 |
| `condition_else[]` | 否 | 点线 + 箭头 |
| `extend` | 继承 | 灰色虚线，无箭头 |
| `settings` | 设置 | 灰色实线，无箭头 |
| 占位符 `@{}`/`${}`/`%{}`/`&{}` | 对应表达式 | execute / config / context / expression |

- **引用解析**：当前文件实体 → 普通节点；跨文件 → `external` 节点（含 `file` 字段标注来源）。
- **占位符建边**：`@{}` 引用实体建边；`${}`/`%{}`/`&{}` 尝试解析建边；跨文件占位符不建边。

### 布局
默认 dagre（LR 层次），可选 breadthfirst / fcose。支持导出 PNG / SVG。

## 6. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/files` | 列出 `jczx/Config/` 下全部 `.txt`（含 `tasks/*.txt`） |
| `GET` | `/api/graph?file=` | 完整图数据（`{nodes, edges}`）；空 → 404 |
| `GET` | `/api/entity/{name}?file=` | 单个实体完整字段 + `explicit`（文件显式声明的字段，供复制精简） |
| `GET` | `/api/entities` | 实体池候选（key+label+type），供自动补全 |
| `GET` | `/api/flow?file=&task=` | 单任务流程树（`{nodes, edges, cycles}`），节点 id 带 `#N` 实例后缀 |
| `POST` | `/api/file/{file}/validate` | 草稿预校验（不写盘）→ `{errors}` |
| `POST` | `/api/file/{file}/apply` | `{ops, base_hash}` → 模拟应用 → 严格校验 → 原子写回 → 新图 + 新 hash |

**apply 流程**：
1. `base_hash` 与磁盘当前哈希不符 → `409` 拒绝，提示重新加载。
2. 在当前实体池快照上**模拟应用**全部 ops（不污染加载结果）。
3. **严格校验**（见 §7.3）；有错 → `422` 返回错误列表，**不写任何文件**。
4. 通过 → 按变更明细写回 → 返回新图数据与 `file_hash`。

## 7. 可视化编辑核心机制

### 7.1 ConfigEditor —— 行级 patch 写回（保真基石）

读文件原始行数组，保留 EOL（`\r\n`/`\n`）与末尾换行；每行标注类型：`comment`（`/` 或 `//` 开头）、`section`、`option`、`blank`。

**已验证的关键事实**：实体文件**无行内注释**（`/` 均出现在行首），但 value 可以以 `/` 开头（如 `action: /|%{x}`）。故 option 行解析为二元组 `(key, value)`，**value = `key : ` 后到行尾去尾空白，不切分行内注释**。

**操作**：
| 操作 | 行为 |
|------|------|
| `update_value` | 整行替换 `key : 新值`，保留原行前缀 |
| `add_option` | 实体末尾追加字段行（用于 extend 继承字段落盘） |
| `delete_option` | 删除指定字段行（清空字段 = 删除行） |
| `add_entity` | 文件末尾追加 `\n[key]` + 字段行 |
| `delete_entity` | 删除 option + section 头 + 紧邻分隔空行（保守保留注释） |
| `rename_entity` | 重写 section 头，自动同步更新所有引用旧 key 的字段 |

**原子写回**：`mkstemp` 临时文件 + `os.replace`，中途失败不留半文件，保留 EOL 字节风格。

### 7.2 变更集（draft ops）

前端草稿攒成**变更集**（list of ops），一次保存 = 一次原子提交。

| op | 结构 | 说明 |
|----|------|------|
| `update` | `{key, fields}` | 修改实体字段；同批 update 合并 |
| `create` | `{key, entity}` | 新增实体（只写 op 提供的字段，不转写默认值） |
| `delete` | `{key}` | 删除实体 |
| `rename` | `{old, new}` | 重命名 + 后端跨文件同步更新引用 |

**写回只按变更明细**（不遍历实体全字段），避免把默认值/未变更字段一并落盘。空字符串字段 → 删除对应 option 行（语义"清空"）。

### 7.3 校验规则（严格，宁可漏检不可误报）

在模拟应用后的**跨文件实体池快照**上执行：

1. **重名**：同文件内 key 唯一；跨文件重名拒绝（与 `_load_one` 的 `ValueError` 一致）。
2. **引用完整**：`action`/`condition`/`condition_not`/`condition_then`/`condition_else`/`extend`/`match` → 实体必须存在于实体池（跨文件）；`match`/`context` 的 `action` 是操作指令（`+|1`、`right|1`），**不做引用校验**。
3. **settings**（task 类型）→ 必须指向 `settings` 实体。
4. **target**（click/match/ocr）→ 校验 `jczx/resources/` 下图片存在；**含占位符的 target 跳过存在性校验**。
5. **func**（func 类型）→ 方法必须存在于 `JCZXGaming`。
6. **字段类型**：float/int 转换错误（复用 `__setattr__`，捕获 `ValueError`）。
7. **占位符深层**：
   - `${}`/`@{}`/`%{}`/`&{}` 括号闭合（未闭合报错）。
   - `@{}` 引用的实体必须存在（跨文件）。
   - `%{}`/`&{}` 跳过（运行时确定，区间内不深检，避免误报如 `&{%{x} | @{missing}}`）。
   - `${}` 不做存在性硬校验（配置值 section 常由运行时创建）。
8. **type 合法**：必须是 `SectionType` 枚举值。

**错误返回**：`[{file, key, field, message}]`，前端定位到节点标红。

## 8. 前端交互

### 8.1 布局（三栏）
```
┌───────────┬──────────────────────────┬────────────┐
│  侧栏     │   Cytoscape.js 画布      │  详情面板   │
│ 文件列表  │   可拖拽 / 滚轮缩放      │ 节点详情/   │
│ 任务列表  │   graph/flow 视图        │ 编辑表单    │
│ 布局切换  │   导出 PNG/SVG           │ 可折叠      │
│ 边过滤    │                          │            │
└───────────┴──────────────────────────┴────────────┘
```

### 8.2 视图
- **graph 视图**：按当前文件渲染完整图；边过滤（按类型开关）；任务列表过滤。
- **flow 视图**：单任务流程树，递归展开 action/condition 分支；**循环检测**（`⟲` 标记）；节点 id 带 `#N` 后缀；可折叠子树。

### 8.3 编辑表单
- 字段按 type 分组渲染（common + 各 type 专有字段）；**type 切换即时重渲染表单**。
- 字段分类：
  - **多实体引用**（逗号串，标签式 + 智能下拉）：`action`、`condition_then`、`condition_else`、`wait_sec`、`fields`。
  - **单实体引用**（下拉/输入）：`match`、`condition`、`condition_not`、`extend`、`settings`。
  - **list 非引用**（逗号串普通输入）：`args`、`options`、`pos`。
  - 普通字段：`target`、`per`、`sleep` 等。
- **自动补全候选** = 全局实体池 + 草稿 `create` 实体（标注 `(草稿)`）。
- 编辑即入草稿（记录有变化的字段）；`type` 变更合并进同 key 的 update op。

### 8.4 实体管理
- 右键菜单：复制 / 新建 / 粘贴 / 删除。
- **新增**：新建时即校验 key 唯一（实体池 + 草稿），冲突提示重新输入。
- **复制/粘贴**：只复制 `explicit` 显式字段（避免默认值污染配置）；新 key 自动唯一后缀（`-copy`/`-copy2`）。
- **删除**：确认弹窗；删除被引用实体由校验拦截。

### 8.5 草稿与保存
- **草稿栏**：未保存改动列表 + 保存 / 放弃按钮；改动节点加黄色脏标记。
- **草稿 action 实时连线**：编辑时实时显示引用边（虚线、半透明），跨文件用 `/api/flow` 展开完整链路；有代际计数防止幽灵草稿。
- **保存**：`POST /apply`；失败保留草稿；409 提示外部修改；422 定位错误。
- **放弃**：清空草稿，从服务器重载图。
- **乐观更新**：新增/删除立即反映在图中（保存后才真正落盘）。

## 9. 已知问题清单（重实现必须处理）

> 来源：`docs/superpowers/specs/2026-08-07-taskview-test-issues.md`（2026-08-07 测试快照；其中"type 不可编辑"已实现为下拉，其余待确认）。

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| 1 | 实体 `type` 不可编辑 | 中 | type 下拉（**已实现**，保留） |
| 2 | `settings` 容器 `fields` / `setting` 专有字段表单缺失 | 中 | 表单补 settings/setting 专有字段 |
| 3 | 选中未保存新节点 → `/api/entity` 404（console 噪音） | 低 | 对 dirty/新建节点跳过 fetch，用节点信息构造表单 |
| 4 | graph 视图不显示跨文件引用边 | 低 | 设计局限（graph=单文件）；如需展示需加载全部实体池 |
| 5 | 新增实体默认 `target` 触发图片校验拦截，UX 引导不足 | 低 | 新增默认 target 留空或提示先填 |
| 6 | flow 视图选中跨文件节点 → 字段值丢失（404 兜底只有 key/type） | 中 | tap 用节点实际来源文件请求 detail，或 `/api/entity` 全局按 key 查 |
| 7 | flow 视图节点脏标记 / 删除标红失效（id 带 `#N` 后缀） | 低-中 | 查找用 `cy.$('[id^="key#"]')` 匹配 |

## 10. 与主项目的耦合点（主项目已变动，重实现需同步）

taskView 复用的 jczx 模块/常量，主项目已发生如下变动：

1. **新增类型 `method` / `call`**（`SectionType.METHOD`/`CALL`）：图构建按 type 着色、表单按 type 分组、`get_entity_detail` 字段输出，都要支持这两个类型。
2. **`JczxSectionEntity` 新增字段**：`fn`（call 目标）、`params` / `param_defaults`（method）、`values`（context 批量初始化）。表单/校验/显式字段都要覆盖。
3. **图片池懒加载**：`target` 图片存在性校验仍指向 `jczx/resources/`；`call` 动态图片路径不做静态校验（与校验规则 §7.3 一致）。
4. 既有字段 `wait_target_sleep` 等已入 configEntity，表单 common 字段表需与之对齐。

## 11. 重实现建议（架构取舍）

1. **字段定义单一来源**：前端 `buildEntityForm` 硬编码的字段分组（common/byType）与 `configEntity.py` 已多次漂移。重实现应让字段分组由 `SectionType`/dataclass 元数据驱动（后端下发字段 schema），避免再次漂移。
2. **前后端职责分离**：图构建（graph_builder）与校验（editor）是纯逻辑，可抽成独立模块 + 单元测试（本项目已引入 pytest，可直接覆盖）。
3. **校验独立可测**：`simulate_and_validate` 已是纯函数风格，重实现时保持，补测试。
4. **前端构建取舍**：原实现用 CDN + 单 HTML（零构建），简单但难以做组件化/测试。若重实现偏向可维护，可考虑轻量构建（Vite + 组件化）；若求快，保留单 HTML。
5. **已知问题前置修复**：§9 的问题 2/6/7 是 flow 视图与 settings 编辑的实质缺陷，重实现时应直接按建议方案做，而非照搬。
6. **保留历史参考**：`docs/superpowers/specs/2026-0*-taskview-*.md` 含详细设计/测试用例，重实现时可参考；但以本文档为唯一需求依据。
