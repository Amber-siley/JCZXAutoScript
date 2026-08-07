"""taskView 可视化配置编辑器后端：行级 patch 写回（保留注释/空行/顺序） + 严格校验。

ConfigEditor 只处理实体文件（MainMenu.txt / tasks/*.txt）。已验证实体文件无行内注释，
注释均在行首 `/` 或 `//`；value 到行尾（可能以 `/` 开头，如 `action: /|%{x}`），不按注释切分。
"""
import os
import re
import tempfile
from copy import deepcopy
from hashlib import sha1
from typing import Optional

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jczx", "Config")
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jczx", "resources")

_SECTION_RE = re.compile(r"^\s*\[(?P<section>[^\]\r\n]+)\]\s*$")
# 兼容 TxtConfig：key 不含冒号，chain 为任意空白:空白，value 到行尾（去尾空白）
_OPTION_RE = re.compile(r"^(?P<key>[^:\r\n]+?)\s*(?P<chain>:)(?P<value>.*?)\s*$")


class _EntityModel:
    """单个实体 section 的行模型。"""
    __slots__ = ("name", "header_idx", "option_lines")

    def __init__(self, name: str, header_idx: int):
        self.name = name                # section 名（key）
        self.header_idx = header_idx    # section 头行索引
        self.option_lines = []          # 该 section 内 option 行索引（有序）


class ConfigEditor:
    def __init__(self, path: str):
        self.path = path
        self._lines: list[str] = []                 # 原始行（不含换行符）
        self._entities: list[_EntityModel] = []     # 有序实体
        self._entity_by_name: dict[str, _EntityModel] = {}

    def load(self) -> None:
        with open(self.path, encoding="utf-8") as fp:
            self._lines = [ln.rstrip("\r\n") for ln in fp.readlines()]
        self._reindex()

    def _reindex(self) -> None:
        """从当前 self._lines 重建实体索引（不访问磁盘）。

        load() 先读盘再调用本方法；行级修改（update_value/add_option/
        add_entity/delete_entity/rename_entity）只改内存行，须调用本方法
        而非 load()，否则会从磁盘重读而丢失未落盘的内存修改。
        """
        self._entities = []
        self._entity_by_name = {}
        cur: Optional[_EntityModel] = None
        for i, line in enumerate(self._lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("/"):
                continue                        # blank / 行首注释，跳过
            m = _SECTION_RE.match(line)
            if m:
                cur = _EntityModel(m.group("section").strip(), i)
                self._entities.append(cur)
                self._entity_by_name[cur.name] = cur
                continue
            m = _OPTION_RE.match(line)
            if m and cur is not None:
                cur.option_lines.append(i)

    @property
    def text(self) -> str:
        return "\n".join(self._lines) + ("\n" if self._lines else "")

    @property
    def sections(self) -> list[str]:
        return [e.name for e in self._entities]

    def _entity(self, key: str) -> _EntityModel:
        if key not in self._entity_by_name:
            raise ValueError(f"实体不存在: {key}")
        return self._entity_by_name[key]

    def update_value(self, key: str, option: str, value: str) -> None:
        ent = self._entity(key)
        for i in ent.option_lines:
            m = _OPTION_RE.match(self._lines[i])
            if m and m.group("key").strip() == option:
                # 保留原行 key+chain 前缀，只替换 value
                head = self._lines[i][: self._lines[i].find(m.group("value"))]
                self._lines[i] = head.rstrip() + " " + value
                return
        raise ValueError(f"实体 {key} 无字段 {option}")

    def add_option(self, key: str, option: str, value: str) -> None:
        """在实体末尾追加一个 option 行。

        用于 extend 实体的继承字段更新落盘：文件里没有该 option 行时，
        update_value 会抛 ValueError，此方法把字段行追加到 section 末尾。
        """
        ent = self._entity(key)
        insert_at = ent.option_lines[-1] + 1 if ent.option_lines else ent.header_idx + 1
        self._lines.insert(insert_at, f"{option}: {value}")
        self._reindex()

    def add_entity(self, key: str, fields: dict[str, str]) -> None:
        if key in self._entity_by_name:
            raise ValueError(f"实体已存在: {key}")
        lines = ["", f"[{key}]"]
        for opt, val in fields.items():
            lines.append(f"{opt}: {val}")
        # 追加到文件末尾；若文件末尾无空行则补一个空行分隔
        if self._lines and self._lines[-1].strip():
            self._lines.append("")
        self._lines.extend(lines)
        self._reindex()  # 重建索引

    def delete_entity(self, key: str) -> None:
        ent = self._entity(key)
        drop = {ent.header_idx, *ent.option_lines}
        self._lines = [ln for i, ln in enumerate(self._lines) if i not in drop]
        self._reindex()

    def rename_entity(self, old: str, new: str) -> None:
        if new in self._entity_by_name:
            raise ValueError(f"实体已存在: {new}")
        ent = self._entity(old)
        self._lines[ent.header_idx] = re.sub(r"\[[^\]]+\]", f"[{new}]", self._lines[ent.header_idx])
        self._reindex()

    def save(self) -> None:
        dirn = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(prefix=".jczx-edit-", suffix=".tmp", dir=dirn)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(self.text)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def file_hash(path: str) -> str:
    h = sha1()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Task 2: 校验层 —— 实体池加载、模拟应用、严格校验
# ---------------------------------------------------------------------------
from jczx.configEntity import JczxSectionEntity, SectionType
from jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig
from jczx.jczxCli import JCZXGaming

_REF_FIELDS = ("action", "condition", "condition_not", "condition_then",
               "condition_else", "extend", "match")
_PLACEHOLDER_RE = re.compile(r"\$\{[^}]*\}|@\{[^}]*\}|%\{[^}]*\}|&\{[^}]*\}")


def _is_editable_file(file: str) -> bool:
    """可编辑文件范围：归一化后必须落在 CONFIG_DIR 内；排除 Config.txt/Queues.txt。

    用 normpath + commonpath 归一化，防止 `tasks/../Config.txt` 之类路径绕过排除。
    """
    full = os.path.normpath(os.path.join(CONFIG_DIR, file))
    base = os.path.basename(full)
    if not file.endswith(".txt") or base in ("Config.txt", "Queues.txt"):
        return False
    try:
        return os.path.commonpath([full, CONFIG_DIR]) == os.path.normpath(CONFIG_DIR)
    except ValueError:
        return False


def load_entity_pool() -> tuple[dict[str, JczxSectionEntity], dict[str, str]]:
    """加载 MainMenu.txt + tasks/*.txt 全部实体，返回 (pool, entity_file)。跨文件重名抛 ValueError。"""
    pool: dict[str, JczxSectionEntity] = {}
    entity_file: dict[str, str] = {}

    def _load(path: str, seen: set[str]) -> None:
        path = os.path.normpath(path)
        if path in seen or not os.path.isfile(path):
            return
        seen.add(path)
        cfg = TxtConfig(path)
        for key, ent in cfg.trans_entity_dict(JczxSectionEntity).items():
            if key in pool:
                raise ValueError(f"跨文件实体重名: {key}")
            pool[key] = ent
            entity_file[key] = path
            if ent.type == SectionType.FILE.value:
                sub = os.path.join(os.path.dirname(path),
                                   (getattr(ent, "target", "") or "").replace("/", os.sep))
                _load(sub, seen)

    seen: set[str] = set()
    _load(os.path.join(CONFIG_DIR, "MainMenu.txt"), seen)
    tasks_dir = os.path.join(CONFIG_DIR, "tasks")
    if os.path.isdir(tasks_dir):
        for name in sorted(os.listdir(tasks_dir)):
            if name.endswith(".txt"):
                _load(os.path.join(tasks_dir, name), seen)
    for key, ent in pool.items():
        ent.only_key = key
    return pool, entity_file


def _apply_field(ent: JczxSectionEntity, field: str, value: str, errors: list[dict]) -> None:
    """把字符串值设置到实体字段，复用 __setattr__ 类型转换；失败记错误。"""
    if field not in ent.__dataclass_fields__:
        errors.append({"file": ent.only_key or "", "key": ent.only_key or "",
                       "field": field, "message": f"未知字段: {field}"})
        return
    try:
        setattr(ent, field, value)
    except Exception as e:
        errors.append({"file": ent.only_key or "", "key": ent.only_key or "",
                       "field": field, "message": f"字段类型错误: {e}"})


def _validate_entity(pool: dict[str, JczxSectionEntity], key: str,
                     ent: JczxSectionEntity, resources_dir: str) -> list[dict]:
    errors: list[dict] = []
    e = {"file": "", "key": key, "field": "", "message": ""}

    if ent.type and not SectionType.__contains__(ent.type):
        return [{**e, "message": f"非法 type: {ent.type}"}]

    for f in _REF_FIELDS:
        val = getattr(ent, f, None)
        if f == "action" and ent.type in (SectionType.MATCH.value, SectionType.CONTEXT.value):
            continue    # match/context 的 action 是操作指令（+|1、right|1），非实体引用
        if isinstance(val, str):
            if val and not _PLACEHOLDER_RE.search(val) and val not in pool:
                errors.append({**e, "field": f, "message": f"引用实体不存在: {val}"})
        elif isinstance(val, list):
            for item in val:
                if item and not _PLACEHOLDER_RE.search(item) and item not in pool:
                    errors.append({**e, "field": f, "message": f"引用实体不存在: {item}"})

    settings = getattr(ent, "settings", None)
    if settings:
        if settings not in pool:
            errors.append({**e, "field": "settings", "message": f"settings 引用实体不存在: {settings}"})
        elif pool[settings].type != SectionType.SETTINGS.value:
            errors.append({**e, "field": "settings", "message": f"{settings} 不是 settings 实体"})

    target = getattr(ent, "target", "") or ""
    if ent.type in (SectionType.CLICK.value, SectionType.MATCH.value, SectionType.OCR.value) \
            and target and not _PLACEHOLDER_RE.search(target):
        img = os.path.join(resources_dir, target.replace("\\", os.sep))
        if not os.path.isfile(img):
            errors.append({**e, "field": "target", "message": f"图片资源不存在: {target}"})

    func = getattr(ent, "func", "") or ""
    if ent.type == SectionType.FUNC.value and func and not hasattr(JCZXGaming, func):
        errors.append({**e, "field": "func", "message": f"JCZXGaming 无方法: {func}"})

    return errors


def _validate_pool(pool: dict[str, JczxSectionEntity], resources_dir: str) -> list[dict]:
    errors: list[dict] = []
    for key, ent in pool.items():
        errors.extend(_validate_entity(pool, key, ent, resources_dir))
    return errors


def simulate_and_validate(pool, entity_file, file: str, ops: list[dict]) -> tuple[list[tuple[str, str]], list[dict]]:
    """模拟应用 ops → 校验 → 返回 (writes, errors)。ops 结构非法抛 ValueError。"""
    if not _is_editable_file(file):
        raise ValueError(f"不可编辑文件: {file}")

    # 目标文件路径 + 复制实体池与实体文件映射（避免污染加载结果）
    target_path = os.path.join(CONFIG_DIR, *file.split("/"))
    new_pool = deepcopy(pool)
    entity_file = dict(entity_file)
    errors: list[dict] = []
    # 变更明细：文件路径 -> 实体 key -> 变更序列。writeback 只按明细写，
    # 不再遍历实体全字段，避免把默认值/未变更字段一并落盘（C1）。
    changes: dict[str, dict[str, list[dict]]] = {}

    def _record(path: str, key: str, chg: dict) -> None:
        lst = changes.setdefault(path, {}).setdefault(key, [])
        if chg["op"] == "update" and lst and lst[-1]["op"] == "update":
            lst[-1]["fields"].update(chg["fields"])
        else:
            lst.append(chg)

    for op in ops:
        t = op.get("type")
        if t == "update":
            key = op["key"]
            if key not in new_pool:
                errors.append({"file": file, "key": key, "field": "", "message": f"实体不存在: {key}"})
                continue
            ent = new_pool[key]
            fields = op.get("fields", {})
            for field, value in fields.items():
                _apply_field(ent, field, value, errors)
            _record(entity_file[key], key, {"op": "update", "fields": dict(fields)})
        elif t == "create":
            key = op["key"]
            if key in new_pool:
                errors.append({"file": file, "key": key, "field": "", "message": f"实体已存在: {key}"})
                continue
            ent = JczxSectionEntity()
            fields = op.get("entity", {})
            for field, value in fields.items():
                _apply_field(ent, field, value, errors)
            if not ent.type:
                errors.append({"file": file, "key": key, "field": "type", "message": "缺少 type"})
            new_pool[key] = ent
            entity_file[key] = target_path
            # 只写 op.entity 提供的字段，不转写实体全字段
            _record(target_path, key, {"op": "create", "fields": dict(fields)})
        elif t == "delete":
            key = op["key"]
            if key not in new_pool:
                errors.append({"file": file, "key": key, "field": "", "message": f"实体不存在: {key}"})
                continue
            del new_pool[key]
            # 本批次内新建的实体不在原 entity_file，已由 create 分支归入目标文件
            _record(entity_file.get(key, target_path), key, {"op": "delete"})
        elif t == "rename":
            old, new = op["old"], op["new"]
            if old not in new_pool or new in new_pool:
                errors.append({"file": file, "key": old, "field": "",
                               "message": "重命名失败（源不存在或目标已存在）"})
                continue
            old_path = entity_file[old]
            new_pool[new] = new_pool.pop(old)
            entity_file[new] = entity_file.pop(old)
            _record(old_path, new, {"op": "rename", "old": old})
            # 同步更新所有引用 old 的字段（内存 + 变更明细）
            for other_key, other in new_pool.items():
                changed_fields: dict[str, str] = {}
                for f in _REF_FIELDS:
                    val = getattr(other, f, None)
                    if isinstance(val, str) and val == old:
                        setattr(other, f, new)
                        changed_fields[f] = new
                    elif isinstance(val, list) and old in val:
                        nv = [new if x == old else x for x in val]
                        setattr(other, f, nv)
                        changed_fields[f] = ",".join(str(x) for x in nv)
                if changed_fields:
                    _record(entity_file[other_key], other_key,
                            {"op": "update", "fields": changed_fields})
        else:
            raise ValueError(f"未知变更类型: {t}")

    # 严格校验（模拟后快照）
    errors.extend(_validate_pool(new_pool, RESOURCES_DIR))

    if errors:
        return [], errors

    # 生成写回：按变更明细逐项应用（只写实际变更，不遍历实体全字段）
    writes: list[tuple[str, str]] = []
    for path, keys_changes in changes.items():
        ed = ConfigEditor(path)
        ed.load()
        for key, chg_list in keys_changes.items():
            for chg in chg_list:
                if chg["op"] == "delete":
                    if key in ed.sections:
                        ed.delete_entity(key)
                elif chg["op"] == "rename":
                    ed.rename_entity(chg["old"], key)
                elif chg["op"] == "create":
                    ed.add_entity(key, {k: str(v) for k, v in chg["fields"].items()})
                elif chg["op"] == "update":
                    for field, value in chg["fields"].items():
                        value = str(value)
                        try:
                            ed.update_value(key, field, value)
                        except ValueError:
                            ed.add_option(key, field, value)  # 文件无此字段行 → 追加（extend 继承字段落盘）
        writes.append((path, ed.text))
    return writes, []


def write_text_atomic(path: str, text: str) -> None:
    dirn = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".jczx-edit-", suffix=".tmp", dir=dirn)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
