# taskView 前端测试问题修复设计

**日期：** 2026-08-07
**状态：** 已设计，待实现
**前置：** 基于测试问题清单 `docs/superpowers/specs/2026-08-07-taskview-test-issues.md`（7 个问题）
**验证方式：** playwright（Edge）回归测试 + `git diff` 写盘验证（测试文件限 `tasks/test.txt`）

## 1. 概述

修复 taskView 前端测试发现的 7 个问题（用户确认**全修**）。涉及前端 `taskView/static/index.html` 与后端 `taskView/graph_builder.py`。不修改 `jczx/` 下任何文件、不修改生产配置。

## 2. 修复范围

| # | 问题 | 修复 | 层级 |
|---|------|------|------|
| 1 | 实体 type 不可编辑 | type 改下拉选择 | 前端 |
| 2 | settings/setting 专有字段不可编辑 | 表单补 settings/setting 字段分组 | 前端+后端 |
| 3 | 未保存新节点 /api/entity 404 噪音 | tap handler 前置判断跳过 fetch | 前端 |
| 4 | graph 视图不显示跨文件引用边 | build_graph 用全局实体池建跨文件引用边 | 后端 |
| 5 | 新增默认 target 误拦 | addDraftEntity 默认 target 留空 | 前端 |
| 6 | flow 跨文件节点字段丢失 | flow 节点带 file 字段，tap handler 用来源文件 fetch | 前端+后端 |
| 7 | flow 脏标记/删除标红失效 | 节点查找兼容 `#N` 后缀 | 前端 |

## 3. 前端修复（`taskView/static/index.html`）

### 3.1 #1 type 可编辑
- `buildEntityForm` 顶部 `type: <b>${esc(type)}</b>` 改为 `<select>` 下拉，选项 = `SectionType` 枚举（`task`/`func`/`click`/`dynamic`/`match`/`ocr`/`context`/`condition`/`settings`/`setting`/`file`）。
- change 时加入 update op（`fields.type`）；表单字段分组不中途重渲染（保存重载后按新 type 更新），避免丢失未保存输入。

### 3.2 #2 settings/setting 字段分组
- `buildEntityForm` 的 `byType` 补充：
  - `settings`：`fields`（引用补全 datalist）
  - `setting`：`setting_type`、`label`、`desc`、`options`、`default`、`min`、`max`
- 字段值来自后端 detail（见 4.2）。

### 3.3 #3 未保存新节点跳过 fetch
- tap handler：`lookupName` 不在当前图数据 `fullNodes`（`fullNodes.some(n => n.data.id === lookupName)`）→ 判定为新建节点，**跳过 fetch**，直接用节点信息构造 detail（type 从 class 推断）。消除 404 噪音。

### 3.4 #5 新增默认 target 留空
- `addDraftEntity` 默认 entity 去掉 `target` 字段（不再填 `buttons\xxx.png`）。
- 后端校验已对空 target 跳过图片检查（`if target and ...`），无需改后端。

### 3.5 #7 flow 节点查找兼容 #N 后缀
- `trackDirty` / 乐观更新 delete 分支：`cy.getElementById(key)` 找不到时回退 `cy.$(`[id^="${key}#"]`)` 匹配 flow 节点（id 形如 `test#1`）。
- 使 flow 视图改字段标黄、删除标红生效。

### 3.6 #6 前端：tap handler 用节点来源文件
- tap handler：`const detailFile = node.data('file') || currentFile;`，fetch `/api/entity/${name}?file=${detailFile}`。
- flow 节点带 `data.file`（后端提供），graph 节点无则回退 currentFile。

## 4. 后端修复（`taskView/graph_builder.py`）

### 4.1 #4 graph 视图跨文件引用边
- 增强 `_load_all_files()` 返回 `(configs, entity_file)`（实体 key → 来源文件绝对路径）。
- `build_graph(filename)`：仍以当前文件实体为主（现有 `_load_all_entities`），但遍历 action/condition/condition_not/condition_then/condition_else/extend 引用时，用**全局实体池**判断存在性：
  - 引用实体存在于当前文件 → 现有逻辑。
  - 引用实体存在于**其他文件** → 添加跨文件节点（`data.file` = `entity_file[key]`、classes 追加 `external`）+ 引用边。
- **限制**：只显示当前文件实体的直接引用，不递归扩展跨文件实体的引用（避免图膨胀）。
- 效果：test.txt 加载后可见 `get-combat-power`/`context-check` 节点 + 引用边（A-02 修复）。

### 4.2 #6 flow 节点带 file 字段 + #2 detail 补字段
- `build_flow_tree` 节点 `data` 增加 `file` 字段（`entity_file[key]`），供前端 tap handler 用来源文件请求 detail。
- `get_entity_detail` 返回补充 settings/setting 专有字段：`fields`、`setting_type`、`label`、`options`、`default`、`min`、`max`。这些字段声明在 `JczxSettingEntity` 而非 `JczxSectionEntity` 上，故：
  - `get_entity_detail` 对 settings/setting 实体用 `JczxSettingEntity` 从来源文件重解析补齐（Task 1 已实现）。
  - `editor.py` 的 `_apply_field` 对 settings/setting 类型实体放行这 7 个专有字段（`_SETTING_ENTITY_FIELDS`），setattr 存为实例属性、写回时按文件行更新（Task 2 修订新增）。

## 5. 不改动的部分

- `taskView/editor.py`：`_apply_field` 修订为支持 settings/setting 专有字段（见 4.2）；其余校验（空 target 跳过图片检查、`explicit` 字段逻辑）保持。
- `jczx/` 全部文件：零侵入。
- 前端只读功能（拖拽/缩放/布局切换/导出/边过滤）：保持。

## 6. 验证方式（回归测试）

对已执行的测试用例做回归（playwright + test.txt，测试产物用 git 恢复）：

| 问题 | 回归用例 |
|------|---------|
| #1 | B-02：type 下拉可选、change 入 op |
| #2 | B-08：settings/setting 表单含专有字段 |
| #3 | E-03：新增后选中，console 无 404 |
| #4 | A-02：test.txt 图显示跨文件引用节点+边 |
| #5 | E-02：新增后保存不再被 target 误拦 |
| #6 | FV-02：flow 选中跨文件节点字段完整 |
| #7 | FV-03/FV-06：flow 改字段/删除有标红 |

## 7. 非目标

- 不做撤销/重做历史（草稿 + 显式保存已够）。
- 不重构 `build_graph`/`build_flow_tree` 的既有结构（只在现有基础上增强）。
- 不处理测试问题清单以外的优化。
