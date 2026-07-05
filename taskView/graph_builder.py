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
_RE_EXPR = re.compile(r"&\{([^}]+)\}")
_RE_CTX = re.compile(r"%\{([^}]+)\}")


TASKS_DIR = os.path.join(CONFIG_DIR, "tasks")


def list_config_files() -> list[str]:
    files = []
    if os.path.isdir(CONFIG_DIR):
        for name in os.listdir(CONFIG_DIR):
            if name.endswith(".txt"):
                files.append(name)
    if os.path.isdir(TASKS_DIR):
        for name in os.listdir(TASKS_DIR):
            if name.endswith(".txt"):
                files.append("tasks/" + name)
    files.sort()
    return files


def _load_all_entities(filename: str) -> dict[str, JczxSectionEntity]:
    filepath = os.path.join(CONFIG_DIR, filename.replace("/", os.sep))
    all_configs: dict[str, JczxSectionEntity] = {}
    _load_one(filepath, all_configs, set())
    _resolve_extends(all_configs)
    for key, entity in all_configs.items():
        entity.only_key = key
    return all_configs


def _load_one(path: str, all_configs: dict[str, JczxSectionEntity], seen: set[str]) -> None:
    if not os.path.isfile(path) or path in seen:
        return
    seen.add(path)
    config = TxtConfig(path)
    configs = config.trans_entity_dict(JczxSectionEntity)
    for key, entity in list(configs.items()):
        if key in all_configs:
            raise ValueError(f"Duplicate section '{key}' in {path}")
        all_configs[key] = entity
        if entity.type == "file":
            sub_path = os.path.join(os.path.dirname(path),
                                    (getattr(entity, "target", "") or "").replace("/", os.sep))
            if sub_path:
                _load_one(sub_path, all_configs, seen)


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


def _find_condition_entities(configs: dict[str, JczxSectionEntity]) -> set[str]:
    result: set[str] = set()
    for entity in configs.values():
        if entity.condition:
            result.add(entity.condition)
        if entity.condition_not:
            result.add(entity.condition_not)
    return result


def build_graph(filename: str) -> dict[str, list[dict[str, Any]]]:
    try:
        configs = _load_all_entities(filename)
    except (ValueError, FileNotFoundError):
        return {"nodes": [], "edges": []}

    condition_keys = _find_condition_entities(configs)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    def _add_node(entity: JczxSectionEntity) -> str:
        nid = entity.only_key
        if nid in seen_node_ids:
            return nid
        seen_node_ids.add(nid)
        classes = entity.type or ""
        if nid in condition_keys or entity.type == "condition":
            classes = (classes + " condition-entity").strip()
        if entity.break_point == "on":
            classes = (classes + " breakpoint").strip()
        if entity.type == "file":
            classes = (classes + " file-entity").strip()
        has_test_after = bool(getattr(entity, "testFor_after", ""))
        has_test_before = bool(getattr(entity, "testFor_before", ""))
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
                "has_test_after": has_test_after,
                "has_test_before": has_test_before,
                "testFor_max_wait": getattr(entity, "testFor_max_wait", 0) or 0,
                "context_key": getattr(entity, "context_key", "") or "",
                "wait_target": getattr(entity, "wait_target", "") or "",
                "wait_target_per": getattr(entity, "wait_target_per", 0.8) or 0.8,
            },
            "classes": classes,
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

        for idx, target in enumerate(entity.action):
            if target in configs:
                _add_node(configs[target])
                if len(entity.action) > 1:
                    label = chr(0x2460 + min(idx, 19))
                else:
                    label = ""
                _add_edge(src, target, label, "action")

        if entity.condition and entity.condition in configs:
            _add_node(configs[entity.condition])
            _add_edge(src, entity.condition, "", "condition")
        if entity.condition_not and entity.condition_not in configs:
            _add_node(configs[entity.condition_not])
            _add_edge(src, entity.condition_not, "", "condition_not")

        for target in entity.condition_then:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "是", "condition_then")
        for target in entity.condition_else:
            if target in configs:
                _add_node(configs[target])
                _add_edge(src, target, "否", "condition_else")

        if entity.extend and entity.extend in configs:
            _add_edge(src, entity.extend, "继承", "extend")

        if entity.type == SectionType.TASK.value and getattr(entity, "settings", None):
            settings_key = getattr(entity, "settings", "")
            if settings_key and settings_key in configs:
                _add_node(configs[settings_key])
                _add_edge(src, settings_key, "设置", "settings")

    for key, entity in configs.items():
        src = entity.only_key
        texts = []
        if entity.target: texts.append(entity.target)
        for lst in (entity.args, entity.action, entity.condition_then,
                     entity.condition_else, entity.wait_sec):
            if lst: texts.extend(lst)
        if entity.condition: texts.append(entity.condition)
        if entity.condition_not: texts.append(entity.condition_not)
        log_v = getattr(entity, "log", "") or ""
        if log_v: texts.append(log_v)
        wt = getattr(entity, "wait_target", "") or ""
        if wt: texts.append(wt)

        for text in texts:
            if not isinstance(text, str): continue
            for m in _RE_EXEC.findall(text):
                if m in configs:
                    _add_node(configs[m])
                    _add_edge(src, m, f"@{{{m}}}", "execute")
            for m in _RE_CFG.findall(text):
                if m in configs:
                    _add_node(configs[m])
                    _add_edge(src, m, f"${{{m}}}", "config")
            for m in _RE_CTX.findall(text):
                ref_key = m.split()[0].rstrip(">")
                for ck in configs:
                    if getattr(configs[ck], "context_key", "") == ref_key:
                        _add_node(configs[ck])
                        _add_edge(src, ck, f"%{{{m}}}", "context")
            for m in _RE_EXPR.findall(text):
                for word in re.findall(r'\b([a-zA-Z][\w-]+)\b', m):
                    if word in configs:
                        _add_node(configs[word])
                        _add_edge(src, word, f"&{{{word}}}", "expression")

    return {"nodes": nodes, "edges": edges}


def build_flow_tree(filename: str, task_key: str, max_depth: int = 50) -> dict[str, Any]:
    try:
        configs = _load_all_entities(filename)
    except (ValueError, FileNotFoundError):
        return {"nodes": [], "edges": [], "cycles": []}

    condition_keys = _find_condition_entities(configs)

    if task_key not in configs:
        return {"nodes": [], "edges": [], "cycles": []}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    cycles: list[dict[str, Any]] = []
    counter: dict[str, int] = {}
    key_to_uid: dict[str, str] = {}

    def _uid(key: str) -> str:
        c = counter.get(key, 0) + 1
        counter[key] = c
        uid = f"{key}#{c}"
        key_to_uid[uid] = uid
        return uid

    def _first_uid(key: str) -> str:
        for uid in key_to_uid:
            if uid.split("#")[0] == key:
                return uid
        return ""

    def _node(entity: JczxSectionEntity, uid: str) -> dict[str, Any]:
        classes = entity.type or ""
        base = uid.split("#")[0]
        if base in condition_keys or entity.type == "condition":
            classes = (classes + " condition-entity").strip()
        if entity.break_point == "on":
            classes = (classes + " breakpoint").strip()
        if entity.type == "file":
            classes = (classes + " file-entity").strip()
        has_test_after = bool(getattr(entity, "testFor_after", ""))
        has_test_before = bool(getattr(entity, "testFor_before", ""))
        return {
            "data": {
                "id": uid, "label": entity.name or entity.desc or uid,
                "type": entity.type or "", "desc": entity.desc or "",
                "func": entity.func or "", "target": entity.target or "",
                "sleep": entity.sleep, "per": entity.per, "times": entity.times,
                "max_wait": entity.max_wait, "break_point": entity.break_point,
                "has_test_after": has_test_after,
                "has_test_before": has_test_before,
                "testFor_max_wait": getattr(entity, "testFor_max_wait", 0) or 0,
                "context_key": getattr(entity, "context_key", "") or "",
                "wait_target": getattr(entity, "wait_target", "") or "",
                "wait_target_per": getattr(entity, "wait_target_per", 0.8) or 0.8,
            },
            "classes": classes,
        }

    def _expand(key: str, path: list[str]) -> str:
        if len(path) > max_depth:
            return ""
        if key not in configs:
            return ""
        uid = _uid(key)
        entity = configs[key]
        nodes.append(_node(entity, uid))

        for idx, target in enumerate(entity.action):
            if target in path:
                label = "⟲" if len(entity.action) == 1 else chr(0x2460 + min(idx, 19))
                cycles.append({"from": uid, "to": _first_uid(target), "label": label})
                continue
            child_uid = _expand(target, path + [key])
            if child_uid:
                label = chr(0x2460 + min(idx, 19)) if len(entity.action) > 1 else ""
                edges.append({"data": {"id": f"{uid}→{child_uid}::action", "source": uid, "target": child_uid, "label": label}, "classes": "action"})

        cond_key = entity.condition or entity.condition_not
        is_not = bool(entity.condition_not)
        then_list = entity.condition_then
        else_list = entity.condition_else

        if cond_key and cond_key in configs:
            if cond_key not in path:
                cond_uid = _expand(cond_key, path + [key])
                if cond_uid:
                    edges.append({"data": {"id": f"{uid}→{cond_uid}::condition", "source": uid, "target": cond_uid, "label": ""}, "classes": "condition_not" if is_not else "condition"})
                    then_label = "否" if is_not else "是"
                    else_label = "是" if is_not else "否"
                    for t in (then_list or []):
                        if t in path:
                            cycles.append({"from": cond_uid, "to": _first_uid(t), "label": "⟲"})
                            continue
                        tuid = _expand(t, path + [key, cond_key])
                        if tuid:
                            edges.append({"data": {"id": f"{cond_uid}→{tuid}::then", "source": cond_uid, "target": tuid, "label": then_label}, "classes": "condition_then"})
                    for t in (else_list or []):
                        if t in path:
                            cycles.append({"from": cond_uid, "to": _first_uid(t), "label": "⟲"})
                            continue
                        tuid = _expand(t, path + [key, cond_key])
                        if tuid:
                            edges.append({"data": {"id": f"{cond_uid}→{tuid}::else", "source": cond_uid, "target": tuid, "label": else_label}, "classes": "condition_else"})
            elif cond_key in path:
                cycles.append({"from": uid, "to": _first_uid(cond_key), "label": "⟲"})

        elif cond_key and cond_key.startswith("&{") and (then_list or else_list):
            synth_key = f"__expr__{uid}"
            cond_uid = _uid(synth_key)
            nodes.append({"data": {"id": cond_uid, "label": cond_key[:40], "type": "condition", "times": 1, "desc": "", "func": "", "target": "", "sleep": 0, "per": 0.8, "max_wait": 0, "break_point": "off", "has_test_after": False, "has_test_before": False, "testFor_max_wait": 0, "context_key": ""}, "classes": "condition condition-entity"})
            edges.append({"data": {"id": f"{uid}→{cond_uid}::condition", "source": uid, "target": cond_uid, "label": ""}, "classes": "condition_not" if is_not else "condition"})
            for word in re.findall(r'\b([a-zA-Z][\w-]+)\b', cond_key[2:-1]):
                if word in configs:
                    e_target = _first_uid(word)
                    if not e_target:
                        e_target = _uid(word)
                        nodes.append(_node(configs[word], e_target))
                    e_label = "&{" + word + "}"
                    edges.append({"data": {"id": f"{cond_uid}_expr_{word}", "source": cond_uid, "target": e_target, "label": e_label}, "classes": "expression"})
            then_label = "否" if is_not else "是"
            else_label = "是" if is_not else "否"
            for t in (then_list or []):
                if t in path:
                    cycles.append({"from": cond_uid, "to": _first_uid(t), "label": "⟲"})
                    continue
                tuid = _expand(t, path + [key])
                if tuid:
                    edges.append({"data": {"id": f"{cond_uid}→{tuid}::then", "source": cond_uid, "target": tuid, "label": then_label}, "classes": "condition_then"})
            for t in (else_list or []):
                if t in path:
                    cycles.append({"from": cond_uid, "to": _first_uid(t), "label": "⟲"})
                    continue
                tuid = _expand(t, path + [key])
                if tuid:
                    edges.append({"data": {"id": f"{cond_uid}→{tuid}::else", "source": cond_uid, "target": tuid, "label": else_label}, "classes": "condition_else"})

        texts = []
        if entity.target: texts.append(entity.target)
        if entity.args: texts.extend(entity.args)
        if entity.condition: texts.append(entity.condition)
        if entity.condition_not: texts.append(entity.condition_not)
        for lst in (entity.wait_sec,):
            if lst: texts.extend(lst)
        log_v = getattr(entity, "log", "") or ""
        if log_v: texts.append(log_v)
        wt = getattr(entity, "wait_target", "") or ""
        if wt: texts.append(wt)

        for text in texts:
            if not isinstance(text, str): continue
            for m in _RE_EXEC.findall(text):
                if m in configs:
                    t = _first_uid(m) or _uid(m)
                    if t not in [n["data"]["id"] for n in nodes]:
                        nodes.append(_node(configs[m], t))
                    edges.append({"data": {"id": f"{uid}_exec_{m}", "source": uid, "target": t, "label": "@{" + m + "}"}, "classes": "execute"})
            for m in _RE_CFG.findall(text):
                if m in configs:
                    t = _first_uid(m) or _uid(m)
                    if t not in [n["data"]["id"] for n in nodes]:
                        nodes.append(_node(configs[m], t))
                    edges.append({"data": {"id": f"{uid}_cfg_{m}", "source": uid, "target": t, "label": "${" + m + "}"}, "classes": "config"})
            for m in _RE_CTX.findall(text):
                ref_key = m.split()[0].rstrip(">")
                for ck in configs:
                    if getattr(configs[ck], "context_key", "") == ref_key:
                        edges.append({"data": {"id": f"{uid}_ctx_{ck}", "source": uid, "target": ck + "#1", "label": "%{" + m + "}"}, "classes": "context"})
            for m in _RE_EXPR.findall(text):
                for word in re.findall(r'\b([a-zA-Z][\w-]+)\b', m):
                    if word in configs:
                        t = _first_uid(word) or _uid(word)
                        if t not in [n["data"]["id"] for n in nodes]:
                            nodes.append(_node(configs[word], t))
                        edges.append({"data": {"id": f"{uid}_expr_{word}", "source": uid, "target": t, "label": "&{" + word + "}"}, "classes": "expression"})

        return uid

    _expand(task_key, [])
    return {"nodes": nodes, "edges": edges, "cycles": cycles}


def get_entity_detail(filename: str, entity_name: str) -> dict[str, Any] | None:
    try:
        configs = _load_all_entities(filename)
    except (ValueError, FileNotFoundError):
        return None

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
        "context_key": getattr(entity, "context_key", "") or "",
        "context_type": getattr(entity, "context_type", "") or "",
        "testFor_before": getattr(entity, "testFor_before", "") or "",
        "testFor_after": getattr(entity, "testFor_after", "") or "",
        "testFor_max_wait": getattr(entity, "testFor_max_wait", 0) or 0,
        "testFor_pre_sleep": getattr(entity, "testFor_pre_sleep", 0) or 0,
        "testFor_sleep": getattr(entity, "testFor_sleep", 0) or 0,
        "testFor_per": getattr(entity, "testFor_per", 0.8) or 0.8,
        "log": getattr(entity, "log", "") or "",
        "log_level": getattr(entity, "log_level", "") or "",
        "wait_target": getattr(entity, "wait_target", "") or "",
        "wait_target_per": getattr(entity, "wait_target_per", 0.8) or 0.8,
    }
