from .configEntity import JczxConfigFileEntity, JczxSectionEntity, JczxSettingEntity, SectionType
from .CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import Config, TxtConfig, FileManage
from .CommoneBuilder.CommonBuilder.FileTools.Base.Variable import DictVariable

from logging import Logger
from typing import Optional
import re

import cv2

from cv2.typing import MatLike
from dataclasses import dataclass

@dataclass
class QueueEntity:
    id: str
    name: str
    tasks: list[str]

class TaskManage:
    def __init__(self, config_dir: str, log: Logger = None):
        # 创建默认配置
        self.fm = FileManage(FileManage(__file__).work_path)
        self.default_config_dir = self.fm.get_obj_relative_path("Config", self)
        self.default_config_path = self.fm.get_obj_relative_path("Config\\Config.txt", self)
        self.config_dir = config_dir if config_dir else self.default_config_dir
        self.main_config_path = self.fm.join(self.config_dir, "Config.txt", seq="\\")
        self.menu_config_path = self.fm.join(self.config_dir, "MainMenu.txt", seq="\\")
        self.main_config: TxtConfig = None
        self.menu_config: TxtConfig = None
        # 图片池
        self._entity_source: dict[str, str] = {}
        self._external_configs: list = []
        self.img_pool = DictVariable()
        self.entity_pool = DictVariable()
        self.task_pool = DictVariable()
        self.log = log if log else Logger("TaskManage")
        self.ready_env()
    
    def ready_env(self):
        if self.config_dir:
            self.fm.makedirs(self.config_dir)
        self.log.debug(f"读取配置文件，主配置路径：{self.main_config_path}，任务配置路径：{self.menu_config_path}")
        if not self.fm.isfile(self.main_config_path):
            config_path = self.fm.join_p("Config", "Config.txt")
            self.fm.cp(config_path, self.main_config_path)
        self.main_config = Config(self.main_config_path).Config
        if not self.fm.isfile(self.menu_config_path):
            menu_config_path = self.fm.join_p("Config", "MainMenu.txt")
            self.fm.cp(menu_config_path, self.menu_config_path)
        self.menu_config = Config(self.menu_config_path).Config
        self.load_task_entity_pool()
        self.load_img_pool()
        
    def refresh_config(self):
        self.log.debug("刷新配置文件")
        self.ready_env()

    @staticmethod
    def read_gray_img(img_path: str) -> MatLike:
        return cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    
    def get_resources_target(self, target: str):
        name = self._resolve_placeholder(target)
        rel_path = "\\".join(["resources"] + name.split("\\"))
        return str(self.fm.get_obj_relative_path(rel_path, self))
    
    def load_img_pool(self):
        """加载图片缓冲池

        Args:
            reboot (bool, optional): 是否重载图片. Defaults to False.
        """
        self.img_pool.clear()
        self.log.debug("开始加载图片缓冲池")
        configs = self.entity_pool
        put_size, fail_size = 0, 0
        for config_entity in configs.values():
            target = config_entity.target
            if target:
                if self._load_img_to_pool(target):
                    put_size += 1
                else:
                    fail_size += 1
            if config_entity.testFor_before:
                if self._load_img_to_pool(config_entity.testFor_before):
                    put_size += 1
                else:
                    fail_size += 1
            if config_entity.testFor_after:
                if self._load_img_to_pool(config_entity.testFor_after):
                    put_size += 1
                else:
                    fail_size += 1
        self.log.debug(f"图片缓冲池加载完成，成功加载 {put_size} 张图片，失败 {fail_size} 张图片")

    def _load_img_to_pool(self, target: str) -> bool:
        if target in self.img_pool:
            return True
        rel_target = self.get_resources_target(target)
        if not self.fm.isfile(rel_target):
            self.log.debug(f"图片路径 {target} 不存在，跳过加载")
            return False
        self.log.debug(f"加载图片 {target} 到缓冲池")
        self.img_pool[target] = self.read_gray_img(rel_target)
        return True
    
    def load_task_entity_pool(self):
        self.log.debug("开始加载任务实体池")
        self._entity_source.clear()
        self._external_configs.clear()
        configs = self.menu_config.trans_entity_dict(JczxSectionEntity)

        file_entities = []
        task_configs = {}
        for key, value in configs.items():
            if value.type == SectionType.FILE.value:
                file_entities.append((key, value))
            else:
                task_configs[key] = value

        for key, file_entity in file_entities:
            target = file_entity.target
            if not target:
                self.log.warning(f"file 实体 {key} 缺少 target，跳过")
                continue
            target = self._resolve_placeholder(target, key)
            external_path = self.fm.join(self.config_dir, target, seq="\\")
            if not self.fm.isfile(external_path):
                self.log.error(f"外部配置文件不存在: {external_path}")
                continue
            external_config = Config(external_path).Config
            self._external_configs.append((external_path, external_config))
            external_configs = external_config.trans_entity_dict(JczxSectionEntity)
            external_configs = {k: v for k, v in external_configs.items() if v.type != SectionType.FILE.value}
            dup_keys = set(external_configs.keys()) & set(task_configs.keys())
            if dup_keys:
                dup_detail = ", ".join(f'"{k}"' for k in dup_keys)
                raise ValueError(
                    f"实体 key 冲突: {target} 与已加载实体中重复定义了 {dup_detail}")
            for e_key, e_val in external_configs.items():
                self._entity_source[e_key] = external_path
            task_configs.update(external_configs)
            self.menu_config.merge(external_config)
            external_config.init_configs()
            self.log.debug(f"已加载外部配置 {target}，{len(external_configs)} 个实体")

        for key in task_configs:
            if key not in self._entity_source:
                self._entity_source[key] = self.menu_config_path

        self._resolve_extends(task_configs)
        for key, value in task_configs.items():
            value.only_key = key
            self.entity_pool[key] = value
            self.log.debug(f"加载实体 {key} 到实体池，{value}")
            if value.type == SectionType.TASK.value:
                self.task_pool[key] = value
        self.log.debug(f"任务实体池加载完成，共 {len(self.entity_pool)} 个实体，其中 {len(self.task_pool)} 个任务")

    def _resolve_extends(self, configs: dict[str, JczxSectionEntity]) -> None:
        default_entity = JczxSectionEntity()
        for key, entity in configs.items():
            if not entity.extend:
                continue
            parent = configs.get(entity.extend)
            if not parent:
                self.log.debug(f"实体 {key} 的 extend 目标 {entity.extend} 未在实体池中找到")
                continue
            self.log.debug(f"实体 {key} 继承自 {entity.extend}")
            for field_name in entity.__dataclass_fields__:
                if field_name == "extend":
                    continue
                child_val = getattr(entity, field_name)
                if child_val == getattr(default_entity, field_name):
                    setattr(entity, field_name, getattr(parent, field_name))
    
    def get_task(self, task_name: str) -> JczxSectionEntity:
        """获取任务实体

        Args:
            task_name (str): 任务名称

        Returns:
            JczxSectionEntity: 任务实体
        """
        return self.task_pool[task_name]
    
    def get_task_names(self) -> list[str]:
        """获取可见任务 key 列表（view != off）"""
        return [k for k, v in self.task_pool.items() if v.view != "off"]

    def get_task_display_name(self, task_key: str) -> str:
        """获取任务的中文显示名称"""
        entity = self.get_task(task_key)
        if entity:
            return entity.name or entity.desc or task_key
        return task_key
    
    def get_img(self, img_path: str) -> MatLike:
        """获取图片

        Args:
            img_path (str): 图片路径

        Returns:
            MatLike: 图片
        """
        name = self._resolve_placeholder(img_path)
        return self.img_pool[name]

    def get_entity(self, entity_name: str, after_key: str = None) -> JczxSectionEntity:
        """获取实体

        Args:
            entity_name (str): 实体名称

        Returns:
            JczxSectionEntity: 实体
        """
        name = self._resolve_placeholder(entity_name, after_key)
        return self.entity_pool[name]
     
    def get_next(self, section: JczxSectionEntity) -> list[JczxSectionEntity]:
        if section.action:
            return [self.get_entity(i) for i in section.action]
        return []

    def get_task_setting_entities(self, task_key: str) -> list[JczxSettingEntity]:
        """获取任务的设置字段定义列表。"""
        try:
            settings_section = self.menu_config.get_config(task_key, "settings")
        except KeyError:
            return []
        if not settings_section:
            return []
        settings_entity = self._get_setting_entity(settings_section, SectionType.SETTINGS)
        if not settings_entity or not settings_entity.fields:
            return []
        result: list[JczxSettingEntity] = []
        for field_name in settings_entity.fields:
            se = self._get_setting_entity(field_name.strip(), SectionType.SETTING)
            if se and se.setting_type:
                result.append(se)
        return result

    def _get_setting_entity(self, section_name: str, expected_type: SectionType = SectionType.SETTING) -> JczxSettingEntity | None:
        if section_name in self.entity_pool:
            existing = self.entity_pool[section_name]
            if isinstance(existing, JczxSettingEntity):
                return existing
        try:
            sec_data = self.menu_config.get_section(section_name)
        except KeyError:
            return None
        entity = JczxSettingEntity()
        for opt, entry in sec_data.items():
            if opt in entity.__dict__:
                entity.__setattr__(opt, entry.value)
        if entity.type == expected_type.value:
            entity.name = section_name
            self.entity_pool[section_name] = entity
            return entity
        return None

    def get_task_values(self, task_key: str) -> dict[str, str]:
        """读取任务已保存的设置值。"""
        section = f"{task_key}-values"
        try:
            sec_data = self.menu_config.get_section(section)
        except KeyError:
            return {}
        return {opt: entry.value for opt, entry in sec_data.items()}

    def save_task_values(self, task_key: str, values: dict[str, object]) -> None:
        section = f"{task_key}-values"
        source = self._entity_source.get(task_key, self.menu_config_path)
        target_config = self.menu_config
        for path, ext_config in self._external_configs:
            if path == source:
                target_config = ext_config
                break
        for field_name, val in values.items():
            target_config.set_config(section, field_name, str(val))
            if target_config is not self.menu_config:
                self.menu_config.set_config(section, field_name, str(val))
        target_config.save()
        self.log.debug(f"任务 {task_key} 设置已保存到 {source}: {values}")
        self._update_entities_after_save(task_key)

    def _update_entities_after_save(self, task_key: str) -> None:
        entity = self.get_task(task_key)
        if not entity or not entity.settings:
            return
        source = self._entity_source.get(task_key, self.menu_config_path)
        target_config = self.menu_config
        for path, ext_config in self._external_configs:
            if path == source:
                target_config = ext_config
                break
        try:
            settings_section = target_config.get_config(task_key, "settings")
        except KeyError:
            return
        if not settings_section:
            return
        settings_entity = self._get_setting_entity(settings_section, SectionType.SETTINGS)
        if not settings_entity:
            return
        self.entity_pool[settings_section] = settings_entity
        self.log.debug(f"已刷新实体 {settings_section}")

    _PLACEHOLDER_PATTERN = re.compile(r"\$\{(.+?)\}")

    def resolve_placeholders(self, args: list, task_key: str = None) -> list:
        """解析参数列表中的 ${...} 占位符。

        - ${option}              → {task_key}-values.option
        - ${section:option}      → section.option
        - ${section:option:def}  → section.option 或默认值 def
        """
        resolved = []
        for arg in args:
            result = self._resolve_placeholder(arg, task_key)
            resolved.append(result)
        return resolved
    
    def _resolve_placeholder(self, arg: str, task_key: str = None) -> str:
        if not isinstance(arg, str):
            return arg
        result = arg
        for match in self._PLACEHOLDER_PATTERN.findall(arg):
            parts = match.split(":", 2)
            if len(parts) == 1:
                section = f"{task_key}-values" if task_key else "default"
                option = parts[0]
                default = ""
            elif len(parts) == 2:
                section, option = parts
                default = ""
            else:
                section, option, default = parts
            try:
                val = self.menu_config.get_config(section, option)
            except KeyError:
                val = default
            result = result.replace("${" + match + "}", val if val else default)
        return result