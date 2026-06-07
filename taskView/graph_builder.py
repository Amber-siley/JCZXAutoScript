import os
import re
from typing import Any

from jczx.CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig
from jczx.configEntity import JczxSectionEntity, SectionType


CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "jczx", "Config"
)

_RE_EXEC = re.compile(r"@\{([^}]+)\}")
_RE_CFG = re.compile(r"\$\{([^}:]+)(?::[^}]*)?}")


def list_config_files() -> list[str]:
    files = []
    if os.path.isdir(CONFIG_DIR):
        for name in os.listdir(CONFIG_DIR):
            if name.endswith(".txt"):
                files.append(name)
    files.sort()
    return files


def _resolve_extends(configs: dict[str, JczxSectionEntity]) -> None:
    default_entity = JczxSectionEntity()
    for key, entity in configs.items():
        if not entity.extend:
            continue
        parent = configs.get(entity.extend)
        if not parent:
            continue
        for field_name in entity.__dataclass_fields__:
            if field_name == "extend":
                continue
            child_val = getattr(entity, field_name)
            if child_val == getattr(default_entity, field_name):
                setattr(entity, field_name, getattr(parent, field_name))


def build_graph(filename: str) -> dict[str, list[dict[str, Any]]]:
    filepath = os.path.join(CONFIG_DIR, filename)
    if not os.path.isfile(filepath):
        return {"nodes": [], "edges": []}

    config = TxtConfig(filepath)
    configs = config.trans_entity_dict(JczxSectionEntity)
    _resolve_extends(configs)

    for key, entity in configs.items():
        entity.only_key = key

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    def _add_node(entity: JczxSectionEntity) -> str:
        nid = entity.only_key
        if nid in seen_node_ids:
            return nid
        seen_node_ids.add(nid)
        nodes.append({
            "data": {
                "id": nid,
                "label": entity.name or entity.desc or nid,
                "type": entity.type or "",
                "desc": entity.desc or "",
                "func": entity.func or "",
                "target": entity.target or "",
                "sleep": entity.sleep,
                "per": entity.per,
                "times": entity.times,
                "max_wait": entity.max_wait,
                "break_point": entity.break_point,
            },
            "classes": entity.type or "",
        })
        return nid

    def _add_edge(source_id: str, target_id: str, label: str, classes: str):
        if not target_id:
            return
        eid = f"{source_id}→{target_id}::{label}"
        if eid in seen_edge_ids:
            return
        seen_edge_ids.add(eid)
        edges.append({
            "data": {
                "id": eid,
                "source": source_id,
                "target": target_id,
                "label": label,
            },
            "classes": classes,
        })

    for key, entity in configs.items():
        _add_node(entity)

    for key, entity in configs.items():
        src = entity.only_key

        for target in entity.action:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "action", "action")

        for i in range(len(entity.action) - 1):
            a, b = entity.action[i], entity.action[i + 1]
            if a in configs and b in configs:
                _add_edge(a, b, "", "chain")

        if entity.condition and entity.condition in configs:
            _add_node(configs[entity.condition])
            _add_edge(src, entity.condition, "condition", "condition")
        if entity.condition_not and entity.condition_not in configs:
            _add_node(configs[entity.condition_not])
            _add_edge(src, entity.condition_not, "condition_not", "condition_not")

        for target in entity.condition_then:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "condition_then", "condition_then")
        for target in entity.condition_else:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "condition_else", "condition_else")

        if entity.extend and entity.extend in configs:
            _add_edge(src, entity.extend, "extend", "extend")

        if entity.type == SectionType.TASK.value and getattr(entity, "settings", None):
            settings_key = getattr(entity, "settings", "")
            if settings_key and settings_key in configs:
                _add_node(configs[settings_key])
                _add_edge(src, settings_key, "settings", "settings")

    for key, entity in configs.items():
        src = entity.only_key
        texts = []
        if entity.target:
            texts.append(entity.target)
        for lst in (entity.args, entity.action, entity.condition_then,
                     entity.condition_else, entity.wait_sec):
            if lst:
                texts.extend(lst)
        if entity.condition:
            texts.append(entity.condition)
        if entity.condition_not:
            texts.append(entity.condition_not)

        for text in texts:
            if not isinstance(text, str):
                continue
            for m in _RE_EXEC.findall(text):
                if m in configs:
                    _add_node(configs[m])
                    _add_edge(src, m, f"@{{{m}}}", "execute")
            for m in _RE_CFG.findall(text):
                if m in configs:
                    _add_node(configs[m])
                    _add_edge(src, m, f"${{{m}}}", "config")

    return {"nodes": nodes, "edges": edges}


def get_entity_detail(filename: str, entity_name: str) -> dict[str, Any] | None:
    filepath = os.path.join(CONFIG_DIR, filename)
    if not os.path.isfile(filepath):
        return None

    config = TxtConfig(filepath)
    configs = config.trans_entity_dict(JczxSectionEntity)
    _resolve_extends(configs)

    if entity_name not in configs:
        return None

    entity = configs[entity_name]
    entity.only_key = entity_name
    return {
        "key": entity_name,
        "type": entity.type or "",
        "name": entity.name or "",
        "desc": entity.desc or "",
        "func": entity.func or "",
        "target": entity.target or "",
        "action": entity.action,
        "args": entity.args,
        "pos": entity.pos,
        "pre_sleep": entity.pre_sleep,
        "sleep": entity.sleep,
        "per": entity.per,
        "max_wait": entity.max_wait,
        "wait_sec": entity.wait_sec,
        "condition": entity.condition or "",
        "condition_not": entity.condition_not or "",
        "condition_then": entity.condition_then,
        "condition_else": entity.condition_else,
        "break_point": entity.break_point,
        "extend": entity.extend or "",
        "times": entity.times,
    }
