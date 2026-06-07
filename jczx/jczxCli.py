import threading
import time
import logging
import re

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from enum import Enum
from logging import Logger, Formatter, Handler, getLevelName
from logging.handlers import RotatingFileHandler
from typing import List, Callable, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime

import cv2
import uiautomator2 as u2

from rich import print
from rich.logging import RichHandler
from rich.console import Console
from pick import Option, Picker
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Footer, Header, Input, Select, Button
from textual.containers import Container, HorizontalGroup, VerticalScroll
from textual.reactive import reactive
from textual import on
from textual.binding import Binding
from textual.events import Mount, Key
from numpy.typing import NDArray

from .CommoneBuilder.CommonBuilder.Android.Adb import Adb, Device
from .CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import Config, TxtConfig
from .CommoneBuilder.CommonBuilder.FileTools.Base.Define import DictConst
from .CommoneBuilder.CommonBuilder.FileTools.File import FileManage
from .translate import Lang, translate
from .configEntity import JczxConfigFileEntity, JczxSectionEntity, SectionType
from .multPick import pick
from .taskManage import TaskManage
from .widgets import (
    DeviceBar,
    TaskCard,
    TaskListPanel,
    TaskSettingsPanel,
    TaskEditorPanel,
    SettingField,
)


LANGUAGE = Lang.ZH_CN

class JCZXGaming(Device):
    # 提供一些内置的方法
    def __init__(self, adb_path: str = None, device_id: str = None, connect_port = 7555, max_workers = 10, log = None, config_dir: str = ""):
        self.log = log if log else Logger(__file__)
        super().__init__(adb_path, device_id, connect_port, max_workers, log=self.log)
        self.fm = FileManage()
        self.task_manage = TaskManage(config_dir, log)
        self.ocr = None
        self._context: dict[str, str] = {}
        self.stop_event = threading.Event()
    
    def set_ocr(self, ocr):
        self.ocr = ocr

    def context_get(self, key: str, default: str = "") -> str:
        return self._context.get(key, default)

    def context_set(self, key: str, value: str) -> None:
        self._context[key] = str(value)
        self.log.debug(f"上下文设置 {key} = {value}")

    def _get_method(self, method_name: str) -> Callable[..., Any]:
        if method_name not in self.__dir__():
            return None
        return getattr(self, method_name)
    
    _EXEC_PLACEHOLDER_PATTERN = re.compile(r"@\{(.+?)\}")
    _CTX_PLACEHOLDER_PATTERN = re.compile(r"%\{(.+?)\}")

    def _resolve_exec_placeholders(self, args: list) -> list:
        resolved = []
        for arg in args:
            result = self._resolve_exec_placeholder(arg)
            resolved.append(result)
        return resolved

    def _resolve_exec_placeholder(self, arg: str) -> str:
        if not isinstance(arg, str):
            return arg
        result = arg
        for match in self._EXEC_PLACEHOLDER_PATTERN.findall(arg):
            exec_result = self.exec(match)
            result = result.replace("@{" + match + "}", str(exec_result) if exec_result is not None else "")
            self.log.debug(f"解析 执行占位符 {match}，值 {exec_result}，原字符串 {arg}")
        for match in self._CTX_PLACEHOLDER_PATTERN.findall(arg):
            val = self.context_get(match)
            result = result.replace("%{" + match + "}", val)
            self.log.debug(f"解析 上下文占位符 {match}，值 {val}，原字符串 {arg}")
        return result

    def exec_func(self, section: Union[JczxSectionEntity, str]):
        entity = section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)
        for _ in range(entity.times):
            if self.stop_event.is_set():
                return None
            time.sleep(entity.pre_sleep)
            method_name = entity.func
            self.log.debug(f"计划预执行 section {section}")
            if method := self._get_method(method_name):
                raw_args = ([entity.target] if entity.target else []) + entity.args
                args = self.task_manage.resolve_placeholders(raw_args, entity.only_key)
                args = self._resolve_exec_placeholders(args)
                self.log.debug(f"开始执行方法 {method.__name__} 参数 {args}")
                if args:
                    result = method(*args)
                else:
                    result = method()
                time.sleep(entity.sleep)
                if next_entities := self.task_manage.get_next(entity):
                    for next_entity in next_entities:
                        result = self.exec(next_entity)
            else:
                self.log.debug(f"方法未查询到 {method_name}")
                raise AttributeError(f"方法未查询到 {method_name}")
        return result

    def exec(self, section: Union[JczxSectionEntity, str]):
        if not section:
            return None
        if self.stop_event.is_set():
            return None
        entity = section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)
        match entity.type:
            case SectionType.TASK.value:
                return self.exec_task(entity)
            case SectionType.FUNC.value:
                return self.exec_func(entity)
            case SectionType.CLICK.value:
                return self.exec_click(entity)
            case SectionType.DYNAMIC.value:
                return self.exec_dynamic(entity)
            case _:
                return None

    def exec_dynamic(self, section: Union[JczxSectionEntity, str]):
        entity = section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)
        for _ in range(entity.times):
            if self.stop_event.is_set():
                return None
            self.log.debug(f"开始动态执行 {entity.get_task_name()} {entity}")
            time.sleep(entity.pre_sleep)
            for key in entity.action:
                if self.stop_event.is_set():
                    return None
                result = self.exec(key)
                result_str = str(result) if result is not None else ""
                if result_str:
                    self.exec(result_str)
            time.sleep(entity.sleep)
            self.log.debug(f"动态执行完成 {entity.get_task_name()}") if entity.get_task_name() else None
        return None

    def exec_click(self, section: Union[JczxSectionEntity, str]):
        entity = section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)
        for _ in range(entity.times):
            if self.stop_event.is_set():
                return None
            startTime = datetime.now()
            result = None
            time.sleep(entity.pre_sleep)
            if entity.pos:
                self.click(*entity.pos)
            else:
                target = entity.target
                target = self._resolve_placeholder(target)
                target = self._resolve_exec_placeholder(target) if target else None
                img = self.task_manage.get_img(target) if target else None
                while True:
                    if self.stop_event.is_set():
                        return None
                    if entity.condition_not:
                        if not self.exec(entity.condition_not):
                            self.log.debug(f"条件 {entity.condition_not} 满足 condition_not，执行 condition_then {entity.condition_then}")
                            for section in entity.condition_then:
                                result = self.exec(section)
                        else:
                            self.log.debug(f"条件 {entity.condition_not} 不满足 condition_not，执行 condition_else {entity.condition_else}")
                            for section in entity.condition_else:
                                result = self.exec(section)
                        break
                    elif entity.condition:
                        if self.exec(entity.condition):
                            self.log.debug(f"条件 {entity.condition} 满足 condition，执行 condition_then {entity.condition_then}")
                            for section in entity.condition_then:
                                result = self.exec(section)
                        else:
                            self.log.debug(f"条件 {entity.condition} 不满足 condition，执行 condition_else {entity.condition_else}")
                            for section in entity.condition_else:
                                result = self.exec(section)
                        break
                    result = self.exec(entity.wait_sec)
                    start = time.monotonic()
                    self.log.debug(f"匹配资源 {target}")
                    if img is not None:
                        if result := self.clickResource(img, per = entity.per, index = entity.index):
                            self.log.debug(f"匹配并点击资源 {target} 耗时 {time.monotonic() - start:.2f}")
                            self.log.info(f"执行点击 {entity.get_task_name()}") if entity.get_task_name() else None
                            self.log.debug(f"匹配资源耗时 {time.monotonic() - start:.2f}")
                            break
                        else: 
                            self.log.debug(f"未匹配到资源 {target}，耗时 {time.monotonic() - start:.2f}")
                    runTime = (datetime.now() - startTime).seconds
                    if runTime >= entity.max_wait:
                        self.log.debug(f"最大等待时间 {entity.max_wait}s 结束, 未匹配到资源 {target}")
                        if entity.break_point == "on":
                            self.log.debug(f"未执行，跳出执行链")
                            time.sleep(entity.sleep)
                            return None
                        break
            time.sleep(entity.sleep)
            entities = self.task_manage.get_next(entity)
            if entities:
                self.log.debug(f"获取下一执行链 {entities}")
            for i in entities:
                result = self.exec(i)
        return result

    def _resolve_placeholder(self, key):
        return self.task_manage._resolve_placeholder(key) if key else None

    def parse_placeholder(self, key: str):
        return self._resolve_placeholder("${"+ key +"}")

    def get_resources_target(self, target: str):
        rel_path = "\\".join(["resources"] + target.split("\\"))
        return str(self.fm.get_obj_relative_path(rel_path, self))

    def exec_task_raw(self, section: Union[JczxSectionEntity, str]):
        self._context.clear()
        try:
            return self.exec_task(section)
        finally:
            self._context.clear()

    def exec_task(self, section: Union[JczxSectionEntity, str]):
        entity = section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)
        for _ in range(entity.times):
            if self.stop_event.is_set():
                return None
            result = None
            next_entities = self.task_manage.get_next(entity)
            self.log.info(f"开始执行任务 {entity.get_task_name()}") if entity.get_task_name() else None
            time.sleep(entity.pre_sleep)
            for i in next_entities:
                if self.stop_event.is_set():
                    self.log.info("任务已被用户停止")
                    return None
                self.log.debug(f"开始执行实体 {i.get_task_name()} {i}")
                result = self.exec(i)
            time.sleep(entity.sleep)
            self.log.info(f"任务执行完毕 {entity.get_task_name()}") if entity.get_task_name() else None
        return result
    
    def in_location(self, target: str, per: float = 0.8):
        list_pos = self.findImageCenterLocations(self.task_manage.get_img(target), per = float(per))
        self.log.debug(f"查找资源 {target} 位置 {list_pos}")
        return bool(list_pos)
        
    def start_game(self, app: str, activity: str):
        if not self.get_app_pid(app):
            self.launch_app(activity)
    
    def save_screenshot(self, dir: str, name: str):
        path = self.fm.join(dir, f"{name}.png")
        array: NDArray = self.screenshot()
        cv2.imwrite(path, array)
        self.log.debug(f"截图已保存到 {path}")
        
    def click_proportion(self, w_pro: int, h_pro: int):
        width, height = self.getScreenSize()
        self.click(width // int(w_pro), height // int(h_pro))
    
    def drag_drop_proportion(self, w1_pro: int, h1_pro: int, w2_pro: int, h2_pro: int, duration: int = 200):
        width, height = self.getScreenSize()
        self.dragAndDrop(width // int(w1_pro), height // int(h1_pro), width // int(w2_pro), height // int(h2_pro), int(duration))

    def swipe_proportion(self, w1_pro: int, h1_pro: int, w2_pro: int, h2_pro: int, duration: int = 200):
        width, height = self.getScreenSize()
        self.swipe(width // int(w1_pro), height // int(h1_pro), width // int(w2_pro), height // int(h2_pro), int(duration))

    def string_concat(self, *args):
        return "".join(args)

class RichLogHandler(Handler):
    """StreamHandler that only auto-scrolls to bottom when the RichLog is already at the end."""

    def __init__(self, rich_log):
        super().__init__()
        self.rich_log = rich_log
        self.terminator = ""

    def emit(self, record):
        try:
            msg = self.format(record)
            at_bottom = getattr(self.rich_log, 'scroll_y', 0) >= getattr(self.rich_log, 'max_scroll_y', 0)
            self.rich_log.auto_scroll = at_bottom
            self.rich_log.write(msg)
        except Exception:
            self.handleError(record)


class JczxCli:
    def __init__(self):
        self.fm = FileManage()  # 文件管理
        self.config: TxtConfig = Config(self.fm.get_obj_relative_path("Config/Config.txt", self)).Config  # 读取主配置文件
        # 初始化日志
        self.logger = Logger(self.__class__.__name__)
        # 初始化线程池
        self.executor = ThreadPoolExecutor(
            max_workers=int(self.config.get_config(opt="thread.max_workers"))
        )
        self.device = None  # 设备
        self.adb: JCZXGaming = None
        self.task_manage = TaskManage("")
        self.ocr = None
        self.rich_log = RichLog(id="console", highlight=True, auto_scroll=False)
        self._running_future: Optional[Future] = None
        self._running_task_id: Optional[str] = None
        self._settings_task_id: Optional[str] = None
        self._init_logger()

    @staticmethod
    def error_exception(func):
        def wrapper(self: "JczxCli", *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                self.logger.error(f"执行失败 {e.__traceback__.tb_lineno} {e}", stack_info=True)
                self.logger.debug(f"本地参数：{locals()}")
        return wrapper

    @error_exception
    def _init_something(self):
        self.thread_pool_run(self._init_device, self._init_ocr)
        if self.device:
            self.device.set_ocr(self.ocr)

    def thread_pool_run(self, *args: Callable):
        futures = [self.executor.submit(i) for i in args]
        self._thread_pool_run(*futures)

    def _thread_pool_run(self, *args: Future):
        completed_list = as_completed(args)
        for future in completed_list:
            future.result()

    def _init_logger(self):
        # 文件日志
        mode = self.config.get_config(opt="logging.file.mode")
        filehander = RotatingFileHandler(
            f"{self.__class__.__name__}.log",
            mode=mode,
            maxBytes=int(self.config.get_config(opt="logging.file.size")) * 1024 if not mode.lower().startswith("w") else 0,
            encoding="utf-8",
        )
        filehander.setFormatter(
            Formatter(self.config.get_config(opt="logging.file.format"), "%H:%M:%S")
        )
        filehander.setLevel(int(self.config.get_config(opt="logging.file.level")))
        # 控制台日志
        console_hander = RichLogHandler(self.rich_log)
        console_hander.setFormatter(
            Formatter(self.config.get_config(opt="logging.format"), "%H:%M:%S")
        )
        console_hander.setLevel(int(self.config.get_config(opt="logging.level")))
        console_hander.terminator = ""
        self.logger.setLevel(console_hander.level)
        self.logger.addHandler(filehander)
        self.logger.addHandler(console_hander)
        self.logger.info("===========日志初始化完成===========")
        self.logger.info(f"日志等级 {getLevelName(self.logger.level)}")

    def _init_device(self):
        adb_path = self.config.get_config(opt="adb.path")
        self.logger.debug(f"ADB路径 {adb_path}")
        self.logger.info("开始加载ADB")
        try:
            if self.adb:
                ...
            elif self.fm.isfile(adb_path):
                self.adb = JCZXGaming(adb_path, log = self.logger)
            else:
                self.adb = JCZXGaming(log = self.logger)
                self.config.set_config(opt="adb.path", val=self.adb.adb_path)
                self.config.save()
        except IndexError:
            self.logger.info("ADB当前无可连接设备")
            return
        if self.adb.get_device_names():
            self.device = self.adb.get_device()
        else:
            self.logger.info("ADB当前无可连接设备")
            return
        self.logger.info(f"ADB加载完成 {self.device.device_id}")
        if self.device.u2_device:
            self.logger.debug(f"截图方式: U2 Screenshot")
        else:
            self.logger.debug(f"截图方式: ADB Screenshot")
        self.logger.debug(f"设备分辨率 {self.device.width}x{self.device.height}")

    def _init_ocr(self):
        if self.ocr:
            return
        self.logger.info("初始化OCR...")
        from .CommoneBuilder.CommonBuilder.Ocr.Ocr import OCR
        self.ocr = OCR(
            use_angle_cls = False,
            lang = 'ch',
            use_gpu = False,
            enable_mkldnn = True,
            show_log = False,
            det_model_dir = self.fm.get_obj_relative_path('OCR\ch_PP-OCRv4_det_infer', self).__str__(),
            rec_model_dir = self.fm.get_obj_relative_path('OCR\ch_PP-OCRv4_rec_infer', self).__str__(),
            cls_model_dir = self.fm.get_obj_relative_path('OCR\ch_ppocr_mobile_v2.0_cls_infer', self).__str__()
        )
        self.logger.info("OCR初始化完成")

class JczxTUI(App, JczxCli):
    BINDINGS = [
        Binding("q", "quit", translate("退出程序", LANGUAGE)),
        Binding("ctrl+l", "clear_log", translate("清空日志", LANGUAGE)),
    ]
    CSS_PATH = "Css\main.tcss"

    def __init__(self):
        super().__init__()
        JczxCli.__init__(self)

    def compose(self) -> ComposeResult:
        devices = self.adb.get_device_names() if self.adb else []
        current_device = self.device.device_id if self.device else ""
        yield Header(show_clock=True)
        yield DeviceBar(
            devices=devices,
            current_device=current_device,
            current_port=self.config.get_config(opt="adb.port") or "7555",
        )
        with Container(id="app-grid"):
            yield self.rich_log
            with VerticalScroll(id="right-panels"):
                yield TaskListPanel(id="task-list-panel")
                yield TaskSettingsPanel(id="task-settings-panel")
                yield TaskEditorPanel(
                    task_list_names=self._get_editor_task_options(),
                    id="task-editor-panel",
                )
        yield Footer(show_command_palette=False)

    def action_clear_log(self) -> None:
        self.rich_log.clear()
        self.logger.debug("日志控制台已清空")

    def on_mount(self) -> None:
        self._populate_task_list()
        self.run_worker(self._init_after_mount, thread=True)

    def _init_after_mount(self) -> None:
        """在后台线程执行 初始化，完成后回主线程刷新 UI."""
        self._init_something()
        self.call_from_thread(self._update_device_bar)

    def _update_device_bar(self) -> None:
        """主线程回调：用初始化后的设备列表刷新顶部栏."""
        if self.adb:
            devices = self.adb.get_device_names()
            current = self.device.device_id if self.device else ""
            self.query_one(DeviceBar).set_devices(devices, current)

    # ── helpers ──────────────────────────────────────────

    def _get_editor_task_names(self) -> list[str]:
        """返回任务 key 列表（英文标识符，用于组件 id）."""
        return self.task_manage.get_task_names()

    def _get_editor_task_options(self) -> list[tuple[str, str]]:
        """返回 [(显示名称, key), ...] 用于下拉框."""
        return [
            (self.task_manage.get_task_display_name(k), k)
            for k in self._get_editor_task_names()
        ]

    def _populate_task_list(self) -> None:
        """Fill the task-list panel from config."""
        panel = self.query_one("#task-list-panel", TaskListPanel)
        panel.clear_tasks()
        for key in self._get_editor_task_names():
            panel.add_task(key, self.task_manage.get_task_display_name(key))

    # ── DeviceBar handlers ───────────────────────────────

    def on_device_bar_saved(self, event: DeviceBar.Saved) -> None:
        self.logger.info(
            "设备配置已保存: device=%s, port=%s", event.device, event.port
        )
        self.config.set_config(opt="adb.port", val=event.port)
        self.config.save()
        self.logger.info("配置已保存到文件")

    def on_device_bar_refresh_pressed(self, event: DeviceBar.RefreshPressed) -> None:
        self.logger.info("正在刷新设备列表...")
        self.run_worker(self._refresh_devices, thread=True)

    def on_device_bar_reload_pressed(self, event: DeviceBar.ReloadPressed) -> None:
        self.logger.info("正在重载配置文件...")
        self._reload_configs()
        self._refresh_all_panels()
        self.logger.info("配置文件重载完成")

    def _reload_configs(self) -> None:
        config_path = self.fm.get_obj_relative_path("Config/Config.txt", self)
        self.config = Config(config_path).Config
        self.task_manage.refresh_config()
        if self.device:
            self.device.task_manage.refresh_config()

    def _refresh_all_panels(self) -> None:
        self._populate_task_list()
        editor_panel = self.query_one("#task-editor-panel", TaskEditorPanel)
        editor_panel.set_task_lists(self._get_editor_task_options())

    def _refresh_devices(self) -> None:
        self._init_device()
        self.call_from_thread(self._update_device_bar)
        self.call_from_thread(
            lambda: self.logger.info("设备列表已刷新")
        )

    # ── TaskCard handlers ────────────────────────────────

    def on_task_card_toggle_pressed(self, event: TaskCard.TogglePressed) -> None:
        if event.running:
            panel = self.query_one("#task-list-panel", TaskListPanel)
            for card in panel.body.query(TaskCard):
                if card._task_id != event.task_id and card.toggle.state:
                    card.reset_toggle()
                    self._stop_running_task()
            if not self._start_task(event.task_id):
                for card in panel.body.query(TaskCard):
                    if card._task_id == event.task_id:
                        card.reset_toggle()
        else:
            self._stop_running_task()

    def _start_task(self, task_id: str) -> bool:
        if not self.device:
            self.logger.warning("设备未就绪，无法启动任务")
            return False
        if not self.ocr:
            self.logger.warning("OCR 未初始化完成，无法启动任务")
            return False
        entity = self.task_manage.get_task(task_id)
        if not entity:
            self.logger.error("任务实体不存在: %s", task_id)
            return False
        self.device.stop_event.clear()
        self._running_task_id = task_id
        self.logger.info("任务启动: %s", task_id)
        self._running_future = self.executor.submit(self._run_task, entity, task_id)
        return True

    def _stop_running_task(self) -> None:
        if self.device:
            self.device.stop_event.set()
        if self._running_future:
            self._running_future.cancel()
            self._running_future = None
        self._running_task_id = None
        self.logger.info("任务已停止")

    def _run_task(self, entity: JczxSectionEntity, task_id: str) -> None:
        try:
            self.device.exec_task_raw(entity)
        except Exception as e:
            self.logger.error("任务执行异常: %s", e)
        finally:
            self.call_from_thread(self._on_task_finished, task_id)

    def _on_task_finished(self, task_id: str) -> None:
        if self._running_task_id != task_id:
            return
        panel = self.query_one("#task-list-panel", TaskListPanel)
        for card in panel.body.query(TaskCard):
            if card._task_id == task_id:
                card.reset_toggle()
        self._running_future = None
        self._running_task_id = None

    def on_task_card_settings_pressed(self, event: TaskCard.SettingsPressed) -> None:
        task_id = event.task_id
        self._settings_task_id = task_id
        self.logger.debug("打开任务设置: %s", task_id)
        panel = self.query_one("#task-settings-panel", TaskSettingsPanel)
        setting_entities = self.task_manage.get_task_setting_entities(task_id)
        if not setting_entities:
            self.logger.debug("任务 %s 没有定义设置项，显示空面板", task_id)
            panel.set_fields([])
            return
        saved_values = self.task_manage.get_task_values(task_id)
        fields: list[SettingField] = []
        for se in setting_entities:
            val = saved_values.get(se.name, se.default or "")
            sub_values: dict[str, bool] = {}
            if se.setting_type == "multi_select_switch":
                sub_str = saved_values.get(f"{se.name}__sub", "")
                sub_set = set(sub_str.split(",")) if sub_str else set()
                for opt in (se.options or []):
                    sub_values[opt] = opt in sub_set
            fields.append(SettingField(
                name=se.name or "",
                label=se.label or se.name or "",
                type=se.setting_type or "input",
                value=val,
                options=se.options or [],
                switch_label=se.switch_label or "",
                switch_values=sub_values,
                min=se.min,
                max=se.max,
                desc=se.desc or "",
            ))
        panel.set_fields(fields)

    # ── TaskSettingsPanel handlers ───────────────────────

    def on_task_settings_panel_saved(self, event: TaskSettingsPanel.Saved) -> None:
        if not self._settings_task_id:
            self.logger.warning("没有活跃的任务设置面板，忽略保存")
            return
        self.task_manage.save_task_values(self._settings_task_id, event.values)
        self.logger.info("任务设置已保存: task=%s, values=%s",
                         self._settings_task_id, event.values)
        if self.device is not None:
            self.device.task_manage.menu_config = self.task_manage.menu_config
            self.logger.debug("已同步配置到设备端")

    # ── TaskEditorPanel handlers ─────────────────────────

    def on_task_editor_panel_run_requested(self, event: TaskEditorPanel.RunRequested) -> None:
        if event.running:
            self.logger.info("开始执行任务列表: %s", event.task_list_name)
        else:
            self.logger.info("停止执行任务列表: %s", event.task_list_name)
