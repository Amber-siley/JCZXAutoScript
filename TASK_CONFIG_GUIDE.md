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
| `settings` | 设置容器，引用一组 `setting` 字段 |
| `setting` | 单个设置字段定义，描述一个表单控件的类型、标签、选项等 |

### 所有字段一览

#### 通用字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | str | — | **必填**。值为 `task` / `func` / `click` / `dynamic` |
| `name` | str | — | 显示名称 |
| `desc` | str | — | 长文本备注（不用于显示名称） |
| `action` | list[str] | `[]` | 当前实体执行完毕后要执行的下一个实体 key 列表 |
| `times` | int | `1` | 执行次数，func / task / click / dynamic 均支持 |
| `view` | str | `off` | 控制 task 在 TUI 任务列表中是否显示。`on`=显示，`off`=隐藏 |
| `only_key` | str | — | 系统自动赋值：当前 section 的名称，用于占位符短格式解析 |
| `pre_sleep` | float | `0` | 执行前等待秒数 |
| `sleep` | float | `0` | 执行后等待秒数 |
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
| `target` | list[str] | `[]` | 要匹配的图片路径，相对于 `resources/` 目录 |
| `pos` | list[int] | `[]` | 直接点击坐标，设置后将跳过模板匹配 |
| `per` | float | `0.8` | 模板匹配阈值 (0.0–1.0)，越高越严格 |
| `max_wait` | int | — | 最大等待时间（秒），超时后跳过或进入 break_point 逻辑 |
| `break_point` | str | `off` | 超时后是否跳出执行链。`on`=跳出，`off`=继续 |
| `condition` | str | — | 前置条件实体 key，该实体执行成功后继续匹配 |
| `condition_not` | str | — | 反向条件实体 key，该实体执行成功则跳过匹配 |
| `condition_then` | list[str] | `[]` | 条件满足时转而执行的实体 key 列表（正向分支） |
| `condition_else` | list[str] | `[]` | 条件不满足时转而执行的实体 key 列表（反向分支） |
| `wait_sec` | list[str] | `[]` | 等待过程中执行的操作实体 key 列表 |
| `index` | int | `0` | 指定 target 匹配的结果 的索引 |

#### dynamic 类型专用

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | list[str] | `[]` | 要依次执行的实体 key 列表。每个实体执行完后，其返回值（转为 str）立即作为实体 key 再次调用 `exec()` |

**执行流程**：
```
dynamic.action[key1, key2, key3]
→ exec(key1) → result1 → exec(str(result1))
→ exec(key2) → result2 → exec(str(result2))
→ exec(key3) → result3 → exec(str(result3))
```

---

## 占位符语法 `${...}`

func / click 的 `target`、`args`、`action` 字段支持 `${...}` 占位符，运行时会从配置中读取对应的值进行替换。

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

`click` 的 `target` 字段也支持 `@{entity_key}`

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

任务执行期间可创建临时上下文变量，在任务链中传递数据，任务完成后自动释放。

### 内建方法

| 方法 | 参数 | 说明 |
|------|------|------|
| `context_set` | key, value | 写入上下文变量 |
| `context_get` | key, default | 读取上下文变量，未设置时返回 default |

### 占位符

| 形式 | 含义 |
|------|------|
| `%{key}` | 读取上下文变量 key 的值，未设置时为空字符串 |

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

`use-ctx-value` 运行时，`%{filename}` 被替换为 `screenshot_001`。

### 占位符解析顺序

`func` 的 `args` / `target` 按以下顺序解析：

1. `${...}` — 从配置文件读取值
2. `@{...}` — 执行实体获取返回值
3. `%{...}` — 从上下文变量读取值

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

## 执行流程

每个实体执行完毕后，按 `action` 列表依次执行下一个实体：

```
TASK → [action] → FUNC/CLICK → [action] → CLICK → [action] → ...
```

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

### 带条件的 click 执行逻辑

```
1. 若设置了 condition_not → 先执行它：
   - 失败（未检测到）→ 按顺序执行 condition_then 列表
   - 成功（检测到）   → 按顺序执行 condition_else 列表（若有），否则继续匹配
2. 若设置了 condition → 先执行它：
   - 成功 → 按顺序执行 condition_then 列表
   - 失败 → 按顺序执行 condition_else 列表（若有），否则继续匹配
3. 执行 wait_sec 中的操作
4. 开始模板匹配循环：
   - 匹配成功 → 点击 → 结束
   - 匹配失败 → 回到步骤 3，直到超过 max_wait
5. 超时后：
    - break_point=on → 跳出，不执行 action 链
    - break_point=off → 继续执行 action 链
```

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

click 类型的 `target` 路径相对于 `jczx/resources/` 目录。图片在加载时自动转为灰度图存入图片池。

支持的路径写法：
```
buttons\login.png
buttons\closeNotice.png
locations\mainScreen.png
```

图片格式要求：PNG，程序会用 `cv2.imread(..., IMREAD_GRAYSCALE)` 读取。

---

## TUI 中的任务显示

- **task 类型**的实体会出现在右侧"任务列表"面板中
- 显示名称为 `name` 字段，若未设置则回退到 `desc`，最后回退到 key
- 其他类型（func、click、dynamic）不出现在任务列表中，但可在"任务编辑器"下拉中选择 task 实体进行手动执行

### 快捷键

| 按键 | 功能 |
|------|------|
| `q` | 退出程序 |
| `ctrl+l` | 清空日志控制台 |
