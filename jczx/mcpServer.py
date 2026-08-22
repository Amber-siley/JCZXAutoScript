"""TUI 内嵌 MCP 服务：向 agent 暴露设备控制工具（截图/点击/滑动/拖动）。

服务随 TUI 启动在后台 daemon 线程运行，streamable-http 传输，
agent 经 http://127.0.0.1:{port}/mcp 连接。
"""
import logging
import os

import cv2
from mcp.server import MCPServer
from mcp.server.mcpserver.utilities.types import Image


class JczxMcpServer:
    """包装 MCPServer，注册 4 个设备操作工具，复用 JczxCli/设备现有实现。

    host 需提供: ``host.device``（JCZXGaming 或 None）、``host.logger``。
    """

    def __init__(self, host, port: int, logger: logging.Logger):
        self._host = host
        self._logger = logger
        self._port = port
        self._mcp = MCPServer(
            "jczx-tui",
            instructions=(
                "管理交错战线游戏设备的工具集（需 TUI 运行且设备已连接，所有操作作用于 TUI 当前选中的设备）。\n"
                "当 debug.screenshot.mode 为 annotated 时，click/swipe/drag 会额外保存标注截图到 screenHistory 目录，"
                "操作未生效时可在其中查看操作位置历史。"
            ),
        )
        self._register_tools()

    # ── 工具注册（薄包装委托 _do_*，便于单测）──

    def _register_tools(self):
        @self._mcp.tool()
        def screenshot() -> Image:
            """截取当前设备屏幕并返回 PNG 图片。"""
            return self._do_screenshot()

        @self._mcp.tool()
        def click(target: str, per: float = 0.8) -> str:
            """点击设备屏幕上的目标图片：先用 crop_screenshot 裁切 + save_screenshot 保存的区域截图路径作为 target，工具会模板匹配该图并点击其中心，无需预估坐标。
            当 debug.screenshot.mode 为 annotated 时，会保存标注截图到 screenHistory 目录，显式标出点击位置，可在其中查看操作历史（操作未生效时用于排查）。"""
            return self._do_click(target, per)

        @self._mcp.tool()
        def swipe(x1: int, y1: int, x2: int, y2: int, duration: int = 200) -> str:
            """从 (x1,y1) 滑动到 (x2,y2)，duration 毫秒。当 debug.screenshot.mode 为 annotated 时，会保存标注滑动轨迹的截图到 screenHistory 目录，可在其中查看操作历史（操作未生效时用于排查）。"""
            return self._do_swipe(x1, y1, x2, y2, duration)

        @self._mcp.tool()
        def drag(x1: int, y1: int, x2: int, y2: int, duration: int = 200) -> str:
            """从 (x1,y1) 拖拽到 (x2,y2)，duration 毫秒。当 debug.screenshot.mode 为 annotated 时，会保存标注拖动轨迹的截图到 screenHistory 目录，可在其中查看操作历史（操作未生效时用于排查）。"""
            return self._do_drag(x1, y1, x2, y2, duration)

        @self._mcp.tool()
        def get_resolution() -> dict:
            """获取当前设备分辨率（宽/高）。"""
            return self._do_get_resolution()

        @self._mcp.tool()
        def crop_screenshot(x1: int, y1: int, x2: int, y2: int) -> Image:
            """裁切当前设备画面：左上角 (x1,y1) 到右下角 (x2,y2)，返回裁切后的 PNG 图片。"""
            return self._do_crop_screenshot(x1, y1, x2, y2)

        @self._mcp.tool()
        def save_screenshot(name: str, x1: int | None = None, y1: int | None = None,
                            x2: int | None = None, y2: int | None = None) -> str:
            """保存当前画面为 PNG 到 template 目录（与截图任务保存路径一致）。name 为文件名（不含扩展名）；可选 x1,y1,x2,y2 裁切区域，缺省保存全屏。"""
            return self._do_save_screenshot(name, x1, y1, x2, y2)

        @self._mcp.tool()
        def get_screenshot_mode() -> str:
            """获取当前 TUI 截图模式（off=关闭 / simple=连续截图 / annotated=标注截图）。"""
            return self._do_get_screenshot_mode()

        @self._mcp.tool()
        def run_entity(args: list[str]) -> str:
            """按 section 名称执行一个或多个实体（task/click/match/func/method/call 等），按列表顺序依次执行。

常用实体（均可直接作为 args 元素）：
- goto-home：返回主界面
- click-center / click-upcenter：点击屏幕中心 / 中上部
- wait-1 / wait-2 / wait-5：等待 1 / 2 / 5 秒
- click-get-item：获取物品
- auto-fight：自动战斗
- emu：启动模拟器
- launch-game：启动游戏
- task-receive-everyday：领取每日礼包
- task-receive-mail：领取邮件礼包
- task-receive-dayAndWeek：领取常规任务奖励
- task-receive-ExplorationGuidelines：领取勘探指南
- task-get-ore：领取矿场矿物
- task-delivery-order：自动交付订单
- jjc-simulate：竞技场日常
- goto-inllusion：虚影周本
- task-favor：竞技场刷好感
- screenshot-task：截图

执行任务实体时无需关注中间过程：大多数任务实体会自行完成导航与操作，并在执行完成后自动返回主界面；直接执行即可。"""
            return self._do_run_entity(*args)

    # ── 工具实现（可直接单测）──

    def _do_screenshot(self) -> Image:
        device = self._device()
        self._logger.debug("MCP 工具调用 [screenshot]")
        ok, buf = cv2.imencode(".png", device.screenshot())
        if not ok:
            raise RuntimeError("截图 PNG 编码失败")
        self._logger.debug(f"MCP 工具调用 [screenshot] 完成 -> {len(buf)} 字节 PNG")
        return Image(data=buf.tobytes(), format="png")

    def _do_click(self, target, per=0.8) -> str:
        device = self._device()
        self._logger.debug(f"MCP 工具调用 [click] target={target} per={per}")
        self._warn_if_busy("点击")
        path = self._resolve_target_path(target)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError(f"点击目标图片无法加载: {target}")
        centers = device.findImageCenterLocations(img, per=per)
        if not centers:
            raise RuntimeError(f"屏幕上未匹配到目标图片: {target}")
        cx, cy = centers[0]
        device.click(cx, cy)
        self._logger.debug(f"MCP 工具调用 [click] 完成 -> 已点击目标 {target} 中心 ({cx}, {cy})")
        return f"已点击目标 {target} 中心 ({cx}, {cy})"

    def _resolve_target_path(self, target: str) -> str:
        """解析点击目标图片路径：绝对路径直接用，相对路径经 fm 基于 work_path 解析。"""
        if os.path.isabs(target):
            return target
        fm = getattr(self._host, "fm", None)
        return fm.join_p(target) if fm is not None else os.path.join(os.getcwd(), target)

    def _do_swipe(self, x1, y1, x2, y2, duration=200) -> str:
        device = self._device()
        self._logger.debug(f"MCP 工具调用 [swipe] ({x1},{y1}) -> ({x2},{y2}) duration={duration}")
        self._warn_if_busy("滑动")
        device.swipe(x1, y1, x2, y2, duration)
        self._logger.debug(f"MCP 工具调用 [swipe] 完成 -> 已滑动 ({x1},{y1}) -> ({x2},{y2})")
        return f"已滑动 ({x1},{y1}) -> ({x2},{y2})"

    def _do_drag(self, x1, y1, x2, y2, duration=200) -> str:
        device = self._device()
        self._logger.debug(f"MCP 工具调用 [drag] ({x1},{y1}) -> ({x2},{y2}) duration={duration}")
        self._warn_if_busy("拖动")
        device.dragAndDrop(x1, y1, x2, y2, duration)
        self._logger.debug(f"MCP 工具调用 [drag] 完成 -> 已拖动 ({x1},{y1}) -> ({x2},{y2})")
        return f"已拖动 ({x1},{y1}) -> ({x2},{y2})"

    def _do_get_resolution(self) -> dict:
        device = self._device()
        self._logger.debug("MCP 工具调用 [get_resolution]")
        size = getattr(device, "size", None)
        if not size or len(size) < 2:
            raise RuntimeError("设备分辨率未知")
        self._logger.debug(f"MCP 工具调用 [get_resolution] 完成 -> {size[0]}x{size[1]}")
        return {"width": int(size[0]), "height": int(size[1])}

    def _do_crop_screenshot(self, x1, y1, x2, y2) -> Image:
        device = self._device()
        self._logger.debug(f"MCP 工具调用 [crop_screenshot] ({x1},{y1}) -> ({x2},{y2})")
        img = device.screenshot()
        h, w = img.shape[:2]
        # 越界坐标裁剪到画面内，宽容 agent 视觉坐标的小偏差
        x1, y1 = max(int(x1), 0), max(int(y1), 0)
        x2, y2 = min(int(x2), w), min(int(y2), h)
        if x2 <= x1 or y2 <= y1:
            raise RuntimeError(f"裁切区域无效: ({x1},{y1})-({x2},{y2}) 超出画面 {w}x{h}")
        crop = img[y1:y2, x1:x2]
        ok, buf = cv2.imencode(".png", crop)
        if not ok:
            raise RuntimeError("截图 PNG 编码失败")
        self._logger.debug(f"MCP 工具调用 [crop_screenshot] 完成 -> {len(buf)} 字节 PNG ({x2-x1}x{y2-y1})")
        return Image(data=buf.tobytes(), format="png")

    def _do_save_screenshot(self, name: str, x1=None, y1=None, x2=None, y2=None) -> str:
        device = self._device()
        self._logger.debug(f"MCP 工具调用 [save_screenshot] name={name} crop=({x1},{y1})-({x2},{y2})")
        img = device.screenshot()
        has_crop = any(v is not None for v in (x1, y1, x2, y2))
        if has_crop:
            h, w = img.shape[:2]
            x1 = max(int(x1 if x1 is not None else 0), 0)
            y1 = max(int(y1 if y1 is not None else 0), 0)
            x2 = min(int(x2 if x2 is not None else w), w)
            y2 = min(int(y2 if y2 is not None else h), h)
            if x2 <= x1 or y2 <= y1:
                raise RuntimeError(f"裁切区域无效: ({x1},{y1})-({x2},{y2}) 超出画面 {w}x{h}")
            img = img[y1:y2, x1:x2]
        path = self._resolve_save_path(name)
        if not cv2.imwrite(path, img):
            raise RuntimeError(f"截图保存失败: {path}")
        self._logger.debug(f"MCP 工具调用 [save_screenshot] 完成 -> {path}")
        return f"截图已保存到 {path}"

    def _resolve_save_path(self, name: str) -> str:
        """保存到 template/{name}.png，与截图任务路径一致。"""
        fm = getattr(self._host, "fm", None)
        base = fm.join_p("template") if fm is not None else os.path.join(os.getcwd(), "template")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, f"{name}.png")

    def _do_get_screenshot_mode(self) -> str:
        self._logger.debug("MCP 工具调用 [get_screenshot_mode]")
        config = getattr(self._host, "config", None)
        mode = "off"
        if config is not None:
            try:
                mode = config.get_config(opt="debug.screenshot.mode") or "off"
            except Exception:
                mode = "off"
        self._logger.debug(f"MCP 工具调用 [get_screenshot_mode] 完成 -> {mode}")
        return mode

    def _do_run_entity(self, *names: str) -> str:
        device = self._device()
        self._logger.debug(f"MCP 工具调用 [run_entity] names={names}")
        self._warn_if_busy("执行实体")
        for name in names:
            if not name or not isinstance(name, str):
                raise RuntimeError(f"实体名称无效: {name!r}")
            self._logger.info(f"MCP 执行实体 [{name}]")
            device.exec(name)
        self._logger.debug(f"MCP 工具调用 [run_entity] 完成 -> {names}")
        return f"已执行实体: {', '.join(names)}"

    # ── 辅助 ──

    def _device(self):
        device = getattr(self._host, "device", None)
        if device is None:
            raise RuntimeError("设备未连接")
        return device

    def _warn_if_busy(self, action: str) -> None:
        mgr = getattr(self._device(), "_exec_mgr", None)
        if mgr is not None and getattr(mgr, "is_running", lambda: False)():
            self._logger.warning(f"agent 在任务执行期间调用 MCP 工具[{action}]，可能干扰自动化")

    # ── 生命周期 ──

    def run(self) -> None:
        """在 daemon 线程中运行 streamable-http 服务（阻塞直到进程退出）。"""
        import asyncio
        asyncio.run(self._mcp.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=self._port,
        ))
