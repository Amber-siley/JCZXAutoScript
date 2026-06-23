from dataclasses import dataclass, field
from enum import Enum
from typing import get_type_hints, get_origin, get_args

LIST_STR_ATTRS = ["list_targets", "action", "list_actions", "choose_tasks", "args", "pos", "condition_then", "condition_else"]

class SectionType(Enum):
    TASK = "task"
    FUNC = "func"
    FILE = "file"
    CLICK = "click"
    OPTION = "option"
    SETTINGS = "settings"
    SETTING = "setting"
    DYNAMIC = "dynamic"
    MATCH = "match"
    OCR = "ocr"
    CONTEXT = "context"
    CONDITION = "condition"
    
    @classmethod
    def __contains__(cls, value):
        return (value in cls._value2member_map_) or (value in cls._member_names_)
    
    @staticmethod
    def is_img_types(value):
        return value in [SectionType.CLICK.value]

@dataclass
class BaseEntity:
    _type_hints_cache = None

    def __setattr__(self, name, value):
        if value is None:
            super().__setattr__(name, value)
            return
        cls = type(self)
        if cls._type_hints_cache is None:
            cls._type_hints_cache = get_type_hints(cls)
        hints = cls._type_hints_cache
        if name not in hints:
            super().__setattr__(name, value)
            return
        typ = hints[name]
        origin = get_origin(typ)
        if origin is list:
            if isinstance(value, list):
                super().__setattr__(name, value)
                return
            args = get_args(typ)
            value_typ = args[0] if args else str
            values = [value_typ(v) for v in value.split(",")]
            super().__setattr__(name, values)
        else:
            super().__setattr__(name, typ(value))

@dataclass
class JczxSectionEntity(BaseEntity):
    type: str = None
    target: str = None
    func: str = None
    index: int = 0
    name: str = None
    desc: str = None
    action: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    pos: list[int] = field(default_factory=list)
    pre_sleep: float = 0
    sleep: float = 0
    per: float = 0.8
    max_wait: float = 0
    wait_sec: list[str] = field(default_factory=list)
    condition: str = None
    condition_not: str = None
    condition_then: list[str] = field(default_factory=list)
    condition_else: list[str] = field(default_factory=list)
    break_point: str = "off"
    extend: str = None
    else_target: list[str] = field(default_factory=list)
    view: str = "off"
    only_key: str = None
    times: int = 1
    context_key: str = None
    context_type: str = "str"
    context_default_type: str = "str"
    context_get: str = None
    context_default: str = ""
    match: str = None
    testFor_before: str = None
    testFor_after: str = None
    testFor_max_wait: float = 0
    testFor_per: float = 0.8
    testFor_pre_sleep: float = 0
    testFor_sleep: float = 0
    
    def get_task_name(self):
        return self.name or self.desc

@dataclass
class JczxConfigFileEntity(BaseEntity):
    type: str = None
    path: str = None
    description: str = None
    choose_tasks: list[str] = None

@dataclass
class JczxSettingEntity(BaseEntity):
    type: str = None
    name: str = None             # 字段标识符（section 名），用于 DOM id 和配置键
    setting_type: str = None
    label: str = None
    desc: str = None
    options: list[str] = field(default_factory=list)
    switch_label: str = None
    default: str = ""
    min: int = None
    max: int = None
    fields: list[str] = field(default_factory=list)
