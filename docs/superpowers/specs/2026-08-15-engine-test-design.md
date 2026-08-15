# 引擎级测试（方案 2）— Design

## 目标

用 FakeDevice 桩替身测试执行引擎（`JCZXGaming` 的 exec 系列 + `_exec_entity` 模板），**不连接 ADB、不联网**，确定性断言引擎编排行为：

- `_exec_entity` 模板流程：`times` / `testFor_before|after` / `pre_sleep` / `sleep` / `wait_target`(+`wait_target_sleep`) / action 链 / `log`
- `exec_match`：级联匹配、action 变换、**标注时机（on_match 收到变换后点）**
- `exec_click`：点击坐标 / `index` 选择 / `condition_then|else` / `max_wait`
- 上下文存取与 `exec_task_raw` 隔离、`TaskExecutionManager` 取消

## 关键设计

### 1. 构造引擎：`object.__new__` 绕过 ADB

`Adb.__init__ → ready_env` 在无 adb_path 时会**联网下载 platform-tools**（`Adb.py:39-52`）。故用 `object.__new__(JCZXGaming)` 构造，手动注入引擎依赖：`task_manage` / `_screen_cache` / `_exec_mgr` / `_resolver` / `log` / `_recorder` / `_context` / `ocr`。

### 2. 设备 I/O 收敛到单一咽喉：`findImageDetail`

引擎 exec 流程实际调用的设备方法（已核实）：

| 引擎调用 | 处理 |
|---|---|
| `task_manage.get_img(target)` | 替换为 `lambda t: t`，让 target 字符串直通 matcher |
| `findImageDetail(img, cutPoints, per, grayScreenshot)` | 替换为 `FakeMatcher`（唯一匹配咽喉） |
| `click/swipe/dragAndDrop` | 替换为记录列表 |
| `screenshot()/grayScreenshot()` | 真 `ScreenshotCache` + 可控 `screenshot_fn` |
| `ocr.readtext(crop)` | 注入 FakeOCR（仅 ocr 流程用到） |
| `_exec_mgr.token.check()/sleep()` | 注入 FakeToken（sleep 记录不阻塞） |

`findImageCenterLocations` 与 `clickResource` 内部都走 `findImageDetail`，故替换一个点即覆盖：`_wait_for_image`、级联、exec_click、exec_ocr。

### 3. 确定性匹配

`FakeMatcher.results` 按 target 字符串映射预设 `MatchTemplete`（`make_match(x0,y0,x1,y1)` 工厂构造位于指定坐标的结果）。未命中返回 `None`（模拟"未匹配到"）。`FakeMatcher.calls` 记录每次 `(img, cutPoints, per)`，用于断言级联的 cutPoints 就是 action 变换后的区域。

### 4. 时间无关

`FakeToken.sleep(s)` 只记录时长（`token.sleeps`），不真正 sleep。断言 `pre_sleep` / `wait_target_sleep` / `max_wait` 值，测试秒级跑完。取消场景用**真实** `TaskExecutionManager` + `CancellationToken`。

## 目录结构

```
tests/engine/
  __init__.py
  conftest.py            # make_gaming / FakeMatcher / make_match fixture
  fake_device.py         # harness 组件（非测试文件）
  test_exec_entity.py
  test_exec_match.py
  test_exec_click.py
  test_context_condition.py
  test_cancellation.py
```

复用根 `tests/conftest.py` 的 `real_config_dir` fixture（真实配置只读副本 → 引擎加载真实实体）。

## 测试矩阵

### test_exec_entity.py
- `times`: action 链执行 N 次
- `testFor_before` 门控：图片未匹配 → 跳过实体返回 None；匹配 → 继续
- `wait_target` + `wait_target_sleep`: 主逻辑后等待图片，成功匹配后记录 sleep 时长
- action 链: task 实体按序执行子实体
- `testFor_after`: 未匹配 → 重新执行整个实体（可配合 times 验证重试）

### test_exec_match.py
- 级联：`exec("matched-exploration-guidelines-new")` → `calls` 中出现 `cutPoints == 变换后区域`
- action 变换：`exec("match-exploration-to-new")` 返回点 == 变换后坐标
- 标注时机：RecordingRecorder 断言 `on_match` 收到的是**变换后**点（回归上一轮修复）

### test_exec_click.py
- 命中点击：`clicks` 记录中心坐标
- `index` 选择多匹配中的指定项
- `condition_then|else` 分支
- `max_wait` 内未命中 → 超时返回 None（FakeToken 快速）

### test_context_condition.py
- `exec_context` 存取；`exec_task_raw` 前后上下文清空（隔离）
- `exec_condition` 条件求值走 `exec`

### test_cancellation.py
- 真实 `TaskExecutionManager`：执行中 `stop()` → `TaskCancelledError`

## 排除范围

- **真实 cv2 匹配**（合成图 + 不替换 findImageDetail）：单列 `@pytest.mark.image` 子层，本轮不做，后续单独加
- OCR 真实识别、Textual TUI：不涉及

## 依赖

pytest（已配置）、cv2、numpy、标准库。无新增依赖。
