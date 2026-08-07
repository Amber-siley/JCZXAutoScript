# taskView 前端体验改进设计

**日期：** 2026-08-07
**状态：** 已设计，待实现
**前置：** 基于用户验收反馈的 6 个体验性问题
**验证方式：** playwright（Edge）+ `git diff` 写盘验证（测试文件限 `tasks/test.txt`）

## 1. 概述

改进 taskView 可视化编辑器的 6 个体验性问题：字段按 type 完整展示、实体引用标签式输入、草稿实体下拉、单/多实体字段输入、清空字段处理、草稿 action 实时连线（含跨文件完整链路）。

## 2. 改进范围

| # | 改进 | 说明 | 层级 |
|---|------|------|------|
| 1 | 按 type 展示完整字段 | 对照 TASK_CONFIG_GUIDE.md 补全 common 与各 type 专有字段 | 前端 |
| 2 | action 标签式输入 | 逗号列表改标签式（手动输入 + 下拉搜索匹配当前片段） | 前端 |
| 3 | 下拉支持草稿实体 | 实体引用候选含草稿 create 的实体 | 前端 |
| 4 | 单/多实体字段输入 | 单实体（match/condition/condition_not/extend）下拉；多实体（action/condition_then/condition_else）标签式，均含草稿 + 删除 | 前端 |
| 5 | 清空则删除字段 | 字段清空保存后从配置删除该 option 行 | 前端+后端 |
| 6 | 草稿 action 实时连线 | 编辑态实时显示引用边 + 跨文件完整链路 | 前端 |

## 3. #1 字段分组补全（`index.html` `buildEntityForm`）

### 3.1 common 补全
在现有 common 基础上补：
- `context_key`、`context_type`、`context_default_type`
- `screen_cache_ttl`、`testFor_max_wait`、`testFor_pre_sleep`、`testFor_sleep`、`testFor_per`、`wait_target_per`

### 3.2 byType 补全
- 补 `dynamic`：`action`（循环源）
- `click` 补 `wait_sec`
- `context` 补 `context_default_type`
- 其余与现有一致（match/ocr/func/condition/task/settings/setting 已覆盖专有字段）

### 3.3 字段分类（供引用输入组件识别）
字段分为：
- **多实体引用**（list，值=逗号串，标签式）：`action`、`condition_then`、`condition_else`、`wait_sec`
- **单实体引用**（str，值=单个 key，下拉/输入）：`match`、`condition`、`condition_not`、`extend`、`settings`
- **普通字段**（str/int/float）：`target`、`per`、`pos`、`sleep`、`pre_sleep` 等
- **list 非引用**：`args`、`options`、`fields`（逗号串，普通输入）

## 4. #2/#3/#4 实体引用输入组件（`index.html`）

新增可复用的**实体引用输入**渲染逻辑，替代现有 `action` 等纯文本 `<input>`。

### 4.1 多实体字段（标签式）
- 渲染为：标签区 `[key1 ×][key2 ×]` + 输入框
- 现有值 split 逗号 → 标签；每标签带 `×` 删除按钮
- 输入框：手动输入 + 下拉（datalist/自定义）搜索
  - **搜索匹配当前输入片段**：输入时取最后一个逗号后的文本作为搜索词
  - 回车或下拉选中 → 添加标签 → 清空输入框
- 提交：标签 join 逗号串（空则提交空串）

### 4.2 单实体字段（下拉/输入）
- 渲染为：输入框 + 下拉（候选含草稿），值 = 单个 key
- 支持手动输入，也支持下拉选中

### 4.3 草稿实体候选
- 候选 = `entityCandidates`（全局实体池）+ draftOps 中 `create` 的实体 key（草稿新增）
- 草稿候选标注（如 `(草稿)`），可选中

### 4.4 保存提交
- 多实体：标签 join 逗号串
- 单实体：单值
- 组件内部维护状态，change 时按现有机制入 draftOps

## 5. #5 清空则删除字段（`editor.py` + `index.html`）

- 字段清空（多实体无标签 / 单实体空）→ 提交空串
- 后端 `editor.py` 写回：update 字段值为**空字符串**时，删除该 option 行（而非写空值）：
  - `ConfigEditor` 新增 `delete_option(key, option)`（删除指定 option 行 + 重建索引）
  - `simulate_and_validate` 写回循环：update 字段值为空 → `ed.delete_option`；否则 `update_value`/`add_option`
- 校验：空值字段跳过类型/引用校验（如 `target` 已支持空跳过；`per` 清空不应报类型错）

## 6. #6 草稿 action 实时连线（`index.html`）

### 6.1 草稿图更新
- `pushDraft` 后调用 `updateDraftGraph()`：
  - 清空已有草稿态节点/边（draft class）
  - 遍历 draftOps 的 create/update 实体，解析其 `action`/`condition_then`/`condition_else` 逗号串
  - 对每个引用：确保 target 节点存在（缺失则添加，跨文件用 `/api/entity` 或 `/api/flow` 展开），建边（source→target，草稿态 class）
- 删除引用（draftOps 移除）→ 对应边/节点移除

### 6.2 跨文件完整链路
- action 引用跨文件实体（不在当前图）→ fetch `/api/flow?file=<来源文件>&task=<target>` 展开其完整执行链路
- 链路节点+边以草稿态加入图（虚线、半透明，`draft-node`/`draft-edge` class）

### 6.3 保存/放弃
- 保存：`loadGraph` 重载正式图（草稿态图清除）
- 放弃：清空草稿态图（保留已保存内容）

### 6.4 样式
- cytoscape style 加 `node.draft`/`edge.draft`：虚线、半透明

## 7. 不改动的部分

- `jczx/` 全部文件：零侵入。
- `graph_builder.py`/`server.py`：保持（#6 用现有 `/api/flow`、`/api/entity`；如需后端支持跨文件链路展开则最小扩展）。
- 既有只读功能（拖拽/缩放/布局切换/导出/边过滤）：保持。

## 8. 验证方式（回归测试）

对已执行用例做回归（playwright + test.txt，测试产物 git 恢复）：

| 改进 | 回归 |
|------|------|
| #1 | 各 type 表单含完整字段（common+专有） |
| #2/#3/#4 | action 标签式输入、草稿实体可选、单实体下拉 |
| #5 | 清空字段保存 → 配置中该 option 行被删除 |
| #6 | 草稿 action 实时建边、跨文件链路显示、删除移除、保存/放弃还原 |

## 9. 非目标

- 不实现撤销/重做历史（草稿 + 显式保存已够）。
- 不重构图构建后端（#6 用现有端点）。
- 不处理体验清单以外的优化。
