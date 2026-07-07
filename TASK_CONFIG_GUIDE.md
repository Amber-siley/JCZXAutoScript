# 任务配置指南

## 配置文件概述

| 文件 | 路径 | 用途 |
|------|------|------|
| 主配置 | `jczx/Config/Config.txt` | 日志、线程、ADB 路径等全局设置 |
| 任务配置 | `jczx/Config/MainMenu.txt` | 公共实体 + 子文件入口引用 |
| 子配置文件 | `jczx/Config/tasks/*.txt` | 各模块任务定义（通过 `type: file` 引入） |

任务较多时建议拆分子文件，MainMenu.txt 仅保留公共实体和 `type: file` 声明。

---

## 配置语法

```ini
/            ← 注释（/ 或 // 开头）
[section]    ← 节名，该实体的唯一标识 key
key : value  ← 键值对，冒号分隔
```

- 逗号分隔的字符串自动解析为列表
- **注意：** 逗号后不要加空格。`action: a,b,c` 正确，`action: a, b, c` 会导致 `" b"` `" c"` 带前导空格，实体查找失败

---

## Config.txt — 主配置

```ini
logging.level : 10              / 10=DEBUG 20=INFO
logging.format : %(asctime)s [%(levelname)s] : %(message)s
logging.file.size : 1024        / kB
logging.file.mode : w           / w=覆盖 a=追加
logging.file.format : %(asctime)s [%(levelname)s] [%(lineno)04d] : %(message)s
logging.file.level : 10
thread.max_workers : 10
adb.path : platform-tools/adb.exe
```

---

## 实体类型总览

| 类型 | 说明 | action 链 | 说明 |
|------|------|-----------|------|
| `task` | 通用过程入口，view=on 时为 TUI 任务，view=off 时为幕后过程 | ✓ | `action` = 子实体链 |
| `func` | 调用 `JCZXGaming` 方法 | ✓ | |
| `click` | 模板匹配 + 点击 | ✓ | 支持 pos / match / target 三种模式 |
| `dynamic` | 动态执行 | ✗ | `action` = 循环源；返回值作为新 key 二次执行 |
| `match` | 纯匹配，返回坐标 | ✗ | `action` = 坐标变换操作 |
| `ocr` | 匹配 + 裁剪 + OCR | ✓ | 返回识别文本 |
| `context` | 上下文变量运算 | ✗ | `action` = 运算链 |
| `condition` | 条件分支控制 | ✓ | 评估 `condition`/`condition_not` |
| `settings` | 设置容器 | — | 引用 `setting` 字段 |
| `setting` | 设置字段定义 | — | 描述表单控件 |
| `file` | 外部配置文件引用 | — | 加载子配置文件中的实体合并到同一 `entity_pool` |

---

## 多文件配置

通过 `type: file` 将任务拆分到独立子文件中，MainMenu.txt 仅保留公共实体和入口声明。

### 使用方式

```ini
/ MainMenu.txt - 入口声明
[jjc-file]
type: file
target: tasks\jjc.txt
name: 竞技场日常
```

| 字段 | 说明 |
|------|------|
| `type` | `file` |
| `target` | 子文件路径（相对于 `Config/`），支持 `${}` 占位符 |
| `name` | 注释用显示名（不影响逻辑） |

### 子文件格式

与 MainMenu.txt 完全相同，可包含任意类型实体。外部实体可通过 `extend` 跨文件继承 MainMenu 中的公共实体，`action` 链也可引用 MainMenu 中的实体。

```ini
/ tasks/jjc.txt
[jjc-simulate]
type: task
name: 竞技场日常
action: goto-jjc,condition-need-fight
settings: settings-jjc

[click-jjc]
type: click
target: buttons\competition.png
```

### 约束

- **冲突检测** — 任意两个文件出现同名 section 时报 `ValueError`，不静默覆盖
- **不能嵌套** — 子文件中 `type: file` 被忽略
- **Settings 持久化** — 外部 task 的设置保存到其来源文件，不污染 MainMenu.txt
- **公共实体** — `in_location`、`click-center`、`goto-home`、`auto-fight` 等跨任务复用的实体保留在 MainMenu 中

### 推荐目录结构

```
Config/
  MainMenu.txt          ← 公共实体 + file 入口
  Config.txt            ← 全局设置
  tasks/
    jjc.txt             ← 竞技场日常
    inllusion.txt       ← 虚影周本
    Favor.txt           ← 好感任务
```

---

## 字段参考

### 通用字段（所有类型生效）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str | — | **必填**。值为上表类型之一 |
| `name` | str | — | 显示名称 |
| `desc` | str | — | 长文本备注 |
| `action` | list[str] | `[]` | 执行后链式调用的实体 key 列表（dynamic/match/context 中另有用处） |
| `times` | int | `1` | 执行次数 |
| `view` | str | `off` | `on`=TUI 中显示为任务，日志用 info 打印；`off`=幕后过程，日志用 debug |
| `only_key` | str | — | 系统自动赋值：section 名 |
| `context_key` | str | — | 返回值存入上下文变量的 key |
| `context_type` | str | `str` | `${`context_key`}` 存储前的类型转换：`str` / `int` / `float` / `bool` |
| `context_default_type` | str | `str` | context 类型**输入**变量的类型：`str` / `int` / `float` / `bool` |
| `pre_sleep` | float | `0` | 执行前等待秒数 |
| `sleep` | float | `0` | 自身逻辑完成后、action 链前的等待秒数 |
| `extend` | str | — | 继承另一个实体的字段（见继承章节） |
| `testFor_before` | str | — | 执行前检测图片，不可见则跳过实体 |
| `testFor_after` | str | — | action 链后检测图片，不可见则重试 |
| `testFor_max_wait` | float | `0` | testFor_before 最大等待秒数。click 中为 0 时沿用 `max_wait` |
| `testFor_pre_sleep` | float | `0` | testFor_before 前的等待 |
| `testFor_sleep` | float | `0` | testFor_before 通过后的等待 |
| `testFor_per` | float | `0.8` | testFor_before 匹配阈值 |
| `wait_target` | str | — | 实体主逻辑完成后等待的图片路径，支持占位符。超时受 `max_wait` 约束 |
| `wait_target_per` | float | `0.8` | wait_target 匹配阈值 |
| `max_wait` | float | `0` | wait_target / click 最大等待秒数。`0` 表示不等待
| `log` | str | — | 自定义日志消息，支持四种占位符（见占位符章节） |
| `log_level` | str | `info` | log 的等级：`debug` / `info` / `warning` / `error` |
| `screen_cache_ttl` | float | `-1` | 截图缓存 TTL（毫秒）。`-1`=继承上级，`0`=禁用（息屏/动画场景），`N`=自定义。只在链顶层设置即可，子实体 `-1` 自动继承 |

### click 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | str | — | 匹配的图片路径（支持 `${}` `@{}` 占位符） |
| `pos` | list[int] | `[]` | 直接点击坐标 `[x, y]`，设置后跳过所有匹配 |
| `match` | str | — | 引用 `match` 实体，对其结果坐标点击 |
| `per` | float | `0.8` | 匹配阈值 |
| `max_wait` | int | — | 最大等待秒数 |
| `break_point` | str | `off` | 超时是否跳出：`on` / `off` |
| `index` | int | `0` | 多匹配时取第几个结果 |
| `condition` | str | — | 前置条件：实体 key 或 `&{...}` 表达式 |
| `condition_not` | str | — | 反向条件（优先级高于 `condition`） |
| `condition_then` | list[str] | `[]` | 条件满足时执行的实体 |
| `condition_else` | list[str] | `[]` | 条件不满足时执行的实体 |
| `wait_sec` | list[str] | `[]` | 匹配等待期间每轮执行的操作 |

### func 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `func` | str | — | 方法名 |
| `target` | list[str] | `[]` | 首参数（与 `args` 合并） |
| `args` | list[str] | `[]` | 额外参数 |

### match 类型专用

`match` 类型执行**纯模板匹配**，在屏幕上查找图片并返回坐标信息，**不执行点击**。返回的 `MatchTemplete` 对象可被 `click`、`ocr` 等类型通过 `match` 字段引用。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | str | — | 匹配的模板图片路径（相对于 `resources/`） |
| `per` | float | `0.8` | 匹配阈值（`cv2.TM_CCOEFF_NORMED`） |
| `action` | list[str] | `[]` | **变换操作**（非执行链），见下方 |

**执行流程**：

1. `testFor_before` 门控（若配置）→ 等待前置图片出现
2. `pre_sleep` 等待
3. `cv2.matchTemplate` 全屏匹配 → 去重（邻近 10px 内只保留一个）
4. 按 `action` 列表依次对匹配结果应用变换操作
5. `sleep` 等待
6. `wait_target` 等待（若配置）
7. 输出 `log` 消息（若配置）
8. `testFor_after` 复检（若配置）→ 不匹配则重试

**变换操作（`action`）**：

`action` 在此类型中**不是执行链**，而是对匹配区域进行位置/尺寸变换的操作序列。多个操作用逗号分隔，依次应用到匹配结果上：

| 操作 | 格式 | 效果 | 计算公式 |
|------|------|------|----------|
| 上移 | `up-N` | 匹配区域向上偏移 | `shift_y = -模板高度 × N` |
| 下移 | `down-N` | 匹配区域向下偏移 | `shift_y = 模板高度 × N` |
| 左移 | `left-N` | 匹配区域向左偏移 | `shift_x = -模板宽度 × N` |
| 右移 | `right-N` | 匹配区域向右偏移 | `shift_x = 模板宽度 × N` |
| 横向缩放 | `reW-N` | 匹配区域宽度缩放 | `新宽度 = 原宽度 × N` |
| 纵向缩放 | `reH-N` | 匹配区域高度缩放 | `新高度 = 原高度 × N` |

> `N` 为浮点数（如 `1.5`、`0.8`），表示偏移量为模板尺寸的倍数，缩放为倍数因子。变换在匹配结果的四个角点和中心点上同步生效。

**变换示例**：

```ini
[find-power-icon]
type: match
target: buttons\power_icon.png
action: down-1.5, reW-2.0, reH-1.2
```

匹配到 `power_icon` 后，匹配区域先向下偏移模板高度的 1.5 倍，再横向扩展为 2 倍宽度、纵向扩展为 1.2 倍高度。最终返回的坐标区域覆盖战力值所在的数字区域。

**如何被其他类型引用**：

```ini
; click 类型引用 match 结果：点击匹配区域中心
[click-match-result]
type: click
match: find-power-icon          ; 引用 match 实体

; ocr 类型引用 match 结果：对匹配区域进行 OCR
[ocr-power-value]
type: ocr
match: find-power-icon          ; 引用 match 实体（优先于 target）
context_key: combat_power
context_type: int
```

**完整字段支持**：

所有**通用字段**（`times`、`pre_sleep`、`sleep`、`max_wait`、`screen_cache_ttl`、`log`、`log_level`、`context_key`、`context_type` 等）和 `testFor_*` / `wait_target` 系列均对 `match` 类型生效。`action` 在此类型中专用于变换操作，不会执行链。

**返回值**：

- 匹配成功：`MatchTemplete` 对象（`matched=True`，包含 `matchTempleteCenterPoints` 中心点坐标列表）
- 匹配失败：`None`

**不支持的字段**（对 `match` 无效）：`pos`、`match`、`index`、`func`、`args`、`condition*`、`break_point`、`wait_sec`

### ocr 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | str | — | 匹配后裁剪并 OCR 的图片 |
| `match` | str | — | 引用 `match` 实体，对其结果区域 OCR |
| `per` | float | `0.8` | 匹配阈值 |

优先级：`match` > `target`。

### context 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `context_get` | str | — | 读取的上下文变量 key |
| `context_default` | str | `""` | 变量不存在时的默认值 |
| `context_default_type` | str | `str` | **输入**类型：`str` / `int` / `float` / `bool` |
| `context_type` | str | `str` | **输出**类型转换（存 context_key 前）：`str` / `int` / `float` / `bool` |
| `action` | list[str] | `[]` | **运算链**（非执行链），格式 `运算符\|值` |

**运算链运算符：**

| 类型 | 运算符 | 说明 | 示例 |
|------|--------|------|------|
| int/float | `+` `-` `x` `/` | 算术 | `+|1`、`x|2`、`/|3` |
| int/float | `=` | 赋值 | `=|100` |
| int/float | `==` `>` `<` `>=` `<=` | 比较（返回 bool） | `>|5` |
| str | `+` | 拼接 | `+|abc` |
| str | `=` `==` | 赋值 / 相等 | `=|新值` |
| str | `contains` | 是否包含（返回 bool） | `contains|关键词` |

类型规则：int + float → float，int x int → int，int / int → float。

### condition 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `condition` | str | — | 条件：实体 key 或 `&{...}` 表达式 |
| `condition_not` | str | — | 反向条件（优先级高于 `condition`） |
| `condition_then` | list[str] | `[]` | 条件满足时执行 |
| `condition_else` | list[str] | `[]` | 条件不满足时执行 |

condition / condition_not 支持 `&{...}` 表达式（见占位符章节）。

### task 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `settings` | str | — | 指向 `settings` 实体，定义任务设置表单 |

### dynamic 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | list[str] | `[]` | **循环源**（非执行链）。每个元素执行后，返回值转为 str 作为新 key 再次 `exec()` |

---

## 执行流程

所有实体由 `_exec_entity` 模板方法统一管控，流程如下：

```
_exec_entity(entity, on_exec)
  for times:
    [stop_check]
    [testFor_before 门控]    ← testFor_pre_sleep → wait → testFor_sleep
    pre_sleep
    on_exec(entity)          ← 类型特有逻辑
    sleep
    [wait_target 等待]         ← 等待指定图片出现，受 max_wait 约束
    log 输出                 ← entity.log 解析占位符后打印
    [action 链]              ← get_next() → 递归 exec
    [testFor_after 复检]     ← 不可见 → continue 重试
```

`wait_target` vs `testFor_after`：`wait_target` 仅等待不重试，超时后继续执行 action 链；`testFor_after` 不可见时重新执行整个实体（含 pre_sleep/on_exec）。

**截图缓存：** 同帧内多个实体共享截图，默认 TTL 500ms。click/swipe/drag 后自动失效。链顶层设置 `screen_cache_ttl`，子实体 `-1` 自动继承，无需每个都配置。

| 类型 | 特有逻辑 | testFor | action 链 |
|------|---------|---------|-----------|
| task | 遍历 `entity.action` 执行子实体 | — | ✗（已内联） |
| func | 调用 `JCZXGaming` 方法 | — | ✓ |
| click | pos / match / target 点击 | ✓ | ✓ |
| dynamic | 遍历 action → 二次 exec | — | ✗ |
| match | findImageDetail + 变换 | — | ✗ |
| ocr | match / target 定位 + OCR | ✓ | ✓ |
| context | 读取变量 + 运算链 | ✓ | ✗ |
| condition | 评估条件 → then/else | ✓ | ✓ |

顶层入口 `exec_task_raw()` 在前后清空上下文变量，确保任务间上下文隔离。

---

## 占位符

四种占位符由统一的 `PlaceholderResolver` 引擎处理，单一入口 `resolve(text, after_key)` 按固定顺序解析。

### 总览对比

| 占位符 | 含义 | 解析方式 | 可用字段 | 解析顺序 |
|--------|------|---------|---------|---------|
| `${section:option}` | 配置值 | 从 `MainMenu.txt` 读取 | **所有字段**（entity key、target、args、action、log、condition、times、sleep 等） | ① |
| `@{entity_key}` | 实体返回值 | 执行实体，用返回值替换 | **所有字段**（entity key、args、target、action、log、condition、times 等） | ② |
| `%{context_key}` | 上下文变量 | 从 `_context` 读取 | **所有字段**（entity key、args、target、action、log、condition、times 等） | ③ |
| `&{表达式}` | 条件表达式 | 执行表达式内实体 + 逻辑/比较运算 | `condition` / `condition_not`（通过 `evaluate_condition()`）、log | ④ |

三种字符串占位符（`${}` / `@{}` / `%{}`）作用域完全一致，覆盖 entity key、action 链、所有标量字段；`&{...}` 仅用于条件求值和 log 展示。

**架构说明：** 所有解析通过 `PlaceholderResolver` 统一入口完成，保证 `${}` → `@{}` → `%{}` → `&{...}` 顺序。`condition` 字段通过 `evaluate_condition(condition, after_key)` 求值（返回 `"True"` / `"False"`），同时支持 `&{...}` 表达式和裸实体 key（兼容旧写法）。条件日志通过 `format_condition()` 额外展示解析后的表达式文本。

### 1. `${...}` — 配置占位符

从配置文件读取值，支持三种格式。**作用于所有字段。**

| 形式 | 含义 | 示例 |
|------|------|------|
| `${section:option}` | 指定 section 下的 option | `${screenshot-values:name}` |
| `${section:option:default}` | 带默认值 | `${mine-values:level:5}` |
| `${option}` | 短格式 → `{当前实体.only_key}-values:{option}` | `${screenshot-name}` |

```ini
[screenshot]
type: func
func: save_screenshot
args: ${screenshot-task-values:dir},${screenshot-name}
```

### 2. `@{...}` — 执行占位符

运行一个实体，将其返回值替换到字符串中。**作用于所有字段**，包括 action 链中的 entity key。

```ini
[get-device]
type: func
func: get_app_activity
args: com.megagame.crosscore

[save-screenshot]
type: func
func: save_screenshot
args: @{get-device},${screenshot-name}
```

### 3. `%{...}` — 上下文占位符

读取 `context_set` / `context_key` 存入的变量（类型为 `str`/`int`/`float`/`bool`），同时支持表达式求值。**作用于所有字段**。

```ini
[use-power]
type: func
func: context_set
args: threshold_check,%{power_value}
```

**表达式模式**（含运算符时自动识别，如 `& | >= <= > < == !=`）：

```ini
condition: &{combat_power >= 50000 & score > %{min_threshold}}
```
```ini
log: 剩余次数=%{total_times > refresh_times}
```

解析规则：`%{key > 5}` → 读取 `key` 上下文变量 → 与 `5` 比较 → 返回 `True`/`False`。表达式中也可混用 `${...}` `@{...}` `%{...}` 子占位符。

**调试输出：** 使用 `context_print` 方法打印当前全部上下文变量：
```ini
[debug-ctx]
type: func
func: context_print
```
输出格式：`上下文变量 (3)：\n  power_value = 3693 (int)\n  win_flag = True (bool)\n  name = 物品A (str)`

### 4. `&{...}` — 条件表达式

用于 `condition` / `condition_not` 字段和 `log` 字段，组合多实体和变量的返回值进行逻辑/比较运算：

```ini
condition: &{entity_a & (entity_b | entity_c >= 2)}
```

| 元素 | 说明 |
|------|------|
| `entity_key` | 执行该实体，返回值作为操作数 |
| `${section:option}` | 从配置读取值 |
| `@{entity_key}` | 执行实体并读取返回值 |
| `%{context_key}` | 读取上下文变量（支持表达式，如 `%{a > 3}`） |
| `123` / `3.5` | 数值字面量 |
| `&` `|` | 逻辑与 / 或 |
| `>=` `<=` `>` `<` `==` `!=` | 比较 |
| `()` | 分组括号 |

优先级（低→高）：`|` → `&` → `>=` `<=` `>` `<` `==` `!=` → `()`

**裸实体 key 兼容：** 不带 `&{...}` 时行为不变，`condition: my-entity` 等价于直接执行实体并取其布尔值。

**log 中的 &{...}：** 嵌入式 `&{...}` 会被替换为最终布尔结果（`True` / `False`），不再保留中间表达式文本。

```ini
[complex-check]
type: click
target: buttons\buy.png
condition: &{can_buy & (get-buy-times > 3 | get-diamond >= ${shop:price})}
condition_then: do-purchase
```

```ini
/ 比较实体结果和上下文变量
condition: &{check-power & %{combat_power} >= 50000}
```

**条件日志格式：** 满足/不满足时打印 `条件 &{原始表达式} → &{${}和%{}已替换} → 结果`，便于调试。

### log 字段中的多占位符混用

`log` 字段唯一支持四种占位符同时使用：

```ini
[debug-task]
type: click
target: buttons\login.png
log: 战力=%{power}, 阈值=${arena:threshold}, 状态@{check}, 判断&{enable >= 1}
log_level: debug
```

---

## 实体继承（extend）

子实体继承父实体的全部字段，仅需覆盖差异部分：

```ini
[base-click]
type: click
per: 0.85
max_wait: 30

[custom-click]
type: click
extend: base-click
target: buttons\special.png      ← 仅覆盖 target，per/max_wait 继承
```

- 继承源必须在**同一配置文件**中
- 建议父实体定义在子实体**之前**
- 找不到目标时不报错，仅输出 debug 信息

---

## 完整示例

### 启动游戏

```ini
[launch-game]
type: task
name: 启动游戏
action: launch-game-plan

[launch-game-plan]
type: func
func: start_game
args: com.megagame.crosscore,com.megagame.crosscore/com.mjsdk.app.MJUnityActivity
action: user-login
sleep: 30

[user-login]
type: click
name: 点击登录
target: buttons\userLogin.png
condition: condition-start-game
condition_then: click-start-game
action: click-start-game
max_wait: 20

[condition-start-game]
type: func
func: in_location
target: buttons\login.png

[click-start-game]
type: click
name: 开始游戏
target: buttons\login.png
action: no-reminders
max_wait: 15

[no-reminders]
type: click
name: 不再提醒
target: buttons\noReminders.png
action: close-Notice
break_point: on
max_wait: 30

[close-Notice]
type: click
name: 关闭公告
target: buttons\closeNotice.png
```

### testFor_before / testFor_after

```ini
[check-and-claim-reward]
type: click
name: 领取奖励
target: buttons\claim.png
testFor_before: buttons\reward_panel.png
testFor_after: buttons\reward_available.png
testFor_max_wait: 5
max_wait: 10
break_point: on
action: claim-next-reward
```

1. 等 `reward_panel.png` 出现（最多 5s），不出现则跳过
2. 匹配点击 `claim.png`（最多 10s）
3. 执行 `claim-next-reward`
4. 复检 `reward_available.png`，不可见则回到步骤 1

### OCR + 上下文运算

```ini
[find-power-icon]
type: match
target: buttons\power_icon.png
action: down-1.5,reW-2.0,reH-1.2

[ocr-power-value]
type: ocr
name: 识别战力值
match: find-power-icon
context_key: combat_power
context_type: int

[judge-power]
type: context
name: 判断战力是否足够
context_get: combat_power
context_default: 0
context_default_type: int
action: >=|50000
context_key: is_strong
```

### condition 独立使用

```ini
[judge-power]
type: condition
name: 判断战力
condition: &{get-combat-power >= 50000}
condition_then: start-fight
condition_else: refresh-opponent
testFor_before: buttons\arena_panel.png
testFor_max_wait: 5
```

---

## 图片资源

- 路径相对于 `jczx/resources/`，如 `buttons\login.png`
- 格式：PNG，以 `cv2.imread(..., IMREAD_GRAYSCALE)` 读取
- 初始化时 `target`、`testFor_before`、`testFor_after` 自动加载到缓冲池

---

## 任务设置配置

三个层级：**task → settings 容器 → setting 字段**

```ini
[order-delivery]
type: task
settings: order-delivery-settings

[order-delivery-settings]
type: settings
fields: enable-orders, enable-craft

[enable-orders]
type: setting
setting_type: multi_select
label: 启用订单
options: 初级订单,中级订单,高级订单,特殊订单
```

### 支持的控件类型

| setting_type | TUI 控件 | 值格式 |
|-------------|---------|--------|
| `input` | 文本输入框 | 自由文本 |
| `integer` | 数字输入框（min/max） | 整数字符串 |
| `select` | 下拉选择框 | 单个选项值 |
| `multi_select` | 多选框 | 逗号分隔选中项 |
| `multi_select_switch` | 主开关 + 子开关 | 选中项，子开关另存 `{name}__sub` |

值存储到 `{task-key}-values` section，读取时优先取值、其次 `default`。

---

## TUI 操作

| 按键 | 功能 |
|------|------|
| `q` | 退出 |
| `ctrl+l` | 清空日志 |

- `task` 类型出现在右侧任务列表，`name` → `desc` → key 作为显示名
- 任务列表中选中后可按"设置"编辑配置
- 任务编辑器中可选择 task 实体手动执行
