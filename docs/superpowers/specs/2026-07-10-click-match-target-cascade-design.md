# click 实体 match + target 级联匹配设计

## 概述

当 click 实体同时设置 `match` 和 `target` 字段时，不再按原优先级互斥，而是级联匹配：先用 match 定位大区域，再在每个区域内用 target 做二次模板匹配，按 index 选择第 N 个子匹配点击。

## 当前行为（不变）

单独使用时优先级：`pos` > `match` > `target`。

## 新增组合语义

### 执行流程

```
1. 执行 match 实体 → MatchTemplete（多区域，如 A, B, C）
2. 对每个匹配区域：
   a. 从截图中裁剪该区域
   b. 在裁剪区域内用 target 图片做 findImageDetail（threshold=entity.per）
   c. 收集所有子匹配中心点
3. 全部子匹配按区域顺序、区域内按匹配顺序排列为一个数组
4. 按 entity.index 选择第 N 个子匹配中心点，执行 click
```

### 优先级示例

match 命中 (A, B, C)，target 二次匹配得：
- A 区域: A0, A1
- B 区域: B0
- C 区域: C0, C1, C2

全局索引：`[A0, A1, B0, C0, C1, C2]`

| index | 点击 |
|-------|------|
| 0 | A0 |
| 1 | A1 |
| 2 | B0 |
| 3 | C0 |
| ... | ... |

### 子匹配去重

target 二次匹配使用 `findImageDetail` → 已有 `_ceilPosition` 去重（10px 内合并且保留首次出现），无需额外处理。

## 代码变更

### `jczx/jczxCli.py` — `exec_click._on_exec`

将 `elif e.match:` 分支从单纯的 match 点击改为 match+target 组合逻辑：

```python
elif e.match:
    mt = self.exec(e.match)
    if mt is not None and mt.matched:
        if e.target:
            # match + target 级联匹配
            target = self._resolver.resolve(e.target, e.only_key)
            img = self.task_manage.get_img(target)
            if img is not None:
                all_pts = []
                for pts in mt.matchTempletePoints:
                    (x0, y0), (_, _), (_, _), (x1, y1) = pts
                    sub_mt = self.findImageDetail(img, cutPoints=((x0, y0), (x1, y1)), per=e.per)
                    if sub_mt and sub_mt.matched:
                        all_pts.extend(sub_mt.matchTempleteCenterPoints)
                if all_pts and e.target_index < len(all_pts):
                    self.click(*all_pts[e.target_index])
                    result = mt
            # 如果 target 匹配失败或 img 不存在 → 不做任何点击（不 fallback）
        else:
            # 仅 match（原逻辑）
            pt = mt.matchTempleteCenterPoints[e.target_index] if e.target_index < len(mt.matchTempleteCenterPoints) else mt.matchTempleteCenterPoints[0]
            self.click(*pt)
            result = mt
```

### `TASK_CONFIG_GUIDE.md`

在 click 类型专用表格中新增组合说明行。

## 不变

- `pos` 优先级最高
- 仅 `match`（无 `target`）：原逻辑不变
- 仅 `target`（无 `match`）：轮询匹配逻辑不变
- `index` 字段（即 `target_index`）语义：始终是第 N 个匹配结果的索引
