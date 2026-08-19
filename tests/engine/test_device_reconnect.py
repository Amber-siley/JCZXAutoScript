"""方案 2：_reconnect_adb 设备重连逻辑（模拟器重启后旧 TCP 传输失效的修复）。"""
import logging
from types import SimpleNamespace

from jczx.jczxCli import JczxCli


class FakeAdb:
    def __init__(self, devices, device_id="127.0.0.1:7555"):
        self.device_id = device_id
        self.size = (2400, 1080)
        self.connect_calls = []
        self.u2_calls = 0
        self.screen_calls = 0
        self._devices = list(devices)

    def connenct(self, port):
        self.connect_calls.append(port)

    def get_device_names(self):
        return list(self._devices)

    def getScreenSize(self):
        self.screen_calls += 1
        self.size = (100, 50)
        return self.size

    def _init_u2_device(self):
        self.u2_calls += 1


def _make(adb):
    inst = object.__new__(JczxCli)
    inst.adb = adb
    inst.config = SimpleNamespace(get_config=lambda opt: "7555")
    inst.logger = logging.getLogger("test")
    return inst


class TestReconnectAdb:
    def test_reconnects_port_and_prefers_port_address(self):
        adb = FakeAdb(["emulator-5554", "127.0.0.1:7555"])
        cli = _make(adb)
        cli._reconnect_adb()
        assert adb.connect_calls == [7555], "应重新 adb connect 端口"
        assert adb.device_id == "127.0.0.1:7555", "优先使用端口地址"
        assert adb.screen_calls == 1, "应重取分辨率（size 已置 None）"
        assert adb.u2_calls == 1, "应重连 u2"

    def test_updates_device_id_when_port_gone(self):
        """模拟器重启后旧端口不在设备列表 → 回退到当前列表第一个。"""
        adb = FakeAdb(["emulator-5554"], device_id="127.0.0.1:7555")
        cli = _make(adb)
        cli._reconnect_adb()
        assert adb.device_id == "emulator-5554"
        assert adb.connect_calls == [7555]

    def test_no_devices_sets_none(self):
        adb = FakeAdb([])
        cli = _make(adb)
        cli._reconnect_adb()
        assert adb.device_id is None

    def test_connect_failure_still_updates_device(self):
        """connenct 失败（如端口未就绪）不阻断后续设备列表刷新。"""

        class _FragileAdb(FakeAdb):
            def connenct(self, port):
                raise RuntimeError("connect failed")

        adb = _FragileAdb(["emulator-5554"], device_id="127.0.0.1:7555")
        cli = _make(adb)
        cli._reconnect_adb()
        assert adb.device_id == "emulator-5554"

    def test_get_screen_size_failure_keeps_old_size(self):
        """模拟器刚启动时 wm size 瞬时不稳：getScreenSize 失败应保留旧 size，避免 size=None 崩溃。"""

        class _FragileScreenAdb(FakeAdb):
            def getScreenSize(self):
                raise RuntimeError("wm size 暂不可用")

        adb = _FragileScreenAdb(["emulator-5554", "127.0.0.1:7555"],
                                device_id="127.0.0.1:7555")
        adb.size = (2400, 1080)  # 旧分辨率
        cli = _make(adb)
        cli._reconnect_adb()
        assert adb.device_id == "127.0.0.1:7555"
        assert adb.size == (2400, 1080), "刷新失败应保留旧 size，而非置 None"
