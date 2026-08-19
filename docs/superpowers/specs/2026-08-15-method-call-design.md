# method / call 可复用参数化执行链 — Design

## 背景与问题

配置中大量"重复的数据实体执行链"难以复用。例："若某按钮旁出现某元素则点击按钮"。当前实现需要为每个场景写 3 个专用实体（match + near_location func + condition），`extend` 只能复制字段不能参数化；context 变量能传参但需逐个写 `context_set` 实体初始化，参数多时繁琐、语义不直观。

## 目标

引入配置级"可复用参数化方法"：

- `type: method` — 定义可复用、带参数的执行链（引用式 body）
- `type: call` — 调用 method，kwargs 自动绑定进全局 context，一次调用替代 N 个 context_set 实体
- `context` 类型新增 `values` 字段 — 批量初始化多个 context 变量（不触发方法，仅设变量）

**命名**：不用 `function`（与现有 `func` 语义撞车）。`func` = 调用 JCZXGaming 单个 Python 方法；`method` = 配置级可复用链。

## 设计

### 1. 类型与字段

新增 `SectionType.METHOD = "method"`、`SectionType.CALL = "call"`。

`JczxSectionEntity` 新增字段：

| 字段 | 类型 | 用于 | 说明 |
|---|---|---|---|
| `fn` | str | call | 目标 method 实体 key |
| `params` | list[str] | method | 声明参数名（逗号分隔），校验依据 |
| `param_defaults` | list[str] | method | 可选参数默认值（`k=v` 逗号分隔） |
| `values` | list[str] | context | 批量初始化（`k=v` 逗号分隔） |

`args` 字段（已有）复用于 call：存放调用处 kwargs（`k=v` 逗号分隔）。

### 2. 执行语义

**`exec_method`**（≈ `exec_task` 同构）：跑 `action` 链，复用 `_exec_entity` 模板（times / testFor / sleep 等通用字段生效）。

**`exec_call`**：
1. 解析 `args`：无 `=` 的 token 按 method `params` 声明顺序作**位置参数**；`k=v` 作 **kwargs**
2. 位置参数填入 `params` 前 N 位，kwargs 按名填充，剩余用 `param_defaults` 兜底（call 处显式值覆盖默认值）
3. 校验：位置参数超出 params 数量 / kwargs 名不在 params / 仍有未填充的必填参数 → `log.warning`（不中断）
4. 逐个 `context_set(key, value)` 绑定进**全局 context**
5. `self.exec(fn)` 执行 method body（仅副作用，无返回值）

**`context.values` 批量初始化**：`exec_context` 检测 `values` 存在时，解析 `k=v` 逐个 `context_set`。

### 3. 作用域与生命周期

按用户选择：**复用全局 context，不做调用后自动恢复**。参数绑定后留在 context，后续实体可读；同一函数体实体（读 `%{param}` 的共享实体）被多次调用时，后一次覆盖前一次。文档约定：函数参数名建议全局唯一或加前缀，避免冲突。

**嵌套调用**天然支持：method body 的 `action` 链里可再写 `call` 实体，形成 `exec_call → exec_method → exec_call ...`。

### 4. 与现有机制的关系

- `method`/`call` 是普通实体，进 `entity_pool`；**不进 `task_pool`**（`type == task` 才进），因此不会出现在任务列表/队列/设置面板。
- body 内复用现有原语（`near_location`/`in_location`/`match` 变换/condition 等），参数用 `%{param}` 从 context 读取。
- 配置文件 `args`/`values` 的值不能含逗号（与现有规则一致）。

## 示例

```txt
/ ===== method 定义 =====
[if-next-to-click]
type: method
name: 若基础图旁出现邻居图则点击
params: base, neighbor, neighbor_match
action: near-check, cond-click

[near-check]
type: func
func: near_location
args: %{neighbor}, %{neighbor_match}
context_key: near_ok

[cond-click]
type: condition
condition: %{near_ok}
condition_then: click-target

[click-target]
type: click
target: %{base}

/ ===== call 调用（位置参数，按 params 顺序）=====
[call-exploration]
type: call
fn: if-next-to-click
args: buttons\ExplorationGuidelines.png, locations\hasNew.png, match-exploration-to-new

/ ===== call 调用（kwargs 或混用亦可）=====
[call-exploration-2]
type: call
fn: if-next-to-click
args: buttons\a.png, neighbor=locations\b.png

[task-receive-x]
type: task
action: goto-home, call-exploration, goto-home
```

## 图片缓冲池与动态参数

`load_img_pool()` 启动时只按实体静态字段（`target`/`testFor_*`/`wait_target`）预载图片。`call` 的 `args` 是运行时参数，图片路径不在静态字段中 → 池缺失 → `get_img` 返回 None → 匹配失败。

**解决方案：运行时懒加载兜底。** `get_img` 池未命中时，若路径指向存在文件则按需加载并缓存（`_load_img_to_pool` 对不存在文件返回 False，非图片参数自动跳过，零副作用）：

```python
def get_img(self, img_path: str) -> MatLike:
    name = self._resolve_placeholder(img_path)
    if name in self.img_pool:
        return self.img_pool[name]
    if self._load_img_to_pool(name):   # 懒加载：按需读入并缓存
        return self.img_pool[name]
    return None
```

## 排除范围

- taskView 可视化编辑器对 method/call 类型与字段的支持：**后续独立任务**
- 真实 cv2 合成图匹配、TUI 测试：不涉及

## 依赖

无新增依赖。纯引擎改动 + 回归测试。
