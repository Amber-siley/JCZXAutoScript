# 任务配置指南

## 配置文件概述

| 文件 | 路径 | 用途 |
|------|------|------|
| 主配置 | `jczx/Config/Config.txt` | 日志、线程、ADB 路径等全局设置 |
| 任务配置 | `jczx/Config/MainMenu.txt` | 所有任务、执行计划、点击操作的定义 |

---

## 配置语法

使用类 INI 格式：

```ini
/ 这是注释（以 / 开头）
[section-name]
option : value
```

- `//` 也是注释
- 以 `[ ]` 包裹的是节名（section name），作为该实体的唯一标识 key
- `option : value` 是键值对，冒号前后空格可选
- 逗号分隔的字符串值会自动解析为列表（见下方字段说明）

> **注意：** 逗号分隔时会保留空格。例如 `"初级订单, 中级订单, 高级订单"` 会解析为 `["初级订单", " 中级订单", " 高级订单"]`，元素可能带有前导空格。在 `action`、`args` 等引用实体 key 的列表字段中，**不要**在逗号后加空格，否则会导致实体查找失败。

---

## Config.txt — 主配置

```ini
/ 日志等级 10=DEBUG 20=INFO
logging.level : 10
/ 日志格式
logging.format : %(asctime)s [%(levelname)s] : %(message)s
/ 日志文件大小 kB
logging.file.size : 1024
/ 日志文件模式 w=覆盖 a=追加
logging.file.mode : w
/ 文件中日志格式
logging.file.format : %(asctime)s [%(levelname)s] [%(lineno)04d] : %(message)s
/ 文件中日志等级
logging.file.level : 10
/ 初始化线程数
thread.max_workers : 10
/ adb路径
adb.path : platform-tools/adb.exe
```

---

## MainMenu.txt — 任务配置

### 节类型（SectionType）

| 类型 | 说明 |
|------|------|
| `task` | 任务入口，聚合一组操作，在 TUI 任务列表中显示 |
| `func` | 函数调用，执行 `JCZXGaming` 上的方法 |
| `click` | 模板匹配点击，在屏幕上查找图片并点击 |
| `dynamic` | 动态执行，依次执行 action 实体并将其返回值作为实体 key 再次执行 |
| `match` | 纯模板匹配（不点击），返回匹配结果供其他实体使用 |
| `ocr` | 模板匹配 + OCR 文字识别，匹配图像区域后裁剪并 OCR，返回识别文本 |
| `context` | 上下文变量运算，读取变量后按 action 链计算，返回运算结果 |
| `condition` | 条件控制，评估 `condition`/`condition_not` 后执行 `then`/`else` 分支，通用字段独立 |
| `settings` | 设置容器，引用一组 `setting` 字段 |
| `setting` | 单个设置字段定义，描述一个表单控件的类型、标签、选项等 |

### 所有字段一览

#### 通用字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str | — | **必填**。值为 `task` / `func` / `click` / `dynamic` / `match` / `ocr` / `context` / `condition` |
| `name` | str | — | 显示名称 |
| `desc` | str | — | 长文本备注（不用于显示名称） |
| `action` | list[str] | `[]` | 当前实体执行完毕后要执行的下一个实体 key 列表（`dynamic`、`match` 除外，见各自说明） |
| `times` | int | `1` | 执行次数，所有类型均支持 |
| `view` | str | `off` | 控制 task 在 TUI 任务列表中是否显示。`on`=显示，`off`=隐藏 |
| `only_key` | str | — | 系统自动赋值：当前 section 的名称，用于占位符短格式解析 |
| `context_key` | str | — | 若设置，实体执行完毕后将返回值存入上下文变量（`%{...}`），可通过 `context_get` 读取 |
| `context_type` | str | `str` | 存入上下文前的类型转换（`str`/`int`/`float`）。context 类型中为**输出**转换 |
| `context_default_type` | str | `str` | context 类型：**输入**变量的类型（`str`/`int`/`float`） |
| `pre_sleep` | float | `0` | 执行前等待秒数 |
| `sleep` | float | `0` | 执行后等待秒数（在 action 链之前） |
| `extend` | str | — | 继承另一个实体的所有字段（详见下方继承章节） |

#### task 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `settings` | str | — | 指向一个 `settings` 类型的 section，定义该任务的设置表单 |

`task` 通过 `action` 指向其包含的子任务链。设置 `view: off` 可隐藏任务（仍可通过其他实体引用执行）。

#### func 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `func` | str | — | 要调用的方法名，必须是 `JCZXGaming` 上的方法 |
| `target` | list[str] | `[]` | 传给方法的参数（与 `args` 合并） |
| `args` | list[str] | `[]` | 传给方法的额外参数 |

#### click 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | str | — | 要匹配的图片路径，相对于 `resources/` 目录（支持 `${}`、`@{}` 占位符） |
| `pos` | list[int] | `[]` | 直接点击坐标 `[x, y]`，设置后跳过模板匹配和 match |
| `per` | float | `0.8` | 模板匹配阈值 (0.0–1.0)，越高越严格 |
| `max_wait` | int | — | 最大等待时间（秒），超时后跳过或进入 break_point 逻辑 |
| `break_point` | str | `off` | 超时后是否跳出执行链。`on`=跳出，`off`=继续 |
| `index` | int | `0` | 指定 target 匹配结果的索引（多个匹配时） |
| `condition` | str | — | 前置条件：支持单实体 key 或 `&{...}` 条件表达式。实体执行成功/表达式为真时进入 `condition_then` 分支 |
| `condition_not` | str | — | 反向条件：entity key 或 `&{...}` 表达式。**优先级高于 `condition`**。失败/为假时进入 `condition_then` 分支 |
| `condition_then` | list[str] | `[]` | 条件满足时转而执行的实体 key 列表（正向分支） |
| `condition_else` | list[str] | `[]` | 条件不满足时转而执行的实体 key 列表（反向分支） |
| `wait_sec` | list[str] | `[]` | 等待过程中每轮执行的操作实体 key 列表 |
| `match` | str | — | 引用一个 `match` 类型实体，用其匹配结果坐标直接点击（跳过 `target` 模板匹配循环） |
| `testFor_before` | str | — | 执行前检测图片路径，确保目标界面临场。图片不可见则跳过整个实体 |
| `testFor_after` | str | — | 执行后检测图片路径（action 链完成之后）。若不可见则回到 times 循环开头重试 |
| `testFor_max_wait` | float | `0` | testFor_before 的最大等待时间（秒）。为 0 时沿用 `max_wait` 的值 |
| `testFor_pre_sleep` | float | `0` | testFor_before 门控检查前的等待秒数 |
| `testFor_sleep` | float | `0` | testFor_before 门控检查通过后的等待秒数 |
| `testFor_per` | float | `0.8` | testFor_before 图片匹配阈值 |
| `log` | str | — | 实体执行时打印的自定义日志消息，支持 `${}` `@{}` `%{}` `&{}` 四种占位符 |
| `log_level` | str | `info` | log 消息的日志等级：`debug` / `info` / `warning` / `error` |

**log 占位符示例：**

```ini
[debug-click]
type: click
name: 测试点击
target: buttons\login.png
log: 战力值=%{combat_power}, 阈值=${arena-values:threshold}, 执行结果 @{check-status}
log_level: debug

[conditional-log]
type: click
name: 有条件日志
target: buttons\buy.png
log: 余额是否足够: &{get-balance >= ${shop-values:price}}
log_level: info
```

输出：`[debug-click] 战力值=3693, 阈值=50000, 执行结果 True`



#### dynamic 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | list[str] | `[]` | 要依次执行的实体 key 列表。每个实体执行完后，其返回值（转为 str）立即作为实体 key 再次调用 `exec()` |

**注意：** `dynamic` 的 `action` 字段**不是**执行链——它是动态循环的源数据。`dynamic` 不支持 `get_next()` action 链。

#### match 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | str | — | 要匹配的图片路径 |
| `per` | float | `0.8` | 匹配阈值 |
| `action` | list[str] | `[]` | 匹配结果的变换操作列表（见下方 match 章节） |

**注意：** `match` 的 `action` 字段**不是**执行链——它是变换操作列表。`match` 不支持 `get_next()` action 链。

#### ocr 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | str | — | 要匹配的图片路径，匹配到后裁剪该区域执行 OCR |
| `match` | str | — | 引用一个 `match` 类型实体，对其匹配结果区域执行 OCR |
| `per` | float | `0.8` | 模板匹配阈值 |

**仅通用字段生效：** `times`、`pre_sleep`、`sleep`、`action`、`context_key`、`testFor_before`、`testFor_after`、`testFor_max_wait`、`testFor_pre_sleep`、`testFor_sleep`。

**注意：** 不支持 condition / break_point / max_wait / wait_sec 等 click 专属字段。target 模式仅执行单次匹配，不循环等待。

**优先级：** `match` > `target`。若设置了 `match`，直接对其实体匹配结果区域执行 OCR。

**示例：**

```ini
/ 先匹配战力图标，再对其下方区域进行 OCR
[find-power-icon]
type: match
target: buttons\power_icon.png
action: down-1.5,reW-2.0,reH-1.2

[ocr-power-value]
type: ocr
name: 识别战力值
match: find-power-icon
context_key: power_value
```

执行后可通过 `%{power_value}` 读取战力数值。

#### context 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `context_get` | str | — | 要读取的上下文变量 key |
| `context_default` | str | `""` | 变量不存在时的默认值 |
| `context_default_type` | str | `str` | **输入**变量类型：`str`、`int`、`float` |
| `context_type` | str | `str` | **输出**类型转换（存入 `context_key` 前）：`str`/`int`/`float`。如计算结果 1.5，`context_type: int` → 存储 `1` |
| `action` | list[str] | `[]` | 运算链，格式 `运算符\|值`，从左到右依次执行 |
| `context_key` | str | — | 若设置，结果存入该 key（不修改原变量） |

**仅通用字段生效：** `times`、`pre_sleep`、`sleep`、`action`、`testFor_before`、`testFor_after`、`testFor_max_wait`、`testFor_pre_sleep`、`testFor_sleep`。

**运算链语法：**

| 类型 | 运算符 | 说明 | 示例 |
|------|--------|------|------|
| int / float | `+` | 加法 | `+|1`、`+|2.5` |
| int / float | `-` | 减法 | `-|3` |
| int / float | `x` | 乘法 | `x|2` |
| int / float | `/` | 除法（结果始终 float） | `/|2` |
| int / float | `=` | 赋值 | `=|100` |
| int / float | `==` | 等于（返回 bool） | `==|5` |
| int / float | `>` | 大于（返回 bool） | `>|5` |
| int / float | `<` | 小于（返回 bool） | `<|10` |
| int / float | `>=` | 大于等于（返回 bool） | `>=|0` |
| int / float | `<=` | 小于等于（返回 bool） | `<=|100` |
| str | `+` | 字符串拼接 | `+|abc` |
| str | `=` | 赋值 | `=|新值` |
| str | `==` | 字符串相等（返回 bool） | `==|预期文字` |
| str | `contains` | 是否包含（返回 bool） | `contains|关键词` |

**类型规则：** int + float → float（与 Python 一致），int x int → int，int / int → float。

**占位符支持：** `action` 运算链中的常量支持三种占位符，执行前按 `${}` → `@{}` → `%{}` 顺序解析：

```ini
[compare-with-config]
type: context
context_get: power
context_default: 0
context_type: int
action: +|${threshold:value},>|@{get-min-value},>=|%{min_threshold}
```

**示例：**

```ini
/ 上下文 {"a": "1"} → +|1 → 2 → -|2 → 0 → >|3 → false
[calc-value]
type: context
name: 计算并判断
context_get: a
context_default_type: int
action: +|1,-|2,>|3
context_key: result
```

执行后 `%{result}` 为 `"False"`。

```ini
/ OCR 获取战力值 → 判断是否大于 50000
[judge-power]
type: context
name: 判断战力是否足够
context_get: power_value
context_default: 0
context_default_type: int
action: >=|50000
context_key: is_strong
```

#### condition 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `condition` | str | — | 条件表达式：单实体 key 或 `&{...}` 表达式。真时执行 `condition_then` |
| `condition_not` | str | — | 反向条件：优先级高于 `condition`。假时执行 `condition_then` |
| `condition_then` | list[str] | `[]` | 条件满足时执行的实体 key 列表 |
| `condition_else` | list[str] | `[]` | 条件不满足时执行的实体 key 列表 |

**仅通用字段生效：** `times`、`pre_sleep`、`sleep`、`action`、`context_key`、`testFor_before`、`testFor_after`、`testFor_max_wait`、`testFor_pre_sleep`、`testFor_sleep`。

**说明：** 将 click 中的条件控制逻辑剥离为独立实体，支持通用字段定时/循环/前后检查。`action` 为执行链（后续实体 key）。

**示例：**

```ini
/ OCR 识别战力 → 判断是否 >= 50000 → 按结果分支
[judge-power]
type: condition
name: 判断战力
condition: &{get-combat-power >= 50000}
condition_then: start-fight
condition_else: refresh-opponent
testFor_before: buttons\arena_panel.png
testFor_max_wait: 5
```

与 `click` 中的内联条件等价的独立写法：
```ini
/ click 内联（旧）
[click-login]
type: click
target: buttons\login.png
condition: check-main-screen
condition_then: go-to-main

/ condition 独立（新）
[pre-check]
type: condition
condition: check-main-screen
condition_then: go-to-main

[click-login]
type: click
target: buttons\login.png
action: pre-check
```

---

## 执行流程

### 整体调度

`exec(entity)` 根据 `type` 分发到对应方法。所有类型执行完毕后，若设置了 `context_key`，将返回值存入上下文：

```
exec(entity)
  ├─ type=task      → exec_task(entity)
  ├─ type=func      → exec_func(entity)
  ├─ type=click     → exec_click(entity)
  ├─ type=dynamic   → exec_dynamic(entity)
  ├─ type=match     → exec_match(entity)
  ├─ type=ocr       → exec_ocr(entity)
  ├─ type=context   → exec_context(entity)
  └─ type=condition → exec_condition(entity)
  → if context_key: 按 context_type 转换后存入上下文（context/condition 类型除外，内部自行处理）
```

### task 类型执行流程

```
exec_task(entity)
  for _ in range(times):
      sleep(pre_sleep)
      for each key in entity.action:
          result = exec(get_entity(key))       ← 递归分发
      sleep(sleep)
  return result
```

顶层入口为 `exec_task_raw()`，会在执行前后清空上下文变量，确保每个顶层任务上下文隔离。

### func 类型执行流程

```
exec_func(entity)
  for _ in range(times):
      sleep(pre_sleep)
      method = getattr(self, entity.func)
      args = [entity.target] + entity.args       ← target 作为首参数
      args = resolve_placeholders(args)           ← ${...} 替换
      args = resolve_exec_placeholders(args)      ← @{...} 然后 %{...} 替换
      method(*args)                               ← 调用方法
      sleep(sleep)
      for each key in entity.action:              ← get_next() 执行链
          result = exec(get_entity(key))
  return result
```

### click 类型执行流程

```
exec_click(entity)
  test_before_img = load_image(entity.testFor_before) if present
  test_after_img = load_image(entity.testFor_after) if present
  for _ in range(times):
      ═══ 执行前门控 ═══
      if test_before_img:
          sleep(testFor_pre_sleep)
          wait = testFor_max_wait or max_wait
          if not _wait_for_image(test_before_img, wait):
              return None
          sleep(testFor_sleep)
```

**注意：** `dynamic` 不支持 action 链（`get_next()` 不会被调用）。`entity.action` 是动态循环的数据源，不是执行链。

### match 类型执行流程

```
exec_match(entity)
  img = load_image(entity.target)
  result = findImageDetail(img, per)              ← 返回 MatchTemplete 对象
  if 未匹配: return None
  for each transform in entity.action:            ← 变换操作（非执行链）
      result = result.transform(transform)
  return result                                    ← 返回 MatchTemplete
```

**支持的变换操作**（`action` 列表中的每个字符串）：

| 变换 | 示例 | 说明 |
|------|------|------|
| `up-N` | `up-0.5` | 向上移动 N × 模板高度 |
| `down-N` | `down-1.0` | 向下移动 N × 模板高度 |
| `left-N` | `left-2.0` | 向左移动 N × 模板宽度 |
| `right-N` | `right-1.5` | 向右移动 N × 模板宽度 |
| `reW-N` | `reW-0.5` | 缩放宽度为 N 倍 |
| `reH-N` | `reH-2.0` | 缩放高度为 N 倍 |

#### 典型用法：click 配合 match

```ini
[find-menu]
type: match
target: buttons\menu_icon.png
action: down-1.5

[click-sub-menu]
type: click
name: 点击子菜单
match: find-menu
```

`click-sub-menu` 执行时，先执行 `find-menu` 匹配 `menu_icon.png`，将结果中心点下移 1.5 个模板高度，然后在计算结果坐标处点击。此时不需要设置 `target`。

---

## 执行流程总结图

```
exec_task_raw(section)              ← 顶层入口（清空上下文）
  └─ exec_task(section)
       └─ for times:
            pre_sleep
            for action_entity in section.action:
                exec(action_entity)
                    ├─ task      → exec_task      (递归)
                    ├─ func      → exec_func      (方法调用 + action 链)
                    ├─ click     → exec_click     (检测 + 匹配点击 + action 链)
                    ├─ dynamic   → exec_dynamic   (循环 action key)
                    ├─ match     → exec_match     (纯匹配 + 变换，无链)
                    ├─ ocr       → exec_ocr       (匹配 + 裁剪 + OCR)
                    ├─ context   → exec_context   (变量运算，无链)
                    └─ condition → exec_condition (条件分支 + action 链)
            sleep
            (click/ocr/context/condition 专属: testFor_after 复检)
```

---

## 占位符语法 `${...}`

func / click / match 的 `target`、`args`、`action` 字段支持 `${...}` 占位符，运行时会从配置中读取对应的值进行替换。

### 语法

| 形式 | 含义 | 示例 |
|------|------|------|
| `${section:option}` | 引用指定 section 下的 option 值 | `${screenshot-task-values:screenshot-name}` |
| `${section:option:default}` | 带默认值 | `${mine-values:level:5}` |
| `${option}` | 短格式，自动补全为 `{entity.only_key}-values:{option}` | `${screenshot-name}` |

### 示例

```ini
[screenshot]
type: func
func: save_screenshot
args: ${screenshot-task-values:dir},${screenshot-name}
```

---

## 执行占位符 `@{...}`

`func` 的 `target` / `args` 字段支持 `@{entity_key}` 占位符，运行时执行对应实体并将其返回值作为参数替换。

`click` 的 `target` 字段也支持 `@{entity_key}`。

### 语法

| 形式 | 含义 |
|------|------|
| `@{entity_key}` | 执行 `entity_key` 对应实体，返回值替换 `@{...}` |

### 与 `${...}` 的区别

| | `${...}` | `@{...}` |
|------|----------|----------|
| 解析方式 | 从配置读取值 | 执行实体获取返回值 |
| 解析时机 | 先解析 | 后解析（在 `${}` 之后） |

### 示例

```ini
[get-device-name]
type: func
func: get_app_activity
args: com.megagame.crosscore

[use-device-name]
type: func
func: save_screenshot
args: @{get-device-name},${screenshot-name}
```

`use-device-name` 运行时：
1. `${screenshot-name}` → 从配置取值
2. `@{get-device-name}` → 执行 `get-device-name` 实体，返回值替换

---

## 上下文变量 `%{...}`

任务执行期间可创建临时上下文变量，在任务链中传递数据，顶层任务完成后自动释放。

### 内建方法

| 方法 | 参数 | 说明 |
|------|------|------|
| `context_set` | key, value | 写入上下文变量 |
| `context_get` | key, default | 读取上下文变量，未设置时返回 default |

### 占位符

| 形式 | 含义 |
|------|------|
| `%{key}` | 读取上下文变量 key 的值，未设置时为空字符串 |

### 通过 context_key 自动写入

任何实体执行完毕后，若设置了 `context_key` 字段，其返回值会自动存入上下文：

```ini
[detect-screen]
type: func
func: in_location
target: buttons\mainScreen.png
context_key: is_main_screen
```

执行后可通过 `%{is_main_screen}` 读取。

通过 `context_type` 可控制存入前的类型转换：

| context_type | 效果 | 示例（OCR 返回 `"123"`) |
|-------------|------|-------------------------|
| `str`（默认） | 直接转字符串 | `"123"` |
| `int` | 先转 float 再转 int（兼容 `"123.0"`） | `"123"` |
| `float` | 转浮点数 | `"123.0"` |

```ini
[ocr-power]
type: ocr
name: 识别战力
match: find-power-icon
context_key: power_value
context_type: int
```

### 示例

```ini
[save-name-to-ctx]
type: func
func: context_set
args: filename,screenshot_001

[use-ctx-value]
type: func
func: save_screenshot
args: %{filename}
```

### 占位符解析顺序

`func` 的 `args` / `target` 按以下顺序解析：

1. `${...}` — 从配置文件读取值
2. `@{...}` — 执行实体获取返回值
3. `%{...}` — 从上下文变量读取值

---

## 条件表达式 `&{...}`

`condition` 和 `condition_not` 字段支持条件表达式语法，可组合多个实体的返回值进行逻辑运算：

```ini
condition: &{entity_1 & (entity_2 | entity_3 >= 2)}
```

### 语法

| 元素 | 说明 |
|------|------|
| `entity_key` | 执行该实体，其返回值作为操作数 |
| `123` / `3.5` | 数值字面量 |
| `&` | 逻辑与 |
| `|` | 逻辑或 |
| `>=` `<=` `>` `<` `==` `!=` | 比较运算符 |
| `()` | 分组括号 |

### 优先级（从低到高）

```
| (OR) → & (AND) → >= <= > < == != → () (分组)
```

### 运算规则

- 所有实体执行后取其返回值参与运算
- `&` / `|` 使用 Python `bool()` 判断真假
- 比较运算符两端转为数值（`==`/`!=` 按字符串比较）

### 示例

```ini
/ 检查购买次数是否足够
[check-buy-enough]
type: func
func: context_set
args: can_buy,%{power_enough}

/ 复杂条件：战力足够 AND (购买次数 > 3 OR 钻石 > 1000)
[complex-check]
type: click
name: 执行购买
target: buttons\buy.png
condition: &{can_buy & (get-buy-times > 3 | get-diamond >= 1000)}
condition_then: do-purchase
max_wait: 5
```

### 与单实体兼容

不带 `&{...}` 时行为不变，`condition: my-entity` 等价于 `condition: &{my-entity}`。

---

## 实体继承（extend）

`extend` 字段允许一个实体继承另一个实体的全部字段，只需配置需要覆盖的字段。

### 语法

```ini
[base-click]
type: click
per: 0.85
max_wait: 30

[custom-click]
type: click
extend: base-click
target: buttons\special.png
```

`custom-click` 继承 `base-click` 的 `per: 0.85` 和 `max_wait: 30`，仅覆盖自己的 `target`。

### 规则

- 继承来源必须在**同一配置文件**中定义
- 子实体显式设置的字段会覆盖父实体的值
- 建议父实体定义在子实体**之前**（按配置文件出现顺序）
- 找不到继承目标时，会在日志中输出 debug 信息，不会报错

---

## 示例

### 示例：启动游戏

```ini
/ 任务入口
[launch-game]
type: task
name: 启动游戏
action: launch-game-plan

/ 执行计划：调起游戏 App
[launch-game-plan]
type: func
func: start_game
args: com.megagame.crosscore,com.megagame.crosscore/com.mjsdk.app.MJUnityActivity
action: user-login
sleep: 30

/ 点击登录按钮
[user-login]
type: click
name: 点击登录
target: buttons\userLogin.png
condition: condition-start-game
condition_then: click-start-game
action: click-start-game
max_wait: 20

/ 条件检测：是否处于登录界面
[condition-start-game]
type: func
func: in_location
target: buttons\login.png

/ 点击"开始游戏"
[click-start-game]
type: click
name: 开始游戏
target: buttons\login.png
action: no-reminders
max_wait: 15

/ 关闭提醒弹窗
[no-reminders]
type: click
name: 不再提醒
target: buttons\noReminders.png
action: close-Notice
break_point: on
max_wait: 30

/ 关闭公告
[close-Notice]
type: click
name: 关闭公告
target: buttons\closeNotice.png
```

### 示例：testFor_before / testFor_after 使用

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

执行逻辑：
1. 等待 `reward_panel.png` 出现（最多 5s），不出现则返回
2. 匹配并点击 `claim.png`（最多 10s）
3. 执行 `claim-next-reward` 链
4. 复检 `reward_available.png` 是否仍然可见，若消失则回到步骤 1

---

## 任务设置配置

每个 `task` 可以通过 `settings` 字段关联一组设置项，在 TUI 中点击任务的"设置"按钮时以动态表单呈现。用户修改并保存后，值持久化到 `MainMenu.txt`。

### 配置结构

三个层级：**task → settings 容器 → setting 字段**

```
[task-name]           type: task, settings: xxx-settings
[xxx-settings]        type: settings, fields: field-a, field-b
[field-a]             type: setting, setting_type: select, ...
[field-b]             type: setting, setting_type: integer, ...
```

### settings 容器字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str | — | **必填**，值为 `settings` |
| `fields` | list[str] | `[]` | 引用的 `setting` 节名列表，逗号分隔 |

### setting 字段定义

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str | — | **必填**，值为 `setting` |
| `setting_type` | str | — | **必填**。见下方支持的控件类型 |
| `label` | str | — | 表单中的显示标签 |
| `desc` | str | — | 帮助描述文本 |
| `options` | list[str] | `[]` | `select` / `multi_select` / `multi_select_switch` 的候选项 |
| `default` | str | `""` | 默认值 |
| `switch_label` | str | — | `multi_select_switch` 专属：子开关的标签 |
| `min` | int | — | `integer` 专属：最小值 |
| `max` | int | — | `integer` 专属：最大值 |

### 支持的控件类型（setting_type）

| setting_type | TUI 控件 | 值格式 |
|-------------|---------|--------|
| `input` | 文本输入框 | 自由文本 |
| `integer` | 数字输入框（带 min/max 校验） | 整数字符串 |
| `select` | 下拉选择框 | 单个选项值 |
| `multi_select` | 多选框（Switch × N） | 逗号分隔的选中项 |
| `multi_select_switch` | 双开关多选（主开关 + 子开关 × N） | 逗号分隔的选中项，子开关状态单独存储 |

### 完整示例

#### 示例 1：订单交付（multi_select + multi_select_switch）

```ini
[order-delivery]
type: task
name: 订单交付
desc: 自动交付订单
action: order-delivery-plan
settings: order-delivery-settings

[order-delivery-settings]
type: settings
fields: enable-orders, enable-craft

[enable-orders]
type: setting
setting_type: multi_select
label: 启用订单
options: 初级订单,中级订单,高级订单,特殊订单

[enable-craft]
type: setting
setting_type: multi_select_switch
label: 订单合成配置
options: 初级订单,中级订单,高级订单,特殊订单
switch_label: 合成
desc: 勾选订单并设置是否在材料不足时合成
```

TUI 中渲染效果：
```
启用订单
[✓] 初级订单  [✓] 中级订单  [ ] 高级订单  [✓] 特殊订单

订单合成配置
[✓] 初级订单  合成 [✓]
[ ] 中级订单  合成 [ ]
[✓] 高级订单  合成 [✓]
[ ] 特殊订单  合成 [ ]
```

#### 示例 2：角斗场挑战（integer）

```ini
[arena-challenge]
type: task
name: 角斗场挑战
desc: 自动挑战角斗场
settings: arena-challenge-settings

[arena-challenge-settings]
type: settings
fields: power-threshold

[power-threshold]
type: setting
setting_type: integer
label: 战力阈值
default: 50000
min: 0
```

#### 示例 3：执行方式（select）

```ini
[exec-mode-task]
type: task
name: 执行方式
desc: 演示选项配置
settings: exec-mode-settings

[exec-mode-settings]
type: settings
fields: exec-mode

[exec-mode]
type: setting
setting_type: select
label: 执行方式
options: 模式A-快速,模式B-均衡,模式C-完整
default: 模式B-均衡
```

### 值存储格式

用户保存后，值自动写入以 `{task-key}-values` 命名的 section：

```ini
[order-delivery-values]
enable-orders: 初级订单,高级订单
enable-craft: 初级订单,特殊订单
enable-craft__sub: 初级订单

[arena-challenge-values]
power-threshold: 35000

[exec-mode-task-values]
exec-mode: 模式C-完整
```

- `multi_select_switch` 的子开关状态存储在 `{field-name}__sub` 键中
- 读取时优先取 `-values` section 的值，若不存在则使用 `default`

---

## 图片资源

click / match 类型的 `target` 路径相对于 `jczx/resources/` 目录。图片在加载时自动转为灰度图存入图片池。

支持的路径写法：
```
buttons\login.png
buttons\closeNotice.png
locations\mainScreen.png
```

图片格式要求：PNG，程序会用 `cv2.imread(..., IMREAD_GRAYSCALE)` 读取。

所有 `target`、`testFor_before` 和 `testFor_after` 字段引用的图片都在初始化时加载到缓冲池，避免运行时重复读取。

---

## TUI 中的任务显示

- **task 类型**的实体会出现在右侧"任务列表"面板中
- 显示名称为 `name` 字段，若未设置则回退到 `desc`，最后回退到 key
- 其他类型（func、click、dynamic、match）不出现在任务列表中，但可在"任务编辑器"下拉中选择 task 实体进行手动执行

### 快捷键

| 按键 | 功能 |
|------|------|
| `q` | 退出程序 |
| `ctrl+l` | 清空日志控制台 |
