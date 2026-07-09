import os
import threading
import time
import re

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from logging import Logger, Formatter, Handler, getLevelName
from logging.handlers import RotatingFileHandler
from typing import Callable, Any, Optional, Union, get_type_hints
from datetime import datetime

import cv2
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Footer, Header
from textual.containers import Container, VerticalScroll
from textual.binding import Binding
from numpy.typing import NDArray

from .CommoneBuilder.CommonBuilder.Android.Adb import Device, MatchTemplete
from .CommoneBuilder.CommonBuilder.FileTools.ConfigUtils import Config, TxtConfig
from .CommoneBuilder.CommonBuilder.FileTools.File import FileManage
from .CommoneBuilder.CommonBuilder.Ocr.typing import OCR
from .debug import DebugRecorder
from .translate import Lang, translate
from .configEntity import JczxSectionEntity, SectionType
from .taskManage import TaskManage
from .widgets import (
    DeviceBar,
    TaskCard,
    TaskListPanel,
    TaskSettingsPanel,
    QueuePanel,
    QueueEditorScreen,
    SettingField,
)


LANGUAGE = Lang.ZH_CN

class ScreenshotCache:
    """截图缓存，TTL + 脏标记，避免同帧重复截图。"""

    def __init__(self, screenshot_fn, ttl_ms=200, log=None):
        self._capture = screenshot_fn
        self._ttl_ms = ttl_ms
        self._log = log
        self._gray: NDArray = None
        self._color: NDArray = None
        self._timestamp: float = 0.0
        self._dirty: bool = True

    def screenshot(self):
        if self._stale():
            self._refresh()
        return self._color

    def gray_screenshot(self):
        if self._stale():
            self._refresh()
        return self._gray

    def invalidate(self):
        self._dirty = True

    def set_ttl(self, ttl_ms: float):
        if self._log and self._ttl_ms != ttl_ms:
            self._log.debug(f"截图缓存 TTL: {self._ttl_ms}ms → {ttl_ms}ms")
        self._ttl_ms = ttl_ms

    def _refresh(self):
        self._color = self._capture()
        self._gray = cv2.cvtColor(self._color, cv2.COLOR_BGR2GRAY)
        self._timestamp = time.monotonic()
        self._dirty = False
        if self._log:
            self._log.debug(f"截图缓存已刷新")

    def _stale(self):
        return self._dirty or (self._ttl_ms > 0 and (time.monotonic() - self._timestamp) * 1000 > self._ttl_ms)

class TaskCancelledError(Exception):
    pass


class CancellationToken:
    def __init__(self):
        self._event = threading.Event()

    def sleep(self, seconds: float) -> None:
        if self._event.wait(timeout=seconds):
            raise TaskCancelledError()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise TaskCancelledError()


class TaskExecutionManager:
    def __init__(self):
        self._token = CancellationToken()
        self._task_id: str | None = None

    @property
    def token(self) -> CancellationToken:
        return self._token

    @property
    def task_id(self) -> str | None:
        return self._task_id

    def is_running(self) -> bool:
        return self._task_id is not None and not self._token.is_cancelled()

    def start(self, task_id: str) -> None:
        self._token.reset()
        self._task_id = task_id

    def stop(self) -> None:
        if not self._token.is_cancelled():
            self._token.cancel()

    def reset(self) -> None:
        self._token.reset()
        self._task_id = None

class PlaceholderResolver:
    _CONFIG_PATTERN = re.compile(r"\$\{(.+?)\}")
    _EXEC_PATTERN = re.compile(r"@\{(.+?)\}")
    _CTX_PATTERN = re.compile(r"%\{(.+?)\}")
    _CONDITION_PATTERN = re.compile(r"^&\{(.+)\}$")
    _LOG_CONDITION_PATTERN = re.compile(r"&\{(.+?)\}")

    def __init__(self, gaming):
        self._gaming = gaming

    def resolve(self, text: str, after_key: str) -> str:
        if not text or not isinstance(text, str):
            return text
        result = self._resolve_config(text, after_key)
        result = self._resolve_exec(result)
        result = self._resolve_context(result)
        result = self._resolve_condition(result, after_key)
        return result

    def resolve_list(self, items: list, after_key: str) -> list:
        return [self.resolve(i, after_key) if isinstance(i, str) else i for i in items]

    def _resolve_config(self, text: str, after_key: str) -> str:
        result = text
        for m in self._CONFIG_PATTERN.findall(text):
            val = self._gaming.task_manage._resolve_placeholder("${" + m + "}", after_key)
            result = result.replace("${" + m + "}", str(val))
        return result

    def _resolve_exec(self, text: str) -> str:
        result = text
        for m in self._EXEC_PATTERN.findall(result):
            val = self._gaming.exec(m)
            result = result.replace("@{" + m + "}", str(val) if val is not None else "")
        return result

    def _resolve_context(self, text: str) -> str:
        result = text
        for m in self._CTX_PATTERN.findall(result):
            if self._is_context_expr(m):
                val = self._eval_context_expr(m)
            else:
                val = self._gaming._context.get(m, "")
            result = result.replace("%{" + m + "}", str(val))
        return result

    def _resolve_condition(self, text: str, after_key: str) -> str:
        if self._CONDITION_PATTERN.match(text):
            return str(self._eval_condition_expr(
                self._CONDITION_PATTERN.match(text).group(1), after_key))
        result = text
        for m in self._LOG_CONDITION_PATTERN.findall(text):
            val = self._eval_condition_expr(m, after_key)
            result = result.replace("&{" + m + "}", str(val))
        return result

    def evaluate_condition(self, condition: str, after_key: str) -> str:
        if not condition:
            return "False"
        match = self._CONDITION_PATTERN.match(condition)
        if match:
            return str(self._eval_condition_expr(match.group(1), after_key))
        return str(bool(self._gaming.exec(condition)))

    def format_condition(self, condition: str, after_key: str, result: str = None) -> str:
        if not condition:
            return "None → False"
        match = self._CONDITION_PATTERN.match(condition)
        if match:
            expr = match.group(1)
            resolved = self._resolve_config(expr, after_key)
            resolved = self._resolve_context(resolved)
            if result is None:
                result = str(self._eval_condition_expr(expr, after_key))
            return f"{condition} → &{{{resolved}}} → {result}"
        if result is None:
            result = str(bool(self._gaming.exec(condition)))
        return f"{condition} → {result}"

    def _eval_condition_expr(self, expr: str, after_key: str) -> bool:
        tokens = self._tokenize(expr)
        return self._parse_expression(tokens, condition_mode=True, after_key=after_key)

    def _eval_context_expr(self, expr: str):
        tokens = self._tokenize(expr)
        return self._parse_expression(tokens, condition_mode=False)

    def _parse_expression(self, tokens: list, *, condition_mode: bool, after_key: str = ""):
        pos = [0]

        def parse_or():
            left = parse_and()
            while pos[0] < len(tokens) and tokens[pos[0]] == "|":
                pos[0] += 1
                left = bool(left) or bool(parse_and())
            return left

        def parse_and():
            left = parse_cmp()
            while pos[0] < len(tokens) and tokens[pos[0]] == "&":
                pos[0] += 1
                left = bool(left) and bool(parse_cmp())
            return left

        def parse_cmp():
            left = parse_primary()
            if pos[0] < len(tokens) and tokens[pos[0]] in (">=", "<=", ">", "<", "==", "!="):
                op_token = tokens[pos[0]]
                pos[0] += 1
                right = parse_primary()
                if op_token == ">=": return float(left) >= float(right)
                if op_token == "<=": return float(left) <= float(right)
                if op_token == ">":  return float(left) > float(right)
                if op_token == "<":  return float(left) < float(right)
                if op_token == "==": return str(left) == str(right)
                if op_token == "!=": return str(left) != str(right)
            return left

        def parse_primary():
            if pos[0] >= len(tokens):
                return False
            token = tokens[pos[0]]
            pos[0] += 1
            if token == "(":
                result = parse_or()
                if pos[0] < len(tokens) and tokens[pos[0]] == ")":
                    pos[0] += 1
                return result
            try:
                if "." in token:
                    return float(token)
                return int(token)
            except (ValueError, TypeError):
                pass
            if condition_mode:
                if self._CTX_PATTERN.match(token):
                    return self._gaming._context.get(
                        self._CTX_PATTERN.match(token).group(1), "")
                if self._EXEC_PATTERN.match(token):
                    return self._gaming.exec(
                        self._EXEC_PATTERN.match(token).group(1))
                if self._CONFIG_PATTERN.match(token):
                    return self._gaming.task_manage._resolve_placeholder(token, after_key)
                return self._gaming.exec(token)
            else:
                if self._CTX_PATTERN.match(token):
                    return self._gaming._context.get(
                        self._CTX_PATTERN.match(token).group(1), "")
                return self._gaming._context.get(token, "")

        result = parse_or()
        return bool(result) if result is not None else False

    @staticmethod
    def _tokenize(expr: str) -> list:
        tokens = []
        i = 0
        n = len(expr)
        while i < n:
            c = expr[i]
            if c.isspace():
                i += 1
                continue
            if c in "()":
                tokens.append(c)
                i += 1
            elif c == "&":
                tokens.append("&")
                i += 1
            elif c == "|":
                tokens.append("|")
                i += 1
            elif expr[i : i + 2] in (">=", "<=", "!=", "=="):
                tokens.append(expr[i : i + 2])
                i += 2
            elif c in "><":
                tokens.append(c)
                i += 1
            else:
                j = i
                while j < n and not expr[j].isspace() and expr[j] not in "()&|><=!":
                    j += 1
                tokens.append(expr[i:j])
                i = j
        return tokens

    @staticmethod
    def _is_context_expr(expr: str) -> bool:
        if not expr:
            return False
        return any(op in expr for op in ("&", "|", ">=", "<=", ">", "<", "==", "!="))

class JCZXGaming(Device):
    # 提供一些内置的方法
    def __init__(self, adb_path: str = None, device_id: str = None, connect_port = 7555, max_workers = 10, log = None, config_dir: str = ""):
        self.log = log if log else Logger(__file__)
        super().__init__(adb_path, device_id, connect_port, max_workers, log=self.log)
        self.fm = FileManage()
        self.task_manage = TaskManage(config_dir, log)
        self.ocr: OCR = None
        self._context: dict[str, str] = {}
        self._exec_mgr = TaskExecutionManager()
        self._resolver = PlaceholderResolver(self)
        self._screen_cache = ScreenshotCache(
            screenshot_fn=lambda: Device.screenshot(self),
            ttl_ms=500,
            log=self.log,
        )
        self._recorder: Optional[DebugRecorder] = None

    def screenshot(self):
        img = self._screen_cache.screenshot()
        if self._recorder:
            self._recorder.on_step(img)
        return img

    def grayScreenshot(self, cutPoints=None):
        gray = self._screen_cache.gray_screenshot()
        if self._recorder:
            self._recorder.on_step(self._screen_cache._color)
        if cutPoints:
            return self.cutScreenshot(gray, cutPoints)
        return gray

    def click(self, x, y):
        if self._recorder:
            self._recorder.on_click(self.screenshot(), x, y)
        super().click(x, y)
        self._screen_cache.invalidate()

    def swipe(self, x1, y1, x2, y2, duration=200):
        if self._recorder:
            self._recorder.on_swipe(self.screenshot(), x1, y1, x2, y2, "滑动")
        super().swipe(x1, y1, x2, y2, duration)
        self._screen_cache.invalidate()

    def dragAndDrop(self, x1, y1, x2, y2, duration=200):
        if self._recorder:
            self._recorder.on_swipe(self.screenshot(), x1, y1, x2, y2, "拖动")
        super().dragAndDrop(x1, y1, x2, y2, duration)
        self._screen_cache.invalidate()
    
    def set_ocr(self, ocr):
        self.ocr = ocr

    def context_get(self, key: str, default = ""):
        return self._context.get(key, default)

    def context_set(self, key: str, value) -> None:
        self._context[key] = value
        self.log.debug(f"上下文设置 {key} = {value}")

    def parse_placeholder(self, key: str):
        return self._resolver._resolve_config("${" + key + "}", "")

    def context_print(self):
        """打印当前全部上下文变量。"""
        if not self._context:
            self.log.debug("上下文为空")
            return
        self.log.debug(f"上下文变量 ({len(self._context)})：")
        for k, v in self._context.items():
            self.log.debug(f"  {k} = {v} ({type(v).__name__})")

    def _get_method(self, method_name: str) -> Callable[..., Any]:
        if method_name not in self.__dir__():
            return None
        return getattr(self, method_name)

    def exec_func(self, section: Union[JczxSectionEntity, str]):
        """执行 func 类型实体：调用 JCZXGaming 上的方法，支持 times / pre_sleep / sleep / action 链"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            if method := self._get_method(e.func):
                raw_args = ([e.target] if e.target else []) + e.args
                args = self._resolver.resolve_list(raw_args, e.only_key)
                return method(*args) if args else method()
            raise AttributeError(f"方法未查询到 {e.func}")
        return self._exec_entity(entity, _on_exec)

    def exec_match(self, section: Union[JczxSectionEntity, str]):
        """执行 match 类型实体：纯模板匹配不点击，返回 MatchTemplete 对象供其他实体使用。
        action 字段为变换操作列表（非执行链），如 down-0.5、reW-1.0 等。"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            target = e.target
            if not target:
                self.log.debug("match 类型缺少 target")
                return None
            img = self.task_manage.get_img(target)
            if img is None:
                self.log.debug(f"match 图片未找到: {target}")
                return None
            result = self.findImageDetail(img, per=e.per)
            if not result or not result.matched:
                self.log.debug(f"match 未匹配到: {target}")
                return None
            if self._recorder:
                self._recorder.on_match(self.screenshot(), result)
            for action in e.action:
                result = self._transform_match(result, action)
            return result
        return self._exec_entity(entity, _on_exec, testFor=True, action_chain=False)

    @staticmethod
    def _transform_match(mt: MatchTemplete, action: str):
        """对 MatchTemplete 结果应用变换操作（如 down-1.5、reW-2.0 等）。"""
        return mt.transform(action)

    def exec_ocr(self, section: Union[JczxSectionEntity, str]):
        """执行 ocr 类型实体：匹配图像区域 → 裁剪 → OCR 识别 → 返回文本。"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            mt = None
            result = ""
            if e.match:
                mt = self.exec(e.match)
                if mt is not None and getattr(mt, "matched", False):
                    result = self._ocr_match_region(mt)
            elif e.target:
                target = self._resolver.resolve(e.target, e.only_key)
                img = self.task_manage.get_img(target) if target else None
                if img is not None:
                    mt = self.findImageDetail(img, per=e.per)
                    if mt and mt.matched and mt.matchTempletePointRange:
                        result = self._ocr_match_region(mt)
                        self.log.info(f"OCR 识别 {e.get_task_name()}: {result}") if e.get_task_name() else None
            if not result and e.raise_value:
                result = self._resolver.resolve(e.raise_value, e.only_key)
                self.log.debug(f"OCR 识别失败，使用 raise_value: {result}")
            if result and self._recorder:
                self._recorder.on_ocr(self.screenshot(), mt, result)
            return result
        return self._exec_entity(entity, _on_exec, testFor=True)

    def exec_dynamic(self, section: Union[JczxSectionEntity, str]):
        """执行 dynamic 类型实体：依次执行 action 中的 entity key，并将每个返回值（转 str）再次作为 entity key 执行。
        不支持 action 链（get_next 不会被调用）。"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            self.log.debug(f"开始动态执行 {e.get_task_name()} {e}")
            for key in e.action:
                self._exec_mgr.token.check()
                result = self.exec(key)
                result_str = str(result) if result is not None else ""
                if result_str:
                    self.exec(result_str)
            self.log.debug(f"动态执行完成 {e.get_task_name()}") if e.get_task_name() else None
            return None
        return self._exec_entity(entity, _on_exec, action_chain=False)

    def exec_context(self, section: Union[JczxSectionEntity, str]):
        """执行 context 类型实体：读取上下文变量 → 按 action 链运算 → 输出结果。"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            result = None
            if e.context_get:
                exists = e.context_get in self._context
                default_type = e.context_default_type or e.context_type
                value = self._context[e.context_get] if exists else self._convert_value(e.context_default, default_type)
                self.log.debug(f"上下文读取 {e.context_get} = {value} (存在: {exists}, 类型: {type(value).__name__})")
                actions = self._resolver.resolve_list(e.action, e.only_key)
                self.log.debug(f"上下文运算链: {e.action} → {actions}")
                for op in actions:
                    prev = value
                    value = self._apply_context_op(value, op)
                    self.log.debug(f"上下文运算: {prev} {op} → {value}")
                result = value
                if e.context_key:
                    out = self._convert_output(result, e.context_type)
                    self.context_set(e.context_key, out)
            return result
        return self._exec_entity(entity, _on_exec, testFor=True, action_chain=False)

    def exec_condition(self, section: Union[JczxSectionEntity, str]):
        """执行 condition 类型实体：评估 condition / condition_not，按结果执行 then / else 分支。"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            result = None
            if e.condition_not:
                cond_result = self._resolver.evaluate_condition(e.condition_not, e.only_key)
                if cond_result != "True":
                    self.log.debug(f"条件 {self._resolver.format_condition(e.condition_not, e.only_key, cond_result)} 满足 condition_not，执行 condition_then {e.condition_then}")
                    for s in e.condition_then:
                        result = self.exec(s)
                else:
                    self.log.debug(f"条件 {self._resolver.format_condition(e.condition_not, e.only_key, cond_result)} 不满足 condition_not，执行 condition_else {e.condition_else}")
                    for s in e.condition_else:
                        result = self.exec(s)
            elif e.condition:
                cond_result = self._resolver.evaluate_condition(e.condition, e.only_key)
                if cond_result == "True":
                    self.log.debug(f"条件 {self._resolver.format_condition(e.condition, e.only_key, cond_result)} 满足 condition，执行 condition_then {e.condition_then}")
                    for s in e.condition_then:
                        result = self.exec(s)
                else:
                    self.log.debug(f"条件 {self._resolver.format_condition(e.condition, e.only_key, cond_result)} 不满足 condition，执行 condition_else {e.condition_else}")
                    for s in e.condition_else:
                        result = self.exec(s)
            return result
        return self._exec_entity(entity, _on_exec, testFor=True)

    def exec_click(self, section: Union[JczxSectionEntity, str]):
        """执行 click 类型实体：testFor_before 门控 → pos/match/target 点击 → action 链 → testFor_after 复检。
        点击优先级：pos > match > target（模板匹配循环）。"""
        entity = self._get_entity(section)
        def _on_exec(e: JczxSectionEntity):
            startTime = datetime.now()
            result = None
            if e.pos:
                self.click(*e.pos)
            elif e.match:
                mt = self.exec(e.match)
                if mt is not None and getattr(mt, 'matchTempleteCenterPoints', None):
                    idx = e.target_index
                    pt = mt.matchTempleteCenterPoints[idx] if idx < len(mt.matchTempleteCenterPoints) else mt.matchTempleteCenterPoints[0]
                    self.click(*pt)
                    result = mt
            else:
                target = self._resolver.resolve(e.target, e.only_key) if e.target else None
                img = self.task_manage.get_img(target) if target else None
                while True:
                    self._exec_mgr.token.check()
                    if e.condition_not:
                        cond_result = self._resolver.evaluate_condition(e.condition_not, e.only_key)
                        if cond_result != "True":
                            self.log.debug(f"条件 {self._resolver.format_condition(e.condition_not, e.only_key, cond_result)} 满足 condition_not，执行 condition_then {e.condition_then}")
                            for s in e.condition_then: result = self.exec(s)
                        else:
                            self.log.debug(f"条件 {self._resolver.format_condition(e.condition_not, e.only_key, cond_result)} 不满足 condition_not，执行 condition_else {e.condition_else}")
                            for s in e.condition_else: result = self.exec(s)
                        break
                    elif e.condition:
                        cond_result = self._resolver.evaluate_condition(e.condition, e.only_key)
                        if cond_result == "True":
                            self.log.debug(f"条件 {self._resolver.format_condition(e.condition, e.only_key, cond_result)} 满足 condition，执行 condition_then {e.condition_then}")
                            for s in e.condition_then: result = self.exec(s)
                        else:
                            self.log.debug(f"条件 {self._resolver.format_condition(e.condition, e.only_key, cond_result)} 不满足 condition，执行 condition_else {e.condition_else}")
                            for s in e.condition_else: result = self.exec(s)
                        break
                    result = self.exec(e.wait_sec)
                    self.log.debug(f"匹配资源 {target}")
                    if img is not None and (result := self.clickResource(img, per=e.per, index=e.index)):
                        self.log.debug(f"匹配并点击资源 {target}")
                        self.log.info(f"执行点击 {e.get_task_name()}") if e.get_task_name() else None
                        break
                    runTime = (datetime.now() - startTime).seconds
                    if runTime >= e.max_wait:
                        self.log.debug(f"最大等待时间 {e.max_wait}s 结束, 未匹配到资源 {target}")
                        if e.break_point == "on":
                            self._exec_mgr.token.sleep(e.sleep)
                            return None
                        break
            return result
        return self._exec_entity(entity, _on_exec, testFor=True, default_max_wait=entity.max_wait)

    def exec_task(self, section: Union[JczxSectionEntity, str]):
        """执行 task 类型实体：遍历 action 链，依次执行子实体。"""
        entity = self._get_entity(section)
        is_task = entity.view == "on"
        prefix = "任务" if is_task else "过程"
        log_fn = self.log.info if is_task else self.log.debug
        def _on_exec(e: JczxSectionEntity):
            result = None
            next_entities = self.task_manage.get_next(e)
            log_fn(f"开始执行{prefix} {e.get_task_name()}") if e.get_task_name() else None
            for i in next_entities:
                self._exec_mgr.token.check()
                result = self.exec(i)
            log_fn(f"{prefix}执行完毕 {e.get_task_name()}") if e.get_task_name() else None
            return result
        return self._exec_entity(entity, _on_exec, action_chain=False)

    def _get_entity(self, section: Union[JczxSectionEntity, str]) -> JczxSectionEntity:
        if isinstance(section, str):
            section = self._resolver.resolve(section, section)
        return section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)

    def _resolve_scalar(self, entity: JczxSectionEntity, name: str):
        val = getattr(entity, name)
        if isinstance(val, str) and ("${" in val or "@{" in val or "%{" in val):
            val = self._resolver.resolve(val, entity.only_key)
            hints = get_type_hints(JczxSectionEntity)
            try:
                val = hints[name](val)
            except (ValueError, TypeError):
                pass
        return val

    def _exec_entity(self, entity: JczxSectionEntity, on_exec: Callable, *, testFor=False, action_chain=True, default_max_wait=0):
        """Template Method：封装实体执行的通用流程（times / testFor / sleep / log / action 链）。"""
        test_before = test_after = None
        if testFor:
            if entity.testFor_before:
                test_before = self.task_manage.get_img(entity.testFor_before)
            if entity.testFor_after:
                test_after = self.task_manage.get_img(entity.testFor_after)
        times = self._resolve_scalar(entity, "times")
        for _ in range(times):
            self._exec_mgr.token.check()
            old_ttl = self._screen_cache._ttl_ms
            screen_ttl = self._resolve_scalar(entity, "screen_cache_ttl")
            if screen_ttl >= 0:
                self._screen_cache.set_ttl(screen_ttl)
            try:
                if test_before is not None:
                    self._exec_mgr.token.sleep(self._resolve_scalar(entity, "testFor_pre_sleep"))
                    test_wait = self._resolve_scalar(entity, "testFor_max_wait")
                    if test_wait <= 0:
                        test_wait = default_max_wait
                    self.log.debug(f"开始等待 testFor_before {entity.testFor_before}")
                    if not self._wait_for_image(test_before, test_wait, per=self._resolve_scalar(entity, "testFor_per")):
                        self.log.debug(f"testFor_before 未匹配到 {entity.testFor_before}")
                        return None
                    self.log.debug(f"testFor_before 匹配到 {entity.testFor_before}")
                    self._exec_mgr.token.sleep(self._resolve_scalar(entity, "testFor_sleep"))
                self._exec_mgr.token.sleep(self._resolve_scalar(entity, "pre_sleep"))
                self.log.debug(f"开始执行实体 {entity.get_task_name()} {entity}")
                result = on_exec(entity)
                self._exec_mgr.token.sleep(self._resolve_scalar(entity, "sleep"))
                if entity.wait_target:
                    wait_img = self.task_manage.get_img(self._resolver.resolve(entity.wait_target, entity.only_key))
                    if wait_img is not None:
                        wait_max = self._resolve_scalar(entity, "max_wait")
                        self.log.debug(f"等待 wait_target {entity.wait_target}，超时 {wait_max}s")
                        self._wait_for_image(wait_img, wait_max, per=self._resolve_scalar(entity, "wait_target_per"))
                self._log_message(entity)
                if action_chain and entity.action:
                    resolved = self._resolver.resolve_list(entity.action, entity.only_key)
                    next_entities = [self.task_manage.get_entity(i) for i in resolved]
                    if next_entities:
                        self.log.debug(f"获取下一执行链 {[i.only_key for i in next_entities]}")
                    for i in next_entities:
                        result = self.exec(i)
                if test_after is not None:
                    if not self.in_location(entity.testFor_after):
                        self.log.debug(f"testFor_after {entity.testFor_after} 不可见，重新执行")
                        continue
                    self.log.debug(f"testFor_after {entity.testFor_after} 可见")
            finally:
                self._screen_cache.set_ttl(old_ttl)
        return result

    def _ocr_match_region(self, mt: MatchTemplete) -> str:
        """从 MatchTemplete 结果中裁剪区域并执行 OCR，返回识别文本。"""
        pt_range = mt.matchTempletePointRange
        if pt_range is None:
            self.log.debug("OCR 裁剪失败: matchTempletePointRange 为 None")
            return ""
        (x0, y0), (x1, y1) = pt_range
        if x0 >= x1 or y0 >= y1:
            self.log.debug(f"OCR 裁剪失败: 非法范围 ({x0},{y0})-({x1},{y1})")
            return ""
        cropped = mt.baseGrayScreenshot[y0:y1, x0:x1]
        if cropped is None or cropped.size == 0:
            self.log.debug(f"OCR 裁剪失败: 图片为空, 范围 ({x0},{y0})-({x1},{y1})")
            return ""
        self.log.debug(f"OCR 裁剪区域: ({x0},{y0})-({x1},{y1}) 尺寸 {cropped.shape[1]}x{cropped.shape[0]}")
        if len(cropped.shape) == 2:
            cropped = cv2.cvtColor(cropped, cv2.COLOR_GRAY2BGR)
        if self.ocr is None:
            self.log.warning("OCR 未初始化，无法识别")
            return ""
        texts = self.ocr.readtext(cropped)
        result = "".join(texts) if texts else ""
        if result:
            self.log.debug(f"OCR 识别结果: {result}")
        else:
            self.log.warning(f"OCR 识别为空: 裁剪区域 ({x0},{y0})-({x1},{y1}) 尺寸 {cropped.shape[1]}x{cropped.shape[0]}, 检查 target 坐标和 per 阈值是否正确")
        return result

    @staticmethod
    def _convert_output(result, context_type: str):
        match context_type:
            case "int": return int(result)
            case "float": return float(result)
            case "bool": return bool(result)
            case _: return str(result)

    @staticmethod
    def _convert_value(raw: str, value_type: str):
        if value_type == "int":
            try:
                return int(float(raw))
            except (ValueError, TypeError):
                return 0
        elif value_type == "float":
            try:
                return float(raw)
            except (ValueError, TypeError):
                return 0.0
        elif value_type == "bool":
            return str(raw).lower() in ("true", "1", "yes")
        return raw

    @staticmethod
    def _apply_context_op(value, action: str):
        parts = action.split("|", 1)
        if len(parts) != 2:
            return value
        op, rhs = parts
        if isinstance(value, str):
            if op == "+":
                return value + rhs
            elif op == "=":
                return rhs
            elif op == "==":
                return value == rhs
            elif op == "contains":
                return rhs in value
            return value
        rhs_num = float(rhs) if rhs else 0.0
        rhs_is_int = "." not in rhs and rhs != ""
        if op == "=":
            return int(rhs_num) if rhs_is_int and rhs_num == int(rhs_num) else rhs_num
        if op == "==":
            return value == rhs_num
        if op == ">":
            return value > rhs_num
        if op == "<":
            return value < rhs_num
        if op == ">=":
            return value >= rhs_num
        if op == "<=":
            return value <= rhs_num
        if op == "/":
            return value / rhs_num
        if isinstance(value, int) and rhs_is_int:
            rhs_int = int(rhs_num)
            if op == "+":
                return value + rhs_int
            if op == "-":
                return value - rhs_int
            if op == "x":
                return value * rhs_int
        else:
            if op == "+":
                return value + rhs_num
            if op == "-":
                return value - rhs_num
            if op == "x":
                return value * rhs_num
        return value

    def _log_message(self, entity: JczxSectionEntity) -> None:
        if not entity.log:
            return
        msg = self._resolver.resolve(entity.log, entity.only_key)
        log_fn = getattr(self.log, entity.log_level, self.log.info)
        log_fn(f"[{entity.get_task_name() or entity.only_key}] {msg}")

    def exec(self, section: Union[JczxSectionEntity, str]):
        """统一调度入口：根据 type 分发到对应执行方法，执行后自动将返回值存入上下文变量（若设置了 context_key）。"""
        if not section:
            return None
        self._exec_mgr.token.check()
        if isinstance(section, str):
            section = self._resolver.resolve(section, section)
        entity = section if isinstance(section, JczxSectionEntity) else self.task_manage.get_entity(section)
        match entity.type:
            case SectionType.TASK.value:
                result = self.exec_task(entity)
            case SectionType.FUNC.value:
                result = self.exec_func(entity)
            case SectionType.CLICK.value:
                result = self.exec_click(entity)
            case SectionType.DYNAMIC.value:
                result = self.exec_dynamic(entity)
            case SectionType.MATCH.value:
                result = self.exec_match(entity)
            case SectionType.OCR.value:
                result = self.exec_ocr(entity)
            case SectionType.CONTEXT.value:
                result = self.exec_context(entity)
            case SectionType.CONDITION.value:
                result = self.exec_condition(entity)
            case _:
                return None
        if entity.context_key and result is not None and entity.type != SectionType.CONTEXT.value and entity.type != SectionType.CONDITION.value:
            try:
                match entity.context_type:
                    case "int":
                        self.context_set(entity.context_key, int(float(result)))
                    case "float":
                        self.context_set(entity.context_key, float(result))
                    case "bool":
                        self.context_set(entity.context_key, bool(result))
                    case _:
                        self.context_set(entity.context_key, str(result))
            except (ValueError, TypeError) as e:
                self.log.warning(f"[{entity.get_task_name() or entity.only_key}] 上下文类型转换失败: context_type={entity.context_type}, result={result!r}, error={e}")
                self.context_set(entity.context_key, str(result))
        return result

    def _wait_for_image(self, img, max_wait: int, per: float = 0.8) -> bool:
        start = time.monotonic()
        while True:
            self._exec_mgr.token.check()
            if self.findImageCenterLocations(img, per=per):
                return True
            if max_wait > 0 and time.monotonic() - start >= max_wait:
                break
            self._exec_mgr.token.sleep(0.3)
        return False

    def get_resources_target(self, target: str):
        rel_path = "\\".join(["resources"] + target.split("\\"))
        return str(self.fm.get_obj_relative_path(rel_path, self))

    def exec_task_raw(self, section: Union[JczxSectionEntity, str]):
        """顶层任务执行入口：执行前后清空上下文变量，确保每个顶层任务上下文隔离。"""
        self._context.clear()
        try:
            return self.exec_task(section)
        finally:
            self._context.clear()

    def exec_queue(self, queue_id: str, on_progress=None) -> None:
        queue = self.task_manage.get_queue(queue_id)
        if not queue:
            self.log.warning(f"队列 {queue_id} 不存在")
            return
        tasks = queue.tasks
        n = len(tasks)
        self.log.info(f"开始执行队列 [{queue.name}]，共 {n} 个任务")
        for i, task_key in enumerate(tasks):
            self._exec_mgr.token.check()
            entity = self.task_manage.get_task(task_key)
            if entity is None:
                self.log.warning(f"队列任务 [{task_key}] 不存在，跳过")
                continue
            self.log.info(f"队列 [{queue.name}] {i + 1}/{n}: {entity.get_task_name()}")
            if on_progress:
                on_progress(queue.name, i, n, entity.get_task_name())
            self.exec_task_raw(task_key)
        self.log.info(f"队列 [{queue.name}] 执行完毕")

    def in_location(self, target: str, per: float = 0.8):
        """检测指定图片是否在当前屏幕上可见，返回 bool。"""
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
    """仅当 RichLog 已在底部时自动滚动；高频日志写入合并到一个定时回调中处理。"""

    def __init__(self, rich_log):
        super().__init__()
        self.rich_log = rich_log
        self.terminator = ""
        self._buffer: list[str] = []

    def emit(self, record):
        try:
            msg = self.format(record)
            self._buffer.append(msg)
            try:
                app = self.rich_log.app
                app.call_from_thread(self._flush_buffer)
            except Exception:
                self._flush_buffer()
        except Exception:
            self.handleError(record)

    def _flush_buffer(self):
        if not self._buffer:
            return
        msgs = self._buffer[:]
        self._buffer.clear()
        at_bottom = self.rich_log.max_scroll_y is None or getattr(self.rich_log, 'scroll_y', 0) >= self.rich_log.max_scroll_y
        self.rich_log.auto_scroll = at_bottom
        for msg in msgs:
            self.rich_log.write(msg)


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
        mode = self.config.get_config(opt="debug.screenshot.mode") or "off"
        debug_dir = os.path.join(os.getcwd(), "screenHistory")
        self._debug_recorder = DebugRecorder(mode, debug_dir, self.logger)
        self._debug_recorder.ensure_dir()
        self.rich_log = RichLog(id="console", highlight=True, auto_scroll=False)
        self._running_future: Optional[Future] = None
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

    @property
    def _running_task_id(self) -> str | None:
        return self.device._exec_mgr.task_id if self.device else None

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
        if self.ocr:
            self.device.set_ocr(self.ocr)
        self.device._recorder = self._debug_recorder
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
            use_textline_orientation = False,
            use_doc_orientation_classify = False,
            lang = 'ch',
            device = 'cpu',
            engine = 'onnxruntime',
        )
        self.logger.info("OCR初始化完成")

class JczxTUI(App, JczxCli):
    BINDINGS = [
        Binding("q", "quit", translate("退出程序", LANGUAGE)),
        Binding("ctrl+l", "clear_log", translate("清空日志", LANGUAGE)),
        Binding("ctrl+shift+c", "copy_log", translate("复制日志", LANGUAGE)),
    ]
    CSS_PATH = "Css\\main.tcss"

    def __init__(self):
        super().__init__()
        JczxCli.__init__(self)
        self._editing_queue_id: str | None = None

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
                yield QueuePanel(
                    queues=self._get_queue_options(),
                    id="queue-panel",
                )
        yield Footer(show_command_palette=False)

    def action_clear_log(self) -> None:
        self.rich_log.clear()
        self.logger.debug("日志控制台已清空")

    def action_copy_log(self) -> None:
        text = str(self.rich_log.render_str)
        self.copy_to_clipboard(text)
        self.logger.debug("日志已复制到剪贴板")

    def on_mount(self) -> None:
        self._populate_task_list()
        self._initialized = False
        self.run_worker(self._init_after_mount, thread=True)

    def _init_after_mount(self) -> None:
        """在后台线程执行 初始化，完成后回主线程刷新 UI."""
        self._init_something()
        self.call_from_thread(self._update_device_bar)
        self.call_from_thread(lambda: setattr(self, '_initialized', True))

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

    def _get_queue_options(self) -> list[tuple[str, str]]:
        return [(q.name, q.id) for q in self.task_manage.get_queues()]

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
        queue_panel = self.query_one("#queue-panel", QueuePanel)
        queue_panel.set_queues(self._get_queue_options())

    def _refresh_devices(self) -> None:
        self._init_device()
        self.call_from_thread(self._update_device_bar)
        self.call_from_thread(
            lambda: self.logger.info("设备列表已刷新")
        )

    # ── TaskCard handlers ────────────────────────────────

    def on_task_card_toggle_pressed(self, event: TaskCard.TogglePressed) -> None:
        if not getattr(self, '_initialized', False):
            self.logger.debug("初始化未完成，忽略启停操作")
            return
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
        if self.device._exec_mgr.is_running():
            self.logger.warning("已有任务/队列正在执行，请先停止")
            return False
        entity = self.task_manage.get_task(task_id)
        if not entity:
            self.logger.error("任务实体不存在: %s", task_id)
            return False
        self.device._exec_mgr.start(task_id)
        self.logger.info("任务启动: %s", entity.get_task_name())
        self._running_future = self.executor.submit(self._run_task, entity, task_id)
        return True

    def _stop_running_task(self) -> None:
        if self.device:
            self.device._exec_mgr.stop()
        self.logger.info("任务已停止")
        try:
            panel = self.query_one("#queue-panel", QueuePanel)
            panel.clear_progress()
            panel.reset_toggle()
        except Exception:
            pass

    def _run_task(self, entity: JczxSectionEntity, task_id: str) -> None:
        try:
            self.device.exec_task_raw(entity)
        except TaskCancelledError:
            self.logger.info("任务已取消: %s", entity.get_task_name())
        except Exception as e:
            self.logger.error("任务执行异常: %s", e)
        finally:
            self.call_from_thread(self._on_task_finished, task_id)

    def _on_task_finished(self, task_id: str) -> None:
        if self.device and self.device._exec_mgr.task_id != task_id:
            return
        if self.device:
            self.device._exec_mgr.reset()
        panel = self.query_one("#task-list-panel", TaskListPanel)
        for card in panel.body.query(TaskCard):
            if card._task_id == task_id:
                card.reset_toggle()
        self._running_future = None

    def on_task_card_settings_pressed(self, event: TaskCard.SettingsPressed) -> None:
        if not getattr(self, '_initialized', False):
            self.logger.debug("初始化未完成，忽略设置操作")
            return
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

    # ── QueuePanel handlers ──────────────────────────────

    def on_queue_panel_run_requested(self, event: QueuePanel.RunRequested) -> None:
        if not getattr(self, '_initialized', False):
            self.logger.debug("初始化未完成，忽略队列操作")
            return
        if event.running:
            self._start_queue(event.queue_id)
        else:
            self._stop_running_task()

    def on_queue_panel_edit_requested(self, event: QueuePanel.EditRequested) -> None:
        if not getattr(self, '_initialized', False):
            return
        self._editing_queue_id = event.queue_id
        if event.queue_id:
            queue = self.task_manage.get_queue(event.queue_id)
            name = queue.name if queue else ""
            tasks = [(k, self.task_manage.get_task_display_name(k)) for k in (queue.tasks if queue else [])]
        else:
            name = ""
            tasks = []
        available = [(k, self.task_manage.get_task_display_name(k)) for k in self._get_editor_task_names()]
        self.push_screen(
            QueueEditorScreen(event.queue_id, name, tasks, available),
            callback=self._on_queue_editor_closed,
        )

    def _on_queue_editor_closed(self, result: dict | None) -> None:
        if result is None:
            return
        if result.get("delete"):
            queue_id = self._editing_queue_id
            self.task_manage.delete_queue(queue_id)
            self.logger.info("队列已删除: %s", queue_id)
            self._refresh_queue_panel()
            return
        name = result.get("name", "")
        task_keys = result.get("tasks", [])
        if not task_keys:
            self.logger.warning("队列任务列表为空，未保存")
            return
        queue_id = self._editing_queue_id or f"queue-{name}"
        self.task_manage.save_queue(queue_id, name, task_keys)
        self.logger.info("队列已保存: %s (%d 个任务)", name, len(task_keys))
        self._refresh_queue_panel()
        self.query_one("#queue-panel", QueuePanel).select_queue(queue_id)

    def _refresh_queue_panel(self) -> None:
        panel = self.query_one("#queue-panel", QueuePanel)
        panel.set_queues(self._get_queue_options())

    def _start_queue(self, queue_id: str) -> bool:
        if not self.device:
            self.logger.warning("设备未就绪，无法启动队列")
            return False
        if not self.ocr:
            self.logger.warning("OCR 未初始化完成，无法启动队列")
            return False
        if self.device._exec_mgr.is_running():
            self.logger.warning("已有任务/队列正在执行，请先停止")
            queue_panel = self.query_one("#queue-panel", QueuePanel)
            queue_panel.reset_toggle()
            return False
        queue = self.task_manage.get_queue(queue_id)
        if not queue:
            self.logger.error("队列不存在: %s", queue_id)
            return False
        self.device._exec_mgr.start(queue_id)
        self.logger.info("队列启动: %s", queue.name)
        self._running_future = self.executor.submit(self._run_queue, queue_id)
        return True

    def _run_queue(self, queue_id: str) -> None:
        try:
            self.device.exec_queue(queue_id, on_progress=lambda name, i, n, tn:
                self.call_from_thread(self._on_queue_progress, name, i, n, tn))
        except TaskCancelledError:
            self.logger.info("队列已取消: %s", queue_id)
        except Exception as e:
            self.logger.error("队列执行异常: %s", e)
        finally:
            self.call_from_thread(self._on_queue_finished, queue_id)

    def _on_queue_finished(self, queue_id: str) -> None:
        if self.device and self.device._exec_mgr.task_id != queue_id:
            return
        if self.device:
            self.device._exec_mgr.reset()
        panel = self.query_one("#queue-panel", QueuePanel)
        panel.reset_toggle()
        panel.clear_progress()
        self._running_future = None

    def _on_queue_progress(self, name: str, idx: int, total: int, task_name: str) -> None:
        try:
            panel = self.query_one("#queue-panel", QueuePanel)
            panel.update_progress(name, idx, total, task_name)
        except Exception:
            pass
