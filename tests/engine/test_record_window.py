import json
import logging
import os
from types import SimpleNamespace

import numpy as np
import pytest
from textual.app import App, active_app

from jczx.debug.recorder import DebugRecorder
from jczx.debug.recordWindow import RecordWindow
from jczx.jczxCli import JczxTUI
from jczx.widgets import DeviceBar


class _DummyTextualApp(App):
    """No-op clear_selection so Textual 8.2.7 widget construction works outside run()."""

    def clear_selection(self) -> None:
        pass


class TestRecorderLastSaved:
    def test_last_saved_updates_after_save(self, tmp_path):
        rec = DebugRecorder("annotated", str(tmp_path), logging.getLogger("record-test"))
        rec.on_click(np.zeros((10, 10, 3), np.uint8), 5, 5)
        assert rec.last_saved == "1.png", "on_click 保存后 last_saved 应为 1.png"
        rec.on_swipe(np.zeros((10, 10, 3), np.uint8), 0, 0, 5, 5, "滑动")
        assert rec.last_saved == "2.png", "on_swipe 保存后 last_saved 应为 2.png"

    def test_last_saved_default_none(self, tmp_path):
        rec = DebugRecorder("annotated", str(tmp_path), logging.getLogger("record-test"))
        assert rec.last_saved is None


class FakeRecordRecorder:
    """模拟 DebugRecorder：on_click/on_swipe 更新 last_saved。"""

    def __init__(self):
        self.last_saved = None
        self._n = 0

    def on_click(self, screenshot, x, y):
        self._n += 1
        self.last_saved = f"{self._n}.png"

    def on_swipe(self, *a, **k):
        self._n += 1
        self.last_saved = f"{self._n}.png"

    def on_step(self, *a, **k):
        pass


def make_record_window(gaming, tmp_path, recorder):
    """构造 RecordWindow：不启动 tkinter，注入桩替身与固定配置。"""
    win = RecordWindow(
        gaming,
        SimpleNamespace(get_config=lambda opt: {
            "record.click_move_threshold": "15",
            "record.hold_threshold": "300",
            "record.refresh_interval": "200",
        }.get(opt, "")),
        str(tmp_path),
        logging.getLogger("record-test"),
    )
    win._session_id = "20260823_153000"
    win._scale = 1.0
    win._root = None
    win._last_gesture = None
    gaming._recorder = recorder
    gaming.device_id = "127.0.0.1:7555"
    gaming.size = (200, 200)
    return win


class TestRecordWindowApplyGesture:
    def test_click_applies_and_records(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.click = lambda x, y: (gaming.clicks.append((x, y)), rec.on_click(None, x, y))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("click", 30, 40, 30, 40)
        assert gaming.clicks == [(30, 40)], "应点击换算后的设备坐标"
        assert win._actions[0]["type"] == "click"
        assert win._actions[0]["x"] == 30 and win._actions[0]["y"] == 40
        assert win._actions[0]["screenshot"] == "1.png", "screenshot 应取自 recorder.last_saved"

    def test_swipe_applies_and_records(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.swipes = []
        gaming.swipe = lambda x1, y1, x2, y2, duration: (gaming.swipes.append((x1, y1, x2, y2, duration)), rec.on_swipe(None, x1, y1))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("swipe", 0, 0, 100, 200)
        assert gaming.swipes == [(0, 0, 100, 200, 200)], "swipe 应带默认时长 200"
        assert win._actions[0]["type"] == "swipe"
        assert win._actions[0]["x2"] == 100 and win._actions[0]["duration"] == 200

    def test_drag_applies_and_records(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.drags = []
        gaming.dragAndDrop = lambda x1, y1, x2, y2, duration: (gaming.drags.append((x1, y1, x2, y2, duration)), rec.on_swipe(None, x1, y1))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("drag", 1, 2, 3, 4)
        assert gaming.drags == [(1, 2, 3, 4, 200)]
        assert win._actions[0]["type"] == "drag"

    def test_coords_scaled_by_scale(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.click = lambda x, y: (gaming.clicks.append((x, y)), rec.on_click(None, x, y))
        win = make_record_window(gaming, tmp_path, rec)
        win._scale = 2.0
        win._apply_gesture("click", 60, 80, 60, 80)
        assert gaming.clicks == [(30, 40)], "像素坐标应除以缩放系数换算设备坐标"


class TestRecordWindowClose:
    def test_close_writes_json(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        gaming.click = lambda x, y: (gaming.clicks.append((x, y)), rec.on_click(None, x, y))
        win = make_record_window(gaming, tmp_path, rec)
        win._apply_gesture("click", 30, 40, 30, 40)
        win._close()
        path = os.path.join(str(tmp_path), "record_20260823_153000.json")
        assert os.path.exists(path), "关闭窗口应写出 JSON"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["session"] == "20260823_153000"
        assert data["device"] == "127.0.0.1:7555"
        assert data["resolution"] == [200, 200]
        assert data["actions"][0]["screenshot"] == "1.png"
        assert data["started_at"] == win._started_at, "started_at 应为会话开始时刻（构造时捕获）"

    def test_close_no_actions_no_file(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        win = make_record_window(gaming, tmp_path, rec)
        win._close()
        path = os.path.join(str(tmp_path), "record_20260823_153000.json")
        assert not os.path.exists(path), "无操作时不生成 JSON"


class TestSyncMode:
    """记录窗口画面同步模式：screenshot（带缓存）/ u2（绕缓存高频截图）。"""

    def test_u2_mode_uses_u2_device(self, gaming, tmp_path):
        rec = FakeRecordRecorder()

        class FakeU2:
            def __init__(self):
                self.calls = []

            def screenshot(self, format):
                self.calls.append(format)
                return np.zeros((2, 2, 3), np.uint8)

        fake = FakeU2()
        gaming.u2_device = fake
        win = make_record_window(gaming, tmp_path, rec)
        win._sync_mode = "u2"
        img = win._take_frame()
        assert fake.calls == ["opencv"], "u2 模式应调用 u2_device.screenshot(format=opencv)"
        assert img.shape == (2, 2, 3)

    def test_u2_mode_falls_back_without_u2(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        win = make_record_window(gaming, tmp_path, rec)
        win._sync_mode = "u2"
        img = win._take_frame()
        assert img is not None, "无 u2_device 时应回退 device.screenshot()"

    def test_screenshot_mode_uses_device_screenshot(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        calls = []
        gaming.screenshot = lambda: (calls.append(1), np.zeros((4, 4, 3), np.uint8))[1]
        win = make_record_window(gaming, tmp_path, rec)
        win._sync_mode = "screenshot"
        img = win._take_frame()
        assert calls == [1], "screenshot 模式应调用 device.screenshot()"
        assert img.shape == (4, 4, 3)


class TestFpsDisplay:
    """记录窗口 FPS 显示：固定时间窗口平均帧率（float，两位小数）。"""

    def test_fps_updates_when_window_full(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        win = make_record_window(gaming, tmp_path, rec)
        win._fps_window = 1.0
        # 窗口未满：不更新，计数保持
        fc, ws = win._accumulate_fps(5, 100.0, 100.5)
        assert win._fps == 0.0, "窗口未满不更新 FPS"
        assert fc == 5 and ws == 100.0
        # 窗口满（elapsed >= 1.0）：更新 FPS 并重置计数
        fc, ws = win._accumulate_fps(5, 100.0, 101.0)
        assert win._fps == 5.0, "5 帧 / 1 秒 = 5.0 FPS"
        assert fc == 0 and ws == 101.0

    def test_fps_is_float_precision(self, gaming, tmp_path):
        rec = FakeRecordRecorder()
        win = make_record_window(gaming, tmp_path, rec)
        win._fps_window = 1.0
        win._accumulate_fps(7, 100.0, 102.0)
        assert isinstance(win._fps, float)
        assert win._fps == 3.5, "7 帧 / 2 秒 = 3.5 FPS"
        assert f"{win._fps:.2f}" == "3.50", "显示应精确到两位小数"


class TestDeviceBarRecordButton:
    @pytest.fixture(autouse=True)
    def _active_app(self):
        """注入 active_app 上下文：Textual 8.2.7 的 Input 构造需访问 self.app。"""
        token = active_app.set(_DummyTextualApp())
        try:
            yield
        finally:
            active_app.reset(token)

    def test_record_button_shown_when_show_record(self):
        bar = DeviceBar(show_record=True)
        ids = [w.id for w in bar.compose()]
        assert "record-btn" in ids, "show_record=True 时应渲染记录按钮"

    def test_record_button_hidden_by_default(self):
        bar = DeviceBar()
        ids = [w.id for w in bar.compose()]
        assert "record-btn" not in ids, "默认不渲染记录按钮"


class TestRecordPressed:
    def test_no_device_warns_and_no_thread(self, monkeypatch, caplog):
        cli = object.__new__(JczxTUI)
        cli._record_active = False
        cli.device = None
        cli.logger = logging.getLogger("record-test")
        started = []
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name=None: SimpleNamespace(start=lambda: started.append(target)))
        cli.on_device_bar_record_pressed(SimpleNamespace())
        assert started == [], "设备未连接不应启动线程"
        assert any("设备未连接" in r.message for r in caplog.records)

    def test_device_starts_thread(self, monkeypatch):
        cli = object.__new__(JczxTUI)
        cli._record_active = False
        cli.device = SimpleNamespace(_exec_mgr=SimpleNamespace(is_running=lambda: False))
        cli.logger = logging.getLogger("record-test")
        started = []
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name=None: SimpleNamespace(start=lambda: started.append(SimpleNamespace(daemon=daemon))))
        cli.on_device_bar_record_pressed(SimpleNamespace())
        assert len(started) == 1, "设备已连接应启动记录线程"
        assert started[0].daemon is True
        assert cli._record_active is True, "启动记录线程后应置位 _record_active"

    def test_record_active_blocks_second_open(self, monkeypatch, caplog):
        cli = object.__new__(JczxTUI)
        cli._record_active = True
        cli.device = SimpleNamespace(_exec_mgr=SimpleNamespace(is_running=lambda: False))
        cli.logger = logging.getLogger("record-test")
        started = []
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name=None: SimpleNamespace(start=lambda: started.append(target)))
        cli.on_device_bar_record_pressed(SimpleNamespace())
        assert started == [], "记录窗口已打开不应再次启动线程"
        assert any("记录窗口已打开" in r.message for r in caplog.records)
