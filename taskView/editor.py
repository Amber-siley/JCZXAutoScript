"""taskView 可视化配置编辑器后端：行级 patch 写回（保留注释/空行/顺序） + 严格校验。

ConfigEditor 只处理实体文件（MainMenu.txt / tasks/*.txt）。已验证实体文件无行内注释，
注释均在行首 `/` 或 `//`；value 到行尾（可能以 `/` 开头，如 `action: /|%{x}`），不按注释切分。
"""
import os
import re
import tempfile
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
