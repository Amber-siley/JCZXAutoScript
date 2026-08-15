"""方案 2 harness：FakeDevice 桩替身，object.__new__ 绕过 ADB（避免 ready_env 联网下载）。"""
import logging
from types import SimpleNamespace

import numpy as np

from jczx.CommonBuilder.CommonBuilder.Android.Adb import MatchTemplete
from jczx.jczxCli import JCZXGaming, PlaceholderResolver, ScreenshotCache
from jczx.taskManage import TaskManage

_SCREEN = np.zeros((200, 200, 3), np.uint8)


def make_match(x0, y0, x1, y1, *, tw=10, th=10):
    """构造位于 (x0,y0)-(x1,y1) 的确定性 MatchTemplete。"""
    gray = np.zeros((200, 200), np.uint8)
    return MatchTemplete(
        baseGrayScreenshot=gray,
        grayScreenshot=gray,
        templeteSize=(tw, th),
        matchTempletePoints=[((x0, y0), (x1, y0), (x0, y1), (x1, y1))],
        matchTempleteCenterPoints=[((x0 + x1) // 2, (y0 + y1) // 2)],
    )


def _unmatched():
    """未命中的 MatchTemplete（matched=False），与真实 findImageDetail 行为一致。"""
    gray = np.zeros((200, 200), np.uint8)
    return MatchTemplete(
        baseGrayScreenshot=gray, grayScreenshot=gray, templeteSize=(1, 1),
        matchTempletePoints=[], matchTempleteCenterPoints=[],
    )


class FakeMatcher:
    """findImageDetail 替身：按 target 字符串返回预设匹配，记录每次调用（含 cutPoints）。"""

    def __init__(self):
        self.calls = []
        self.results = {}

    def __call__(self, img, cutPoints=None, per=0.9, grayScreenshot=None):
        self.calls.append((img, cutPoints, per))
        if isinstance(img, str):
            return self.results.get(img, _unmatched())
        return _unmatched()


class FakeToken:
    """记录 sleep 时长并推进假时钟，不真实阻塞（测试秒级跑完）。"""

    def __init__(self):
        self.sleeps = []
        self._now = 0.0

    @property
    def now(self):
        return self._now

    def check(self):
        pass

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self._now += seconds

    def is_cancelled(self):
        return False


class RecordingRecorder:
    """记录 on_match / on_click 收到的数据，用于断言标注时机。"""

    def __init__(self):
        self.match_points = []
        self.clicks = []

    def on_match(self, screenshot, mt):
        if getattr(mt, "matched", False):
            self.match_points.append(mt.matchTempletePoints)

    def on_click(self, screenshot, x, y):
        self.clicks.append((x, y))

    def on_swipe(self, *a, **k):
        pass

    def on_ocr(self, *a, **k):
        pass

    def on_step(self, *a, **k):
        pass


def patch_clock(monkeypatch, gaming):
    """让 _wait_for_image 的超时判断使用 FakeToken 的假时钟。"""
    monkeypatch.setattr("jczx.jczxCli.time.monotonic", lambda: gaming.token.now)


def make_gaming(real_config_dir, *, matcher=None, clicks=None, recorder=None,
                token=None, exec_mgr=None):
    """构造引擎：绕过 Adb.__init__，注入桩替身。"""
    g = object.__new__(JCZXGaming)
    g.task_manage = TaskManage(real_config_dir)
    g._screen_cache = ScreenshotCache(screenshot_fn=lambda: _SCREEN, ttl_ms=500)
    tok = token if token is not None else FakeToken()
    g._exec_mgr = exec_mgr if exec_mgr is not None else SimpleNamespace(token=tok)
    g.token = tok
    g._resolver = PlaceholderResolver(g)
    g.log = logging.getLogger("engine-test")
    g._recorder = recorder
    g._context = {}
    g.ocr = None
    # —— 设备 I/O 全部替换 ——
    g.task_manage.get_img = lambda target: target  # target 字符串直通 matcher
    g.findImageDetail = matcher if matcher is not None else FakeMatcher()
    g.clicks = clicks if clicks is not None else []
    g.click = g.clicks.append
    g.matcher = matcher if matcher is not None else g.findImageDetail
    return g
