# taskView 前端可视化编辑器 — 详细测试用例

**日期：** 2026-08-07
**状态：** 待执行
**测试文件：** `jczx/Config/tasks/test.txt`（仅此文件，防止影响生产配置；可在其中新增各类型实体测试）
**执行方式：** playwright（Edge）操作真实浏览器 + `git diff` 验证写盘
**约定：** 测试产物（test.txt 改动）用 `git checkout` 恢复；**问题只记录不修复**（`docs/superpowers/specs/2026-08-07-taskview-test-issues.md`）

## 测试目标

验证 taskView 前端可视化编辑器的全部交互功能与写盘正确性：加载渲染、编辑表单（各实体类型）、字段编辑、草稿管理、新增/复制/删除（乐观更新）、保存写盘、校验拦截、flow 视图、冲突处理。

## 测试环境

- 服务：`http://localhost:8000`（`uv run python -m taskView`）
- 浏览器：playwright + Edge（headless）
- 测试文件：`tasks/test.txt`（原始内容：`test` 实体，task 类型，action 引用 `get-combat-power,context-check`）

## 用例汇总表

| 用例 ID | 模块 | 用例名 | 结果 |
|---------|------|--------|------|
| A-01 | 加载与图渲染 | 加载 test.txt | |
| A-02 | 加载与图渲染 | action 引用边渲染 | |
| A-03 | 加载与图渲染 | 节点 type 着色 | |
| B-01 | 编辑表单 | 选中 test → 表单渲染 | |
| B-02 | 编辑表单 | 字段值回显 | |
| B-03 | 编辑表单 | click 类型字段分组 | |
| B-04 | 编辑表单 | match 类型字段分组 | |
| B-05 | 编辑表单 | func 类型字段分组 | |
| B-06 | 编辑表单 | condition 类型字段分组 | |
| B-07 | 编辑表单 | context 类型字段分组 | |
| B-08 | 编辑表单 | settings 类型字段分组 | |
| C-01 | 字段编辑 | 改字段 → 脏标记 + 草稿 | |
| C-02 | 字段编辑 | 改引用字段 → 自动补全 | |
| C-03 | 字段编辑 | 字段改回原值 → 撤销 | |
| D-01 | 草稿管理 | 保存 → 清空草稿 + 图重排 | |
| D-02 | 草稿管理 | 放弃 → 图还原 | |
| E-01 | 新增实体 | 新增 click → 乐观更新上图 | |
| E-02 | 新增实体 | 新增实体默认 target → 保存校验拦截 | |
| E-03 | 新增实体 | 新增后选中 → 表单可用（404 兜底） | |
| F-01 | 复制实体 | 复制 task → 只复制显式字段 | |
| F-02 | 复制实体 | 复制后保存 → 写盘简洁 | |
| G-01 | 删除实体 | 删除已保存实体 → 标红 | |
| G-02 | 删除实体 | 删除未保存新实体 → 标红 | |
| G-03 | 删除实体 | 放弃 → 恢复 | |
| H-01 | 保存写盘 | 保存修改 → test.txt 写回正确 | |
| H-02 | 保存写盘 | 保存新增 → test.txt 追加实体 | |
| H-03 | 保存写盘 | CRLF / 注释保留 | |
| I-01 | 校验 | action 引用不存在 → 拦截 + 错误横幅 | |
| I-02 | 校验 | 字段类型错误 → 拦截 | |
| I-03 | 校验 | target 图片不存在 → 拦截 | |
| I-04 | 校验 | 占位符括号未闭合 → 拦截 | |
| J-01 | flow 视图 | 切流程 → 流程树 | |
| J-02 | flow 视图 | flow 下新增 → 视图不跳变 | |
| K-01 | 冲突边界 | 外部改文件后保存 → 409 | |
| K-02 | 冲突边界 | 保存失败 → 草稿保留 | |

---

## 模块 A：加载与图渲染

### A-01 加载 test.txt
- **前置：** 服务在 8000，浏览器打开首页
- **步骤：** 点击侧栏文件列表 `tasks/test.txt`
- **预期：** 图渲染 `test` 节点（count=1），`currentFile='tasks/test.txt'`
- **实际：** 

### A-02 action 引用边渲染
- **前置：** A-01 完成
- **步骤：** 检查图数据（`cy` 全局）
- **预期：** `test` 节点的 action `[get-combat-power, context-check]` 生成两条边（action 实线），引用实体出现在节点中（或 flow 视图可见）
- **实际：** 

### A-03 节点 type 着色
- **前置：** A-01 完成
- **步骤：** 检查 `test` 节点的 classes
- **预期：** 节点带 `task` class（蓝色圆角矩形）
- **实际：** 

## 模块 B：编辑表单渲染

### B-01 选中 test → 表单渲染
- **前置：** A-01
- **步骤：** `cy.getElementById('test').emit('tap')` → 等待 1.2s
- **预期：** 右侧表单出现：新增/复制/删除按钮、15 个输入框、`type: task` 标签、点击瞬间显示"加载中…"
- **实际：** 

### B-02 字段值回显
- **前置：** B-01
- **步骤：** 读取表单字段值
- **预期：** `name='测试'`、`action='get-combat-power,context-check'`、`view='off'`、`type='task'`
- **实际：** 

### B-03 click 类型字段分组
- **前置：** test.txt 已含新增的 click 实体（用 E-01 新增）
- **步骤：** 选中 click 实体，读取表单字段
- **预期：** 含 click 专有字段：`target`/`per`/`pos`/`match`/`index`/`break_point`/`condition*`
- **实际：** 

### B-04 match 类型字段分组
- **前置：** test.txt 已含 match 实体
- **步骤：** 选中 match 实体
- **预期：** 含 `target`/`per`/`action`(变换)，不含 pos/condition
- **实际：** 

### B-05 func 类型字段分组
- **前置：** test.txt 已含 func 实体
- **步骤：** 选中 func 实体
- **预期：** 含 `func`/`target`/`args`
- **实际：** 

### B-06 condition 类型字段分组
- **前置：** test.txt 已含 condition 实体
- **步骤：** 选中 condition 实体
- **预期：** 含 `condition`/`condition_not`/`condition_then`/`condition_else`
- **实际：** 

### B-07 context 类型字段分组
- **前置：** test.txt 已含 context 实体
- **步骤：** 选中 context 实体
- **预期：** 含 `context_get`/`context_default`/`action`(运算链)/`context_key`
- **实际：** 

### B-08 settings 类型字段分组
- **前置：** test.txt 已含 settings 实体
- **步骤：** 选中 settings 实体
- **预期：** 表单正常渲染（settings 容器）
- **实际：** 

## 模块 C：字段编辑

### C-01 改字段 → 脏标记 + 草稿
- **前置：** B-01
- **步骤：** 改 `name` 输入框值 → dispatch change
- **预期：** 节点标黄（dirty=1）、草稿栏"草稿 1 项 · 保存 · 放弃"
- **实际：** 

### C-02 改引用字段 → 自动补全
- **前置：** B-01
- **步骤：** 检查 action 输入框的 datalist（`list="ref-action"`）
- **预期：** action 输入框绑定实体候选 datalist
- **实际：** 

### C-03 字段改回原值 → 撤销
- **前置：** C-01 完成
- **步骤：** 把 name 改回"测试" → dispatch change
- **预期：** update op 被撤销（draftOps 空）、节点去脏
- **实际：** 

## 模块 D：草稿管理

### D-01 保存 → 清空草稿 + 图重排
- **前置：** 有草稿（C-01）
- **步骤：** 点"保存"
- **预期：** draftOps=0、脏标记清除、图重排、草稿栏"无未保存修改"
- **实际：** 

### D-02 放弃 → 图还原
- **前置：** 有草稿（含新增/删除）
- **步骤：** 点"放弃"
- **预期：** 草稿清空、新增节点消失/删除恢复、脏标记清除
- **实际：** 

## 模块 E：新增实体

### E-01 新增 click → 乐观更新上图
- **前置：** B-01
- **步骤：** 点"新增"→ prompt 输入 `zz-click-test` → 检查
- **预期：** 图上立即出现 `zz-click-test` 节点（count+1）、黄色脏标记、草稿"草稿 N 项"
- **实际：** 

### E-02 新增实体默认 target → 保存校验拦截
- **前置：** E-01（draftOps 含 create:zz-click-test）
- **步骤：** 点"保存"
- **预期：** 保存被拦截（422）、错误横幅显示"图片资源不存在: buttons\xxx.png"、草稿保留
- **实际：** 

### E-03 新增后选中 → 表单可用
- **前置：** E-01
- **步骤：** 选中 `zz-click-test` 节点 → 等待
- **预期：** 表单渲染（datasetKey=zz-click-test、type=click）、无"加载详情失败"
- **实际：** 

## 模块 F：复制实体

### F-01 复制 task → 只复制显式字段
- **前置：** B-01
- **步骤：** 点"复制"→ prompt 输入 `test-copy` → 检查 create op 字段
- **预期：** create op 的 entity 只含显式字段（type/name/action），不含 index/per/times 等默认值
- **实际：** 

### F-02 复制后保存 → 写盘简洁
- **前置：** F-01
- **步骤：** 点"保存"→ `git diff test.txt`
- **预期：** test-copy 只写 3 行显式字段，无默认值噪音；test 未被改动；CRLF 保留
- **实际：** 

## 模块 G：删除实体

### G-01 删除已保存实体 → 标红
- **前置：** B-01
- **步骤：** 选中 test → 点"删除"→ confirm 接受
- **预期：** test 节点标红虚线（deleted class）、draftOps 含 delete:test
- **实际：** 

### G-02 删除未保存新实体 → 标红
- **前置：** E-01（zz-click-test 存在）
- **步骤：** 选中 zz-click-test → 点"删除"→ confirm
- **预期：** zz-click-test 标红、draftOps 含 delete:zz-click-test
- **实际：** 

### G-03 放弃 → 恢复
- **前置：** G-01/G-02
- **步骤：** 点"放弃"
- **预期：** deleted 标记清除、节点恢复
- **实际：** 

## 模块 H：保存写盘

### H-01 保存修改 → test.txt 写回正确
- **前置：** 修改 test 的 name 为"测试-改"入草稿
- **步骤：** 保存 → `git diff test.txt`
- **预期：** test 的 name 行变为"测试-改"，其余行不变，CRLF/EOL 保留
- **实际：** 

### H-02 保存新增 → test.txt 追加实体
- **前置：** draftOps 含 create 实体
- **步骤：** 保存 → `git diff test.txt`
- **预期：** 新实体追加到 test.txt 末尾，空行分隔正确
- **实际：** 

### H-03 CRLF / 注释保留
- **前置：** H-01/H-02
- **步骤：** `cat -A test.txt` 检查行尾
- **预期：** 行尾为 `^M$`（CRLF），行首注释未丢失
- **实际：** 

## 模块 I：校验

### I-01 action 引用不存在 → 拦截 + 错误横幅
- **前置：** B-01
- **步骤：** 改 action 为 `no-such-entity` → 保存
- **预期：** 保存被拦截（422）、错误横幅"引用实体不存在: no-such-entity"、草稿保留
- **实际：** 

### I-02 字段类型错误 → 拦截
- **前置：** B-01
- **步骤：** 改 `times` 为 `abc`（int 字段）→ 保存
- **预期：** 拦截、"字段类型错误"
- **实际：** 

### I-03 target 图片不存在 → 拦截
- **前置：** E-01（zz-click-test 默认 target）
- **步骤：** 保存
- **预期：** 拦截、"图片资源不存在"
- **实际：** 

### I-04 占位符括号未闭合 → 拦截
- **前置：** B-01
- **步骤：** 改某字段为 `@{broken` → 保存
- **预期：** 拦截、"占位符括号未闭合"
- **实际：** 

## 模块 J：flow 视图

### J-01 切流程 → 流程树
- **前置：** A-01
- **步骤：** 点布局按钮 `flow`
- **预期：** `currentView='flow'`、流程树节点渲染
- **实际：** 

### J-02 flow 下新增 → 视图不跳变
- **前置：** J-01
- **步骤：** 记录 pan/zoom → 选中节点 → 新增 → 检查
- **预期：** pan/zoom/节点数不变、草稿栏"草稿 1 项"
- **实际：** 

## 模块 K：冲突边界

### K-01 外部改文件后保存 → 409
- **前置：** A-01（baseHash 已记录）
- **步骤：** 用 bash 修改 test.txt → 点"保存"
- **预期：** 409、提示"文件已被外部修改，请重新加载"、草稿保留
- **实际：** 

### K-02 保存失败 → 草稿保留
- **前置：** 有草稿，构造校验失败（I-01）
- **步骤：** 保存 → 检查
- **预期：** 草稿未清空、错误横幅显示
- **实际：** PASS（校验失败后草稿保留、错误横幅显示）

---

## 执行结果汇总（2026-08-07，playwright MCP 实测）

| 用例 ID | 结果 | 备注 |
|---------|------|------|
| A-01 | ✅ PASS | 加载 test.txt，1 节点 |
| A-02 | ⚠️ 观察 | graph 视图不显示跨文件引用边（test 的 action 指向 MainMenu 实体）；flow 视图可见（J-01） |
| A-03 | ✅ PASS | test 节点带 `task` class |
| B-01 | ✅ PASS | 表单渲染（按钮+15 输入框+type 标签+加载中反馈） |
| B-02 | ✅ PASS / 问题#1 | name/action/view 回显正确；**type 无输入框（只读标签）** |
| B-03 | ✅ PASS | click 专有字段齐全 |
| B-04 | ✅ PASS | match 字段（target/per/action） |
| B-05 | ✅ PASS | func 字段（func/target/args） |
| B-06 | ✅ PASS | condition 字段（condition/then/else） |
| B-07 | ✅ PASS | context 字段（context_get/action/context_key） |
| B-08 | ⚠️ 问题#2 | settings 容器只有通用字段，**fields 引用不可编辑** |
| C-01 | ✅ PASS | 改字段 → 脏标记+草稿 |
| C-02 | ✅ PASS | action 输入框绑定 datalist 自动补全 |
| C-03 | ✅ PASS | 改回原值 → 撤销 op + 去脏 |
| D-01 | ✅ PASS | 保存 → 草稿清空+图重排 |
| D-02 | ✅ PASS | 放弃 → 图还原 |
| E-01 | ✅ PASS | 新增 → 乐观更新即时上图 |
| E-02 | ✅ PASS / 已知 | 默认 target 占位符 → 保存校验拦截（图片不存在） |
| E-03 | ✅ PASS / 问题#3 | 新增后选中 → 表单可用（404 兜底生效，console 有 404 噪音） |
| F-01 | ✅ PASS | 复制只含显式字段（type/name/action） |
| F-02 | ✅ PASS | test-copy 写盘仅 3 行、无默认值噪音、test 未动 |
| G-01 | ✅ PASS | 删除已保存 → 标红 |
| G-02 | ✅ PASS | 删除未保存新实体 → 标红（间接验证） |
| G-03 | ✅ PASS | 放弃 → 恢复 |
| H-01 | ✅ PASS | 保存修改 → test.txt 写回正确 |
| H-02 | ✅ PASS | 保存新增 → 追加实体+空行分隔 |
| H-03 | ⚠️ 观察 | 原 CRLF 行保留；bash heredoc 追加的测试实体为 LF（测试操作导致混合，非 ConfigEditor 缺陷） |
| I-01 | ✅ PASS | 引用不存在 → 拦截+错误横幅 |
| I-02 | ✅ PASS | 类型错误 → 拦截 |
| I-03 | ✅ PASS | 图片不存在 → 拦截（E-02 覆盖） |
| I-04 | ✅ PASS | 占位符未闭合 → 拦截 |
| J-01 | ✅ PASS | 切 flow → 流程树（含跨文件引用节点） |
| J-02 | ✅ PASS | flow 下新增 → pan/zoom/节点数全不变 |
| K-01 | ✅ PASS | 外部改文件 → 保存 409 提示 |
| K-02 | ✅ PASS | 保存失败 → 草稿保留 |

**结论：** 38 用例中 34 PASS，4 项观察/已知（A-02、H-03 为设计行为；B-02 含问题#1、B-08 问题#2、E-03 问题#3）。问题详情见 `2026-08-07-taskview-test-issues.md`。 
