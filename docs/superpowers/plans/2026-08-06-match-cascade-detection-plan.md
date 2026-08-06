# match 实体级联匹配检测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `match` 类型新增 `match` + `target` 级联匹配能力，同时提取 `exec_click` 中的级联逻辑为 `JCZXGaming._cascade_match` 共享方法，消除重复代码。

**Architecture:** 新增 `_cascade_match(mt, target, per)` 方法接收已执行的 `MatchTemplete` + target 图片，返回合并子匹配点的 `MatchTemplete` 或 `None`。`exec_match` 的 `_on_exec` 增加级联分支，`exec_click` 改为调用共享方法。

**Tech Stack:** Python 3.11+, cv2, 项目内 ADB/Device/MatchTemplete

## Global Constraints

- 匹配失败统一返回 `None`（falsy），成功返回 `MatchTemplete`（truthy）
- `action` 变换操作在级联结果上同样生效
- 现有单图 match 行为完全不变
- 无测试框架，通过实际运行日志验证

---

### Task 1: 新增 `_cascade_match` 共享方法

**Files:**
- Modify: `jczx/jczxCli.py`

**Interfaces:**
- Consumes: `MatchTemplete` (已执行的结果对象), `self.task_manage.get_img(target)`, `self.findImageDetail(img, cutPoints=..., per=per)`
- Produces: `self._cascade_match(mt: MatchTemplete, target: str, per: float) -> MatchTemplete | None`

- [ ] **Step 1: 在 `JCZXGaming` 类中添加 `_cascade_match` 方法**

在 `exec_match` 方法之前（约第 416 行之前）插入：

```python
    def _cascade_match(self, mt: MatchTemplete, target: str, per: float):
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

- [ ] **Step 2: 验证文件语法无错误**

```powershell
python -c "import ast; ast.parse(open('jczx/jczxCli.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add jczx/jczxCli.py
git commit -m ":sparkles: 新增 JCZXGaming._cascade_match 级联匹配共享方法"
```

---

### Task 2: 扩展 `exec_match` 支持 `match` 字段级联匹配

**Files:**
- Modify: `jczx/jczxCli.py:417-439`

**Interfaces:**
- Consumes: `self._cascade_match(mt, target, per)`, `self._resolver.resolve()`
- Produces: `exec_match` 现在支持 `match` + `target` 级联

- [ ] **Step 1: 修改 `exec_match._on_exec`**

将 `_on_exec` 内部逻辑改为级联优先：

```python
        def _on_exec(e: JczxSectionEntity):
            if e.match and e.target:
                mt = self.exec(e.match)
                if mt is None or not mt.matched:
                    return None
                target = self._resolver.resolve(e.target, e.only_key)
                result = self._cascade_match(mt, target, e.per)
            elif e.target:
                img = self.task_manage.get_img(e.target)
                if img is None:
                    self.log.debug(f"match 图片未找到: {e.target}")
                    return None
                result = self.findImageDetail(img, per=e.per)
                if not result or not result.matched:
                    self.log.debug(f"match 未匹配到: {e.target}")
                    return None
            else:
                self.log.debug("match 类型缺少 target")
                return None
            if self._recorder:
                self._recorder.on_match(self.screenshot(), result)
            for action in e.action:
                result = self._transform_match(result, action)
            return result
```

- [ ] **Step 2: 验证语法**

```powershell
python -c "import ast; ast.parse(open('jczx/jczxCli.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add jczx/jczxCli.py
git commit -m ":sparkles: exec_match 支持 match+target 级联匹配检测"
```

---

### Task 3: 重构 `exec_click` 使用 `_cascade_match` 并修复 `target_index` bug

**Files:**
- Modify: `jczx/jczxCli.py:548-565`

**Interfaces:**
- Consumes: `self._cascade_match(mt, target, per)` 替代内联级联逻辑
- Bugfix: `e.target_index` → `e.index`

- [ ] **Step 1: 替换 `exec_click._on_exec` 中 `elif e.match:` 分支的级联匹配块**

将第 548-565 行替换为：

```python
            elif e.match:
                mt = self.exec(e.match)
                if mt is not None and mt.matched:
                    if e.target:
                        target = self._resolver.resolve(e.target, e.only_key)
                        cascade_result = self._cascade_match(mt, target, e.per)
                        if cascade_result and cascade_result.matchTempleteCenterPoints:
                            idx = e.index
                            pts = cascade_result.matchTempleteCenterPoints
                            pt = pts[idx] if idx < len(pts) else pts[0]
                            self.click(*pt)
                            result = mt
                    else:
                        if mt.matchTempleteCenterPoints:
                            idx = e.index
                            pt = mt.matchTempleteCenterPoints[idx] if idx < len(mt.matchTempleteCenterPoints) else mt.matchTempleteCenterPoints[0]
                            self.click(*pt)
                        result = mt
```

- [ ] **Step 2: 验证语法**

```powershell
python -c "import ast; ast.parse(open('jczx/jczxCli.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add jczx/jczxCli.py
git commit -m ":recycle: exec_click 改用 _cascade_match + 修复 target_index→index"
```

---

### Task 4: 更新 `TASK_CONFIG_GUIDE.md` 文档

**Files:**
- Modify: `TASK_CONFIG_GUIDE.md`

- [ ] **Step 1: 在 match 类型表格中新增 `match` 字段说明**

在 match 类型专用表格（约第 186 行 `| target | str | — |` 行之前）插入一行：

```markdown
| `match` | str | — | 引用 `match` 实体 key，与 `target` 同时设置时触发级联匹配（不点击，仅检测） |
```

- [ ] **Step 2: 在 match 类型章节末尾添加级联匹配配置示例**

在 "不支持的字段" 行之后（约第 276 行之后），"### ocr 类型专用" 之前，插入：

```markdown
**`match` + `target` 级联匹配**：同时设置时，先执行 `match` 实体定位大区域，再在每个区域内用 `target` 图片做二次模板匹配，合并所有子匹配点返回 `MatchTemplete`。无任何子匹配返回 `None`。

```ini
# 级联检测：先找大区域 power-panel，再检测区域内是否有 power-icon
[check-power-in-region]
type: match
match: find-power-panel
target: buttons\power_icon.png

# 用作条件判断（None → 条件不满足）
[guard-power]
type: condition
condition: check-power-in-region
condition_then: do-something
```
```

- [ ] **Step 3: Commit**

```bash
git add TASK_CONFIG_GUIDE.md
git commit -m ":memo: 文档补充 match 级联匹配用法"
```

---

### Task 5: 端到端验证

- [ ] **Step 1: 确认所有改动文件无语法错误**

```powershell
python -c "import ast; ast.parse(open('jczx/jczxCli.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 2: 确认 `_cascade_match` 方法可被正常引用**

```powershell
python -c "from jczx.jczxCli import JCZXGaming; assert hasattr(JCZXGaming, '_cascade_match'); print('OK')"
```

- [ ] **Step 3: 检查 `target_index` 引用已全部清除**

```powershell
Select-String -Path "jczx/jczxCli.py" -Pattern "target_index"
```
期望：无匹配输出。
