# 多文件任务配置支持 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过 `type: file` 实体将任务配置拆分到多个 `.txt` 文件，外部实体合并到同一 entity_pool，冲突时报错。

**Architecture:** `TaskManage` 加载时收集 `type: file` 实体，逐个解析外部 TxtConfig，冲突检测后合并到 `entity_pool`。`save_task_values` 根据 `_entity_source` 写入正确文件。

**Tech Stack:** Python 3.14, 现有 `TxtConfig` / `IniConfig.merge()`

**Spec:** `docs/superpowers/specs/2026-07-05-multi-file-config-design.md`

---

## File Changes

| 文件 | 操作 |
|------|------|
| `jczx/jczx/taskManage.py` | `__init__` 新增 `_entity_source` `_file_entities`；`load_task_entity_pool()` 重构；`save_task_values()` 改用来源文件路径 |
| `jczx/jczx/jczxCli.py` | `exec()` 增加 `SectionType.FILE` → `return None` |
| `jczx/jczx/configEntity.py` | 无需改动（`SectionType.FILE` 已存在） |

---

### Task 1: TaskManage — __init__ 新增数据结构 + load_task_entity_pool 重构

**Files:**
- Modify: `jczx/jczx/taskManage.py`

- [ ] **Step 1: `__init__` 新增两个属性**

在 `TaskManage.__init__` 中 `self.img_pool = ...` 之前增加：

```python
        self._entity_source: dict[str, str] = {}   # entity key → 来源文件路径
        self._external_configs: list = []           # 外部文件的 TxtConfig 对象（用于 save）
```

- [ ] **Step 2: 重构 `load_task_entity_pool()`**

替换为以下完整实现：

```python
    def load_task_entity_pool(self):
        self.log.debug("开始加载任务实体池")
        self._entity_source.clear()
        self._external_configs.clear()
        configs = self.menu_config.trans_entity_dict(JczxSectionEntity)

        # 提取 type=file 实体，不进入 entity_pool
        file_entities = []
        task_configs = {}
        for key, value in configs.items():
            if value.type == SectionType.FILE.value:
                file_entities.append((key, value))
            else:
                task_configs[key] = value

        # 处理 type=file：加载外部文件
        for key, file_entity in file_entities:
            target = file_entity.target
            if not target:
                self.log.warning(f"file 实体 {key} 缺少 target，跳过")
                continue
            target = self._resolve_placeholder(target, key)
            external_path = self.fm.join(self.config_dir, target, seq="\\")
            if not self.fm.isfile(external_path):
                self.log.error(f"外部配置文件不存在: {external_path}")
                continue
            external_config = Config(external_path, log=self.log).Config
            self._external_configs.append((external_path, external_config))
            external_configs = external_config.trans_entity_dict(JczxSectionEntity)
            # 冲突检测
            dup_keys = set(external_configs.keys()) & set(task_configs.keys())
            if dup_keys:
                dup_detail = ", ".join(f'"{k}"' for k in dup_keys)
                raise ValueError(
                    f"实体 key 冲突: {target} 和 MainMenu.txt 中重复定义了 {dup_detail}")
            for e_key, e_val in external_configs.items():
                self._entity_source[e_key] = external_path
            task_configs.update(external_configs)
            self.log.debug(f"已加载外部配置 {target}，{len(external_configs)} 个实体")

        # 初始化 MainMenu 实体的来源
        for key in task_configs:
            if key not in self._entity_source:
                self._entity_source[key] = self.menu_config_path

        # 继承处理 + 入池
        self._resolve_extends(task_configs)
        for key, value in task_configs.items():
            value.only_key = key
            self.entity_pool[key] = value
            self.log.debug(f"加载实体 {key} 到实体池，{value}")
            if value.type == SectionType.TASK.value:
                self.task_pool[key] = value
        self.log.debug(f"任务实体池加载完成，共 {len(self.entity_pool)} 个实体，其中 {len(self.task_pool)} 个任务")
```

- [ ] **Step 3: 提交**

```bash
git add jczx\jczx\taskManage.py
git commit -m "feat: multi-file config loading via type=file entities"
```

---

### Task 2: save_task_values 路由到来源文件

**Files:**
- Modify: `jczx/jczx/taskManage.py`

- [ ] **Step 1: 修改 `save_task_values()`**

替换为：

```python
    def save_task_values(self, task_key: str, values: dict[str, object]) -> None:
        section = f"{task_key}-values"
        source = self._entity_source.get(task_key, self.menu_config_path)
        # 找到对应的 TxtConfig
        target_config = self.menu_config
        for path, ext_config in self._external_configs:
            if path == source:
                target_config = ext_config
                break
        for field_name, val in values.items():
            target_config.set_config(section, field_name, str(val))
        target_config.save()
        self.log.debug(f"任务 {task_key} 设置已保存到 {source}: {values}")
        self._update_entities_after_save(task_key)
```

- [ ] **Step 2: 修改 `_update_entities_after_save()` 支持多文件读取**

将 `self.menu_config.get_config(task_key, "settings")` 改为按来源路由：

```python
    def _update_entities_after_save(self, task_key: str) -> None:
        entity = self.get_task(task_key)
        if not entity or not entity.settings:
            return
        source = self._entity_source.get(task_key, self.menu_config_path)
        target_config = self.menu_config
        for path, ext_config in self._external_configs:
            if path == source:
                target_config = ext_config
                break
        try:
            settings_section = target_config.get_config(task_key, "settings")
        except KeyError:
            return
        if not settings_section:
            return
        settings_entity = self._get_setting_entity(settings_section, SectionType.SETTINGS)
        if not settings_entity:
            return
        self.entity_pool[settings_section] = settings_entity
        self.log.debug(f"已刷新实体 {settings_section}")
```

- [ ] **Step 3: 提交**

```bash
git add jczx\jczx\taskManage.py
git commit -m "refactor: route save_task_values to entity source file"
```

---

### Task 3: exec() 增加 FILE 类型处理 + 验证

**Files:**
- Modify: `jczx/jczx/jczxCli.py`

- [ ] **Step 1: `exec()` 增加 FILE case**

在 `exec()` 方法的 match 块中找到 `case _:` 之前，插入：

```python
            case SectionType.FILE.value:
                return None
```

- [ ] **Step 2: 提交**

```bash
git add jczx\jczx\jczxCli.py
git commit -m "feat: skip file-type entities in exec dispatch"
```

---

### Task 4: 手动验证

- [ ] **Step 1: 创建外部配置文件**

创建 `Config/tasks/test_arena.txt`:

```ini
[click-arena-test]
type: click
name: 测试竞技场点击
target: buttons\cancel.png
max_wait: 5
```

在 `MainMenu.txt` 末尾添加：

```ini
[arena-file]
type: file
target: tasks\test_arena.txt
```

- [ ] **Step 2: 验证加载**

启动 TUI 并确认：
1. 正常启动无报错
2. `entity_pool` 中包含 `click-arena-test`
3. 日志显示 "已加载外部配置 tasks\test_arena.txt"

- [ ] **Step 3: 验证冲突检测**

在 `MainMenu.txt` 中创建一个与外部文件同名的 section，重启 TUI，确认报 `ValueError` 并提示冲突 key。

- [ ] **Step 4: 验证向后兼容**

删除 `[arena-file]` 实体，重启 TUI，确认行为与重构前完全一致。
