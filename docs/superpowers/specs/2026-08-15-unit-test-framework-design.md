# 单元测试框架搭建 — Design

## 目标

为交错战线自动化脚本项目引入 pytest 单元测试，分两层落地：

- **方案 1（纯逻辑单测）**：不依赖设备、不依赖真实配置，秒级跑完，覆盖配置解析/实体强转/占位符/截图缓存/匹配变换等纯逻辑。
- **方案 3（真实配置回归测试）**：以 `jczx/Config/` 的**只读副本**为输入，锁住配置加载与保存行为，防配置格式回归（含已修复的 Fix A/Fix B）。

方案 2（FakeDevice 引擎测试）与方案 4（图像/TUI）明确排除在本框架之外，后续单独规划。

## 目录结构（分类明确）

```
tests/
  conftest.py            # 共享 fixture（真实配置只读副本）
  pure/                  # 方案 1：纯逻辑单测，自建最小 fixture
    test_config_entity.py
    test_screenshot_cache.py
    test_match_transform.py
    test_placeholder_resolver.py
    test_config_utils.py
  regression/            # 方案 3：基于真实 jczx/Config 副本的回归测试
    test_config_loading.py
    test_save_task_values.py
```

分层原则：

| 目录 | 输入来源 | 依赖 | 目的 |
|---|---|---|---|
| `pure/` | 测试内自建的小段 TxtConfig 字符串 / stub 对象 / 合成 numpy 数组 | 仅被测模块 | 验证逻辑正确性，快、独立 |
| `regression/` | `shutil.copytree(jczx/Config, tmp)` 副本 | `TaskManage` + cv2 | 锁住真实配置的解析/保存行为 |

`pure/` 与 `regression/` 各自可独立运行：`uv run pytest tests/pure` 或 `uv run pytest tests/regression`。

## 关键约束

1. **不得触碰真实配置**：`regression/` 一律先 `copytree` 到 `tmp_path` 再操作，断言只针对副本。
2. **不得触发 ADB 联网**：纯逻辑测试只构造 `ScreenshotCache`/`MatchTemplete`/`PlaceholderResolver` 的最小对象，不构造 `JCZXGaming`（其 `Adb.__init__→ready_env` 会下载 platform-tools）。
3. **pytest 导入路径**：项目非标准包布局（模块在 `jczx/` 下），通过 `pyproject.toml` 的 `pythonpath = ["."]` 解决 `import jczx.*`。
4. **CLAUDE.md 同步**：现有"不要运行 pytest"表述已过时，随本框架更新。

## 各测试文件覆盖点

### pure/test_config_entity.py
- `BaseEntity.__setattr__` 类型强转：`str → int/float`、逗号字符串 → `list`
- 占位符字段（`${...}` 等）保持 str 不强制转换
- `SectionType` 枚举 `in` 判断与 `is_img_types`

### pure/test_screenshot_cache.py
- TTL 内复用（同帧不重复截图）
- TTL 过期重新截图
- `invalidate()` 后强制刷新
- **TTL=0 每次读取都重截**（回归 Fix B 的 `_stale` 语义）

### pure/test_match_transform.py
- `MatchTemplete.transform` 各算子几何数学：`left/right/up/down`、`*-M` 边距、`reW/reH` 缩放
- 链式变换累积
- 非法 action 返回原对象、不影响后续

### pure/test_placeholder_resolver.py
- 四类占位符解析顺序：`${}` → `@{}` → `%{}` → `&{}`
- `@{}` 调用 `gaming.exec`、`%{}` 读 `gaming._context`
- `resolve_list` 批量解析
- 条件表达式 `&{...}` 求值（stub gaming）

### pure/test_config_utils.py
- TxtConfig 解析/`get_config`/`set_config`/`save` 回写 round-trip
- `merge` 后新条目 `index == -1`
- **save 过期索引回退不再双写**（回归 Fix B）

### regression/test_config_loading.py
- 真实配置副本加载成功，关键实体存在（`goto-home`/`click-center` 等）
- `type: file` 合并：外部任务 `task-favor` 进入实体池
- `extend` 继承解析（`click-upcenter` 继承 `click-center`）
- 跨文件占位符解析（`${task-favor-values:setting-favor-times}`）

### regression/test_save_task_values.py
- **外部任务保存**（`task-favor`）：MainMenu.txt 不被污染（Fix A）、值写入 Favor.txt、重载解析新值、无 duplicate-key 冲突
- **原生任务保存**（`emu`）：值回写 MainMenu.txt、无重复、无外部 section 泄漏
- 文件行数/`[MainMenu]` 出现次数断言，锁死"重复插入"类回归

## 依赖与配置

- `uv add --dev pytest pytest-cov`
- `pyproject.toml` 新增：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- `tests/conftest.py` 提供 `real_config_dir` fixture（拷贝真实配置树到 `tmp_path`）。
