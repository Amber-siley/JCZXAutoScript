# 多文件任务配置支持 — 设计文档

**日期**: 2026-07-05
**目标**: 通过 `type: file` 实体将任务配置拆分到多个 `.txt` 文件，解决 MainMenu.txt 随任务数量增长而臃肿的问题。

## 1. 问题分析

当前所有任务实体（task、func、click、condition 等）全部定义在单一 `Config/MainMenu.txt` 中。随着任务数量增长，该文件迅速膨胀，导致：
- 单文件难以维护和定位
- 多人协作时合并冲突频繁
- 不同模块的实体混杂，缺乏物理隔离

## 2. 设计方案

### 2.1 `type: file` 实体

在 `MainMenu.txt` 中声明外部文件引用：

```ini
[arena-tasks]
type: file
target: tasks\arena.txt
name: 竞技场任务
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | str | `file` |
| `target` | str | 外部文件路径（相对于 `Config/` 目录），支持 `${}` 占位符 |
| `name` | str | 显示名（可选，不在 TUI 中展示） |

**外部文件格式：** 与 MainMenu.txt 完全相同的 TxtConfig 语法，可包含任意类型实体（task/func/click/match/ocr/context/condition/settings/setting）。

**限制：**
- 外部文件**不支持**嵌套 `type: file`（避免循环依赖）
- 外部文件中的 `extend` 可跨文件引用 MainMenu 的实体
- `type: file` 实体本身不进入 `entity_pool` / `task_pool`

### 2.2 加载与合并

修改 `TaskManage.load_task_entity_pool()`，流程：

```
1. 解析 MainMenu.txt → base_configs (dict[str, JczxSectionEntity])
2. 收集所有 type=file 实体，记录到 self._file_entities（不进入 entity_pool）
3. 对每个 file 实体:
    a. 记录 entity key → MainMenu 路径到 self._entity_source
    b. 解析 target 中的 ${} 占位符
    c. TxtConfig(target_path).trans_entity_dict() → external_configs
    d. 冲突检测: external_configs.keys() ∩ 已加载全体 keys → 报错退出
    e. 记录 external_configs 各 key → external_file_path 到 self._entity_source
    f. 合并 external_configs 到 entity_pool / task_pool
4. _resolve_extends() 统一处理继承（支持跨文件扩展）
```

**冲突检测：** 任意两个文件之间出现重复 section 名立即报错，不静默覆盖。

```
ValueError: 实体 key "click-fight" 冲突: tasks\arena.txt 和 MainMenu.txt 均定义了该 section
```

**加载顺序：** MainMenu 优先，外部文件按 `target` 声明顺序依次合并。

### 2.3 Settings 持久化

**新增数据结构：**

```python
# TaskManage
self._entity_source: dict[str, str]  # entity key → 来源文件绝对路径
self._file_entities: list[JczxSectionEntity]  # type=file 的实体（不参与执行）
```

**加载时填充：**
- MainMenu 中的 entity → `self._entity_source[key] = menu_config_path`
- 外部文件中的 entity → `self._entity_source[key] = external_file_path`

**`save_task_values()` 修改：**

原来硬编码写入 `self.menu_config_path`。修改为：根据 `self._entity_source[task_key]` 定位到正确文件，将 `{task-key}-values` 节写入该文件。

**`get_task_setting_entities()` / 设置相关方法：** 不变。设置节 `[{task_key}-values]` 由 `save_task_values` 写入正确文件，读时统一从 `menu_config` 读取（settings section 在文件级已合并）。

**TUI 刷新：** `_reload_configs()` 调用 `refresh_config()` 重新加载所有文件并重建 `_entity_source`。

### 2.4 `img_pool` 加载

`load_img_pool()` 遍历 `entity_pool` 中所有实体，外部实体的 `target` / `testFor_before` / `testFor_after` 自动加载。外部文件中的图片路径相对于 `jczx/resources/`（与 MainMenu 一致）。

## 3. 文件变更

| 文件 | 变更 |
|------|------|
| `jczx/jczx/configEntity.py` | `SectionType` 枚举中 `file` 已存在，无需改动 |
| `jczx/jczx/taskManage.py` | `load_task_entity_pool()` 重构；新增 `_entity_source`、`_file_entities`；`save_task_values()` 改用来源文件路径；新增 `_load_external_file()` 方法 |
| `jczx/jczx/jczxCli.py` | `exec()` 中增加 `SectionType.FILE` 的 case（默认跳过文件类型实体） |
| 无新文件 | — |

## 4. 验收标准

1. **声明式引入** — `type: file, target: xxx.txt` 将外部文件实体合并到同一 entity_pool
2. **冲突报错** — 任何两个文件出现同名 section 立即抛 `ValueError`
3. **跨文件引用** — 外部实体可 `extend: MainMenu 实体`，action 链可引用 MainMenu 实体
4. **Settings 正确写入** — 外部 task 的设置保存到其来源文件，不污染 MainMenu
5. **不嵌套** — 外部文件中的 `type: file` 被忽略（或 warn）
6. **向后兼容** — 不含 `type: file` 的 MainMenu.txt 加载行为完全不变
