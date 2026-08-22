"""方案 2（引擎级）：JczxMcpServer — 4 个设备工具注册与行为。

host 桩替身：SimpleNamespace(device=make_gaming(...), logger=...)。
复用 fake_device 的 make_gaming（object.__new__ 绕过 ADB）。
"""
import asyncio
import logging
import os
from types import SimpleNamespace

from jczx.jczxCli import JczxCli
from jczx.mcpServer import JczxMcpServer


def make_host(gaming):
    return SimpleNamespace(device=gaming, logger=logging.getLogger("mcp-test"))


class FakeFm:
    """FileManage 替身：join_p 基于 work_path 拼接（对应真实 fm.join_p → work_path/template）。"""

    def __init__(self, work_path):
        self.work_path = str(work_path)

    def join_p(self, *args):
        return os.path.join(self.work_path, *args)


def make_save_host(gaming, tmp_path):
    return SimpleNamespace(device=gaming, logger=logging.getLogger("mcp-test"),
                           fm=FakeFm(tmp_path))


class TestToolRegistration:
    def test_nine_tools_registered(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        names = {t.name for t in asyncio.run(server._mcp.list_tools())}
        assert names == {
            "screenshot", "click", "swipe", "drag",
            "get_resolution", "crop_screenshot", "save_screenshot", "get_screenshot_mode",
            "run_entity",
        }


class TestDeviceOps:
    def test_click_with_target_clicks_center(self, gaming, tmp_path):
        import cv2
        import numpy as np
        p = str(tmp_path / "btn.png")
        cv2.imwrite(p, np.zeros((20, 20), np.uint8))
        gaming.findImageCenterLocations = lambda img, per=0.8, cutPoints=None, grayScreenshot=None: [(30, 40)]
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        result = server._do_click(target=p)
        assert "已点击目标" in result and "(30, 40)" in result
        assert gaming.clicks == [(30, 40)], "应点击模板匹配的中心点"

    def test_click_with_target_not_found_raises(self, gaming, tmp_path):
        import cv2
        import numpy as np
        p = str(tmp_path / "btn.png")
        cv2.imwrite(p, np.zeros((20, 20), np.uint8))
        gaming.findImageCenterLocations = lambda img, per=0.8, cutPoints=None, grayScreenshot=None: []
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        try:
            server._do_click(target=p)
            assert False, "应抛未匹配"
        except RuntimeError as e:
            assert "未匹配到目标" in str(e)

    def test_click_with_bad_target_raises(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        try:
            server._do_click(target="nonexistent\\path.png")
            assert False, "应抛无法加载"
        except RuntimeError as e:
            assert "无法加载" in str(e)

    def test_swipe_calls_device(self, gaming):
        gaming.swipes = []
        gaming.swipe = lambda x1, y1, x2, y2, duration: gaming.swipes.append((x1, y1, x2, y2, duration))
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_swipe(0, 0, 100, 200) == "已滑动 (0,0) -> (100,200)"
        assert gaming.swipes == [(0, 0, 100, 200, 200)]

    def test_drag_calls_device(self, gaming):
        gaming.drags = []
        gaming.dragAndDrop = lambda x1, y1, x2, y2, duration: gaming.drags.append((x1, y1, x2, y2, duration))
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_drag(1, 2, 3, 4, 500) == "已拖动 (1,2) -> (3,4)"
        assert gaming.drags == [(1, 2, 3, 4, 500)]

    def test_screenshot_returns_png_image(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        img = server._do_screenshot()
        assert img.data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数
        assert img._format == "png"  # mcp v2.0.0 Image 将 format 存为私有 _format

    def test_get_resolution_returns_device_size(self, gaming):
        gaming.size = (2400, 1080)
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_get_resolution() == {"width": 2400, "height": 1080}

    def test_crop_screenshot_returns_cropped_png(self, gaming):
        import cv2
        import numpy as np
        img = np.arange(20 * 20 * 3, dtype=np.uint8).reshape(20, 20, 3)
        gaming.screenshot = lambda: img
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        out = server._do_crop_screenshot(5, 5, 10, 10)
        assert out._format == "png"
        dec = cv2.imdecode(np.frombuffer(out.data, np.uint8), cv2.IMREAD_COLOR)
        assert dec.shape == (5, 5, 3), f"应裁出 5x5，实际 {dec.shape}"
        assert (dec == img[5:10, 5:10]).all(), "裁切内容应与原图对应区域一致"

    def test_crop_screenshot_clips_to_bounds(self, gaming):
        import cv2
        import numpy as np
        gaming.screenshot = lambda: np.zeros((20, 20, 3), np.uint8)
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        out = server._do_crop_screenshot(-5, -5, 100, 100)
        dec = cv2.imdecode(np.frombuffer(out.data, np.uint8), cv2.IMREAD_COLOR)
        assert dec.shape == (20, 20, 3), "越界坐标应裁剪到画面范围"


class TestErrors:
    def test_device_not_connected_raises(self):
        host = SimpleNamespace(device=None, logger=logging.getLogger("mcp-test"))
        server = JczxMcpServer(host, 8765, logging.getLogger("mcp-test"))
        try:
            server._do_click(1, 1)
            assert False, "应抛设备未连接"
        except RuntimeError as e:
            assert "设备未连接" in str(e)

    def test_get_resolution_unknown_raises(self, gaming):
        gaming.size = None  # 设备无分辨率信息
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        try:
            server._do_get_resolution()
            assert False, "应抛设备分辨率未知"
        except RuntimeError as e:
            assert "设备分辨率未知" in str(e)

    def test_crop_screenshot_invalid_region_raises(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        try:
            server._do_crop_screenshot(10, 10, 5, 5)  # x2 < x1
            assert False, "应抛裁切区域无效"
        except RuntimeError as e:
            assert "裁切区域无效" in str(e)


class TestBusyWarning:
    def test_busy_warns_but_executes(self, gaming, caplog, tmp_path):
        import cv2
        import numpy as np
        p = str(tmp_path / "btn.png")
        cv2.imwrite(p, np.zeros((20, 20), np.uint8))
        gaming._exec_mgr = SimpleNamespace(is_running=lambda: True, token=gaming.token)
        gaming.findImageCenterLocations = lambda img, per=0.8, cutPoints=None, grayScreenshot=None: [(5, 5)]
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.WARNING, logger="mcp-test"):
            server._do_click(p)
        assert gaming.clicks == [(5, 5)], "应照常执行"
        assert any("任务执行期间" in r.message for r in caplog.records)


class TestDebugLogging:
    """MCP 工具调用应输出 debug 日志（工具名 + 参数 + 结果）。"""

    def test_tool_call_logs_debug(self, gaming, caplog, tmp_path):
        import cv2
        import numpy as np
        p = str(tmp_path / "btn.png")
        cv2.imwrite(p, np.zeros((20, 20), np.uint8))
        gaming.findImageCenterLocations = lambda img, per=0.8, cutPoints=None, grayScreenshot=None: [(5, 5)]
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_click(p)
        msgs = [r.message for r in caplog.records]
        assert any("MCP 工具调用 [click] target=" in m for m in msgs)
        assert any("MCP 工具调用 [click] 完成 -> 已点击目标" in m for m in msgs)

    def test_screenshot_logs_byte_count(self, gaming, caplog):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_screenshot()
        assert any("MCP 工具调用 [screenshot] 完成 -> " in r.message for r in caplog.records)

    def test_get_resolution_logs_debug(self, gaming, caplog):
        gaming.size = (2400, 1080)
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_get_resolution()
        msgs = [r.message for r in caplog.records]
        assert any("MCP 工具调用 [get_resolution]" in m for m in msgs)
        assert any("完成 -> 2400x1080" in m for m in msgs)

    def test_crop_screenshot_logs_debug(self, gaming, caplog):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_crop_screenshot(1, 1, 5, 5)
        msgs = [r.message for r in caplog.records]
        assert any("MCP 工具调用 [crop_screenshot] (1,1) -> (5,5)" in m for m in msgs)
        assert any("完成 -> " in m for m in msgs)

    def test_save_screenshot_logs_debug(self, gaming, tmp_path, caplog):
        server = JczxMcpServer(make_save_host(gaming, tmp_path), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_save_screenshot("d1")
        assert any("MCP 工具调用 [save_screenshot]" in r.message for r in caplog.records)

    def test_get_screenshot_mode_logs_debug(self, gaming, caplog):
        host = SimpleNamespace(device=gaming, logger=logging.getLogger("mcp-test"),
                               config=SimpleNamespace(get_config=lambda opt: "annotated"))
        server = JczxMcpServer(host, 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_get_screenshot_mode()
        assert any("MCP 工具调用 [get_screenshot_mode]" in r.message for r in caplog.records)


class TestSaveScreenshot:
    """save_screenshot：保存到 template/{name}.png（与截图任务路径一致），可选裁切区域。"""

    def test_save_full_screenshot(self, gaming, tmp_path):
        import cv2
        server = JczxMcpServer(make_save_host(gaming, tmp_path), 8765, logging.getLogger("mcp-test"))
        result = server._do_save_screenshot("shot1")
        assert "截图已保存到" in result
        p = str(tmp_path / "template" / "shot1.png")
        assert os.path.exists(p), f"应保存到 {p}"
        img = cv2.imread(p)
        assert img.shape == (200, 200, 3)  # _SCREEN 尺寸

    def test_save_cropped_screenshot(self, gaming, tmp_path):
        import cv2
        import numpy as np
        gaming.screenshot = lambda: np.arange(20 * 20 * 3, dtype=np.uint8).reshape(20, 20, 3)
        server = JczxMcpServer(make_save_host(gaming, tmp_path), 8765, logging.getLogger("mcp-test"))
        server._do_save_screenshot("crop1", 5, 5, 10, 10)
        p = str(tmp_path / "template" / "crop1.png")
        assert os.path.exists(p)
        img = cv2.imread(p)
        assert img.shape == (5, 5, 3), f"应保存 5x5 裁切，实际 {img.shape}"

    def test_save_screenshot_invalid_crop_raises(self, gaming, tmp_path):
        server = JczxMcpServer(make_save_host(gaming, tmp_path), 8765, logging.getLogger("mcp-test"))
        try:
            server._do_save_screenshot("bad", 10, 10, 5, 5)
            assert False, "应抛裁切区域无效"
        except RuntimeError as e:
            assert "裁切区域无效" in str(e)


class TestGetScreenshotMode:
    """get_screenshot_mode：读取 TUI 的 debug.screenshot.mode，无配置回退 off。"""

    def test_returns_config_mode(self, gaming):
        host = SimpleNamespace(device=gaming, logger=logging.getLogger("mcp-test"),
                               config=SimpleNamespace(get_config=lambda opt: "annotated"))
        server = JczxMcpServer(host, 8765, logging.getLogger("mcp-test"))
        assert server._do_get_screenshot_mode() == "annotated"

    def test_defaults_off_when_no_config(self, gaming):
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        assert server._do_get_screenshot_mode() == "off"


class TestRunEntity:
    """run_entity：按 section 名称依次执行实体。"""

    def test_executes_each_name_in_order(self, gaming):
        executed = []
        gaming.exec = lambda name: executed.append(name)
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        result = server._do_run_entity("task-a", "click-b")
        assert executed == ["task-a", "click-b"], "应按参数顺序依次执行"
        assert result == "已执行实体: task-a, click-b"

    def test_invalid_name_raises(self, gaming):
        executed = []
        gaming.exec = lambda name: executed.append(name)
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        try:
            server._do_run_entity("ok", None)
            assert False, "应抛实体名称无效"
        except RuntimeError as e:
            assert "实体名称无效" in str(e)
        assert executed == ["ok"], "无效名称前的实体应已执行"

    def test_run_entity_logs_debug(self, gaming, caplog):
        gaming.exec = lambda name: None
        server = JczxMcpServer(make_host(gaming), 8765, logging.getLogger("mcp-test"))
        with caplog.at_level(logging.DEBUG, logger="mcp-test"):
            server._do_run_entity("click-a")
        assert any("MCP 工具调用 [run_entity]" in r.message for r in caplog.records)
        assert any("MCP 执行实体 [click-a]" in r.message for r in caplog.records)


class TestInitMcp:
    def test_init_mcp_starts_daemon_thread(self, monkeypatch):
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: "8765")
        cli.logger = logging.getLogger("mcp-init-test")
        started = []

        class FakeThread:
            def __init__(self, target, daemon=False, name=None):
                self.target, self.daemon, self.name = target, daemon, name

            def start(self):
                started.append(self)

        monkeypatch.setattr("jczx.jczxCli.threading.Thread", FakeThread)
        monkeypatch.setattr("jczx.mcpServer.JczxMcpServer",
                            lambda host, port, logger: SimpleNamespace(host=host, port=port, run=lambda: None))
        cli._init_mcp()
        assert len(started) == 1
        assert started[0].daemon is True
        assert started[0].name == "jczx-mcp"
        assert cli._mcp_server.port == 8765

    def test_init_mcp_port_fallback(self, monkeypatch):
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: "abc")  # 非法端口
        cli.logger = logging.getLogger("mcp-init-test")
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name: SimpleNamespace(start=lambda: None))
        monkeypatch.setattr("jczx.mcpServer.JczxMcpServer",
                            lambda host, port, logger: SimpleNamespace(host=host, port=port))
        cli._init_mcp()
        assert cli._mcp_server.port == 8765

    def test_init_mcp_port_fallback_missing_key(self, monkeypatch):
        """Config.txt 缺 mcp.port 键（get_config 抛 KeyError）时应回退默认 8765。"""
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: (_ for _ in ()).throw(KeyError(opt)))
        cli.logger = logging.getLogger("mcp-init-test")
        monkeypatch.setattr("jczx.jczxCli.threading.Thread",
                            lambda target, daemon, name: SimpleNamespace(start=lambda: None))
        monkeypatch.setattr("jczx.mcpServer.JczxMcpServer",
                            lambda host, port, logger: SimpleNamespace(host=host, port=port))
        cli._init_mcp()
        assert cli._mcp_server.port == 8765

    def test_init_mcp_failure_logs_error(self, monkeypatch, caplog):
        cli = object.__new__(JczxCli)
        cli.config = SimpleNamespace(get_config=lambda opt: "8765")
        cli.logger = logging.getLogger("mcp-init-test")

        def boom(host, port, logger):
            raise RuntimeError("端口占用")

        monkeypatch.setattr("jczx.mcpServer.JczxMcpServer", boom)
        with caplog.at_level(logging.ERROR, logger="mcp-init-test"):
            cli._init_mcp()
        assert any("MCP 服务启动失败" in r.message for r in caplog.records)
