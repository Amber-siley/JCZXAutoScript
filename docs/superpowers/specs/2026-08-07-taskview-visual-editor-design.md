# taskView 可视化配置编辑器设计

**日期：** 2026-08-07
**状态：** 已设计，待实现
**前置：** 基于 2026-06-07 taskview-design（只读图可视化）扩展

## 1. 概述

在现有 taskView 只读流程图可视化基础上，扩展为**可视化配置编辑器**。目标：替代手工编辑 TxtConfig 配置文件的重复劳动，通过表单 + 图联动完成实体字段编辑、实体增删与复制、图结构编辑。

**背景问题：** 手动编辑 `jczx/Config/MainMenu.txt` 与 `jczx/Config/tasks/*.txt` 高度重复（克隆相似实体、改 target/action/sleep 等）。配置写错会破坏自动化运行，需要可视化 + 严格校验。

## 2. 核心决策

| 决策 | 选择 |
|------|------|
| 编辑范围 | 字段表单编辑 + 实体增删与复制 + 图结构编辑 |
| 图编辑形式 | **表单联动**：图保持只读展示执行路径，编辑走表单，保存后图自动重排 |
| 保存策略 | **草稿暂存 + 显式保存**（一次保存 = 一次原子提交） |
| 写回机制 | **行级 patch**（自建 ConfigEditor），保留注释/空行/顺序 |
| 校验 | **严格校验阻止保存**（全有或全无，出错不写盘） |
| 文件范围 | 仅实体文件（`MainMenu.txt` + `tasks/*.txt`），不含 Config.txt / Queues.txt |
| 依赖与运行 | **uv 管理**：依赖在根 `pyproject.toml`，运行 `uv run python -m taskView`（不使用独立 sde 虚拟环境） |

## 3. 模块结构

```
taskView/
├── __main__.py          # 入口（不变）
├── server.py            # FastAPI 路由：新增 CRUD/校验/应用变更 API
├── graph_builder.py     # 只读图构建（不变，保存后复用于重排）
├── editor.py            # 新增：ConfigEditor（行级 patch 写回 + 严格校验）
└── static/
    └── index.html       # 前端：+编辑表单、草稿、自动补全、右键菜单
```

零侵入：不修改 `jczx/` 下任何文件。`editor.py` 仅 import 复用 jczx 的 `TxtConfig` / `JczxSectionEntity` / `SectionType`。

## 4. ConfigEditor —— 行级 patch 写回（核心）

**保留注释/空行/顺序**是设计基石。现有 `TxtConfig.save()` 的 value 正则 `(?P<value>.*)` 贪婪匹配到行尾，行内注释 `key : value / 注释` 整个进入 value，改值会连注释一起覆盖；删除/重排时还会全量重写丢失注释。故自建 ConfigEditor。

### 4.1 文件模型

读文件原始行数组，每行标注类型：

- `comment` — `/` 或 `//` 开头
- `section` — `[xxx]` 节头
- `option` — `key : value` 键值行
- `blank` — 空行

**已验证的事实（2026-08-07）：** 实体文件（MainMenu.txt 与 tasks/*.txt）**不存在行内注释**（`/` 均出现在行首），但存在以 `/` 开头的 value（如 `jjc.txt` 中 `action: /|%{simulate_times}`）。故 option 行解析为二元组 `(key, value)`，**value = `key : ` 后到行尾去尾空白**，不切分行内注释。注释保留仅针对行首 comment 行。

### 4.2 三种写回操作

| 操作 | 行为 |
|------|------|
| 改值 | 整行替换为 `key : 新值` |
| 新增实体 | 文件末尾追加 `\n[new-key]` + 字段行 |
| 删除实体 | 删除 option 行 + section 头行；**comment / blank 行保留**（保守，不猜注释归属） |

### 4.3 原子写回

写临时文件 + `os.replace` 原子替换，中途失败不留半文件。

## 5. 变更集 API

前端草稿攒成**变更集**（list of ops），一次保存 = 一次原子提交。

**变更操作类型：**

| op | 结构 | 说明 |
|----|------|------|
| `update` | `{key, fields}` | 修改实体字段 |
| `create` | `{key, entity}` | 新增实体 |
| `delete` | `{key}` | 删除实体 |
| `rename` | `{old, new}` | 重命名，后端自动同步更新所有引用旧 key 的字段 |

**接口：**

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/files` | 现有：列出配置文件 |
| `GET` | `/api/graph?file=` | 现有：完整图数据 |
| `GET` | `/api/entity/{name}?file=` | 现有：单个实体完整字段 |
| `GET` | `/api/entities?file=` | 新增：实体池候选（key+label+type），供自动补全 |
| `POST` | `/api/file/{file}/validate` | 新增：草稿预校验（不写盘），边改边提示 |
| `POST` | `/api/file/{file}/apply` | 新增：`{ops, base_hash}` → 模拟应用 → 严格校验 → 原子写回 → 返回新图或错误列表 |

**apply 流程：**

1. 比对 `base_hash` 与磁盘当前内容哈希；不符（TUI/手动改过）→ 拒绝并提示重新加载。
2. 在当前文件实体池快照上**模拟应用**全部变更。
3. **严格校验**（见 §6）。
4. 通过 → ConfigEditor 原子写回 → 返回新图数据。
5. 有错 → 返回错误列表，**不写任何文件**。

## 6. 校验规则

在模拟应用后的实体池快照上执行（跨文件校验，实体池含 MainMenu + 全部 tasks/*.txt）：

1. **重名**：同文件内 section key 唯一；跨文件重名同样拒绝（与现有 `_load_one` 的 `ValueError` 一致）。
2. **引用完整**（按字段语义区分，避免误报）：
   - `action` / `condition` / `condition_not` / `condition_then` / `condition_else` / `extend` / `match` → 实体必须存在于实体池（跨文件）
   - `settings`（task 类型）→ 必须指向 `settings` 实体
   - `target`（click/match/ocr 类型）→ 校验 `jczx/resources/` 下图片存在；**含 `${}` 占位符的 target 跳过存在性校验**
   - `func`（func 类型）→ 校验方法存在于 `JCZXGaming`
3. **字段类型**：float/int 字段转换错误（复用 `JczxSectionEntity.__setattr__`，捕获 `ValueError`）。
4. **占位符**：`${}` / `@{}` / `%{}` / `&{}` 括号闭合；`${section:option}` 引用的 section 存在；`@{}` 引用的实体存在。
5. **type 合法**：必须是 `SectionType` 枚举值。

**重命名**：`rename` 时后端自动把所有引用旧 key 的字段（跨文件）同步更新为新 key，再校验重名/冲突。

**错误返回：** `[{file, key, field, message}]`，前端定位到节点标红。

## 7. 前端交互

- 图保持只读（Cytoscape 现有能力）。
- **节点点击 → 编辑抽屉**：右侧详情面板扩展为可编辑表单，字段按 type 分组渲染：
  - 通用组：`name` `desc` `action` `times` `view` `sleep` `pre_sleep` `max_wait` `wait_target` `testFor_*` `log` `log_level` `context_*`
  - click：`target` `per` `pos` `match` `index` `break_point` `condition*`
  - match：`target` `per` `action`(变换)
  - func：`func` `target` `args`
  - condition：`condition` `condition_not` `condition_then` `condition_else`
  - task：`settings`
- **自动补全下拉**：引用字段（action / condition_then 等）候选来自实体池。
- **实体工具栏**：新增 / 复制（弹窗填新 key，默认自动唯一后缀）/ 删除（确认弹窗）。
- **草稿状态栏**：未保存改动列表 + 保存 / 放弃按钮，改动过的节点加脏标记。
- **校验失败**：错误横幅列出问题，点击跳转标红对应节点/字段。
- **保存成功**：重新请求图数据重排。

## 8. 错误处理与边界

| 场景 | 处理 |
|------|------|
| 文件不存在 / 解析失败 | 404 + 前端提示 |
| 保存冲突（外部修改） | `base_hash` 不匹配 → 拒绝 + 提示重新加载 |
| 删除被引用实体 | 校验拦截，列出所有引用它的实体 |
| 复制 key 冲突 | 自动追加唯一后缀 |
| 写入失败 | 前端保留草稿可重试 |

## 9. 依赖与运行（uv）

- taskView 依赖 `fastapi` / `uvicorn` 已在根 `pyproject.toml` 的 dependencies 中，由 uv 统一管理。
- 运行：`uv run python -m taskView`（浏览器自动打开 `http://localhost:8000`）。
- 不使用独立 `sde` 虚拟环境（原 taskview-design.md 中的 SDE 环境约定废弃）。

## 10. 验证方式（无测试套件，手动验证）

1. `uv run python -m taskView` 启动。
2. 对真实配置执行：改值 / 新增 / 复制 / 删除 / 重命名 / 保存。
3. `git diff` 检查写回文件：注释保留、顺序稳定、格式正确。
4. 保存后 `uv run python -m jczx.jczxCli` 加载同一配置，确认能正常解析执行。

## 11. 非目标

- 不支持新建任务向导（模板化生成整串实体）。
- 不编辑 `Config.txt`（全局设置）与 `Queues.txt`（队列）。
- 不做图上拖拽连线（表单联动已够）。
- 不提供撤销/重做历史（草稿 + 显式保存已提供反悔入口；保存前的改动可放弃）。
