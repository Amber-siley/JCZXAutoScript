# match 实体级联匹配检测设计

## 概述

扩展 `match` 类型，使其支持 `match` + `target` 级联匹配（与 click 的级联机制一致），用于仅检测不点击的场景。同时将级联匹配逻辑从 `exec_click` 中提取为共享方法，消除重复代码。

## 背景

当前 `match` 类型仅支持单图全屏模板匹配。级联匹配（先用 match 定位大区域，再在每个区域内用 target 做二次匹配）只能在 `exec_click` 内部使用，无法单独用于检测场景。用户需要在 `condition`、`context` 等场景仅判断子目标是否存在。

## 新增能力

### match 实体新增 `match` 字段

当 `match` 类型同时设置 `match` 和 `target` 字段时，触发级联匹配：

```
1. 执行 match 实体 → MatchTemplete（多区域）
2. 对每个匹配区域：
   a. 在区域内用 target 图片做 findImageDetail
   b. 收集所有子匹配中心点
3. 合并所有子匹配点为 MatchTemplete 返回
4. 无任何子匹配 → 返回 None
```

### 配置示例

```ini
# 级联检测：先找大区域，再检测区域内是否有子图片
[check-power-in-region]
type: match
match: find-power-panel          # 引用另一个 match 实体
target: buttons\power_icon.png   # 子区域内的检测目标
context_key: has_power

# 用作条件判断（None → falsy，MatchTemplete → truthy）
[guard-power]
type: condition
condition: check-power-in-region
condition_then: do-something
```

## 代码变更

### `jczx/jczxCli.py`

**1. 新增 `JCZXGaming._cascade_match` 共享方法**

从 `exec_click` 提取级联匹配逻辑。参数：`mt`（已执行的 MatchTemplete）、`target`（图片路径）、`per`（阈值）。返回合并子匹配点的 `MatchTemplete` 或 `None`。由调用方负责执行 match 实体并检查结果，避免重复执行。

```python
def _cascade_match(self, mt: MatchTemplete, target: str, per: float):
    img = self.task_manage.get_img(target)
        return None
    img = self.task_manage.get_img(target)
    if img is None:
        self.log.debug(f"级联匹配 target 图片未找到: {target}")
        return None
    all_pts = []
    for pts in mt.matchTempletePoints:
        (x0, y0), (_, _), (_, _), (x1, y1) = pts
        sub_mt = self.findImageDetail(img, cutPoints=((x0, y0), (x1, y1)), per=per)
        if sub_mt and sub_mt.matched:
            all_pts.extend(sub_mt.matchTempleteCenterPoints)
    if not all_pts:
        return None
    merged = MatchTemplete()
    merged.matchTempleteCenterPoints = all_pts
    merged.matched = True
    return merged
```

**2. 修改 `exec_match._on_exec` — 增加级联分支**

```python
def _on_exec(e: JczxSectionEntity):
    if e.match and e.target:
        return self._cascade_match(e.match, e.target, e.per)
    # ... 现有单图匹配逻辑不变
```

**3. 修改 `exec_click._on_exec` — 改用共享方法**

级联匹配块（约15行）替换为：
```python
cascade_result = self._cascade_match(e.match, target, e.per)
if cascade_result and cascade_result.matchTempleteCenterPoints:
    idx = e.index
    pts = cascade_result.matchTempleteCenterPoints
    pt = pts[idx] if idx < len(pts) else pts[0]
    self.click(*pt)
    result = mt
```

同时将现有 `e.target_index`（bug：实体定义中字段名为 `index`）修正为 `e.index`。

**4. 匹配优先级（不变）**

- 仅 `match`：原逻辑不变
- 仅 `target`：单图模板匹配不变
- 同时 `match` + `target`：级联匹配
- `action` 字段仍为变换操作，在级联结果上应用（与单图一致）

### `TASK_CONFIG_GUIDE.md`

在 match 类型专用章节补充 `match` 字段说明和级联匹配用法示例。

## 不变

- `exec_match` 单图匹配行为完全不变
- `exec_click` 级联点击的最终效果不变（仅实现方式改为调用 `_cascade_match`）
- 实体定义 `JczxSectionEntity` 无需修改（`match` 字段已存在）
