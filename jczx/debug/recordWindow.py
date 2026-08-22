"""TUI 记录窗口：tkinter 实时画面 + 手势识别 + JSON 记录。

运行于独立子线程（tkinter mainloop 阻塞），复用 JCZXGaming 的设备操作
与 DebugRecorder 的标注截图（annotated 模式）。手势判定抽为顶层纯函数。
"""
import json
import math
import os
import time
import tkinter as tk

import cv2
from PIL import Image as PILImage, ImageTk


def classify_gesture(press_t, press_x, press_y, release_t, release_x, release_y,
                     move_start_t, click_move_threshold=15, hold_threshold=300):
    """按位移与移动前停留时长判定手势类型。

    - 位移 < click_move_threshold → "click"
    - 位移 ≥ click_move_threshold 且移动前停留 ≥ hold_threshold ms → "drag"
    - 其余 → "swipe"
    """
    dist = math.hypot(release_x - press_x, release_y - press_y)
    if dist < click_move_threshold:
        return "click"
    if move_start_t is not None and (move_start_t - press_t) * 1000 >= hold_threshold:
        return "drag"
    return "swipe"


def build_action_entry(seq, gesture, x, y, x2, y2, duration, time_str, screenshot):
    """构造单条操作记录。click 时 x2/y2/duration 为 None。"""
    return {
        "seq": seq,
        "type": gesture,
        "x": x, "y": y,
        "x2": x2, "y2": y2,
        "duration": duration,
        "time": time_str,
        "screenshot": screenshot,
    }


class RecordWindow:
    """tkinter 记录窗口：实时画面 + 手势捕获 + JSON 记录。"""

    CANVAS_W = 800
    CANVAS_H = 600

    def __init__(self, device, config, output_dir, log):
        self._device = device
        self._config = config
        self._output_dir = output_dir
        self._log = log
        self._session_id = time.strftime("%Y%m%d_%H%M%S")
        self._started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self._actions = []
        self._seq = 1
        self._scale = None
        self._photo = None
        self._press_t = None
        self._press_xy = None
        self._move_start_t = None
        self._cur_xy = None
        self._last_gesture = None
        self._root = None
        self._click_move_threshold = self._cfg_int("record.click_move_threshold", 15)
        self._hold_threshold = self._cfg_int("record.hold_threshold", 300)
        self._refresh_interval = self._cfg_int("record.refresh_interval", 200)
        self._sync_mode = self._cfg_str("record.sync.mode", "screenshot")

    def _cfg_int(self, opt, default):
        """读取 int 配置，缺键/非法值回退默认。"""
        try:
            return int(self._config.get_config(opt=opt))
        except (KeyError, TypeError, ValueError):
            return default

    def _cfg_str(self, opt, default):
        """读取 str 配置，缺键/非法值回退默认。"""
        try:
            return self._config.get_config(opt=opt) or default
        except (KeyError, TypeError, ValueError):
            return default

    def _get_device_size(self):
        """窗口尺寸与设备分辨率一致；设备尺寸未知时回退 CANVAS_W/H。"""
        size = getattr(self._device, "size", None)
        if size and len(size) >= 2 and size[0] and size[1]:
            return int(size[0]), int(size[1])
        return self.CANVAS_W, self.CANVAS_H

    def run(self):
        """创建 Tk 窗口并 mainloop（阻塞直到窗口关闭）。"""
        cw, ch = self._get_device_size()
        self._root = tk.Tk()
        self._root.title(f"记录 - {self._session_id}")
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._canvas = tk.Canvas(self._root, width=cw, height=ch, bg="black")
        self._canvas.pack()
        self._status = tk.Label(self._root, text="", anchor="w")
        self._status.pack(fill="x")
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._refresh()
        self._root.mainloop()

    def _take_frame(self):
        """按同步模式取设备画面帧。

        u2 模式绕过截图缓存，直接走 u2 minicap 高频截图；失败或无 u2 时回退截图同步。
        """
        if self._sync_mode == "u2":
            u2d = getattr(self._device, "u2_device", None)
            if u2d is not None:
                try:
                    return u2d.screenshot(format="opencv")
                except Exception as e:
                    self._log.warning(f"u2 截图失败，回退截图同步: {e}")
        return self._device.screenshot()

    def _refresh(self):
        """定时拉取设备画面并显示到 Canvas。"""
        try:
            img = self._take_frame()
            h, w = img.shape[:2]
            cw, ch = self._get_device_size()
            scale = min(cw / w, ch / h)
            self._scale = scale
            # 窗口与设备分辨率一致时原图显示（scale≈1）；尺寸不匹配才缩放
            if scale < 1.0:
                display = cv2.resize(img, (max(int(w * scale), 1), max(int(h * scale), 1)))
            else:
                display = img
            rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
            self._photo = ImageTk.PhotoImage(PILImage.fromarray(rgb))
            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
            self._status.config(
                text=f"{w}x{h}  缩放 {scale:.2f}  操作 {self._seq - 1}  {self._last_gesture or ''}"
            )
        except Exception as e:
            self._log.warning(f"记录窗口刷新失败: {e}")
        self._root.after(self._refresh_interval, self._refresh)

    def _on_press(self, event):
        self._press_t = time.time()
        self._press_xy = (event.x, event.y)
        self._move_start_t = None
        self._cur_xy = (event.x, event.y)

    def _on_motion(self, event):
        if self._move_start_t is None:
            self._move_start_t = time.time()
        self._cur_xy = (event.x, event.y)

    def _on_release(self, event):
        if self._press_xy is None:
            return
        px, py = self._press_xy
        gesture = classify_gesture(
            self._press_t, px, py, time.time(), event.x, event.y,
            self._move_start_t, self._click_move_threshold, self._hold_threshold,
        )
        self._apply_gesture(gesture, px, py, event.x, event.y)
        self._press_xy = None

    def _apply_gesture(self, gesture, px1, py1, px2, py2):
        """设备操作（复用 DebugRecorder 标注截图）+ 记录条目。"""
        x1 = round(px1 / self._scale) if self._scale else px1
        y1 = round(py1 / self._scale) if self._scale else py1
        x2 = round(px2 / self._scale) if self._scale else px2
        y2 = round(py2 / self._scale) if self._scale else py2
        time_str = time.strftime("%H:%M:%S")
        if gesture == "click":
            self._device.click(x1, y1)
            entry = build_action_entry(self._seq, "click", x1, y1, None, None, None,
                                       time_str, self._last_saved())
        elif gesture == "swipe":
            self._device.swipe(x1, y1, x2, y2, 200)
            entry = build_action_entry(self._seq, "swipe", x1, y1, x2, y2, 200,
                                       time_str, self._last_saved())
        else:  # drag
            self._device.dragAndDrop(x1, y1, x2, y2, 200)
            entry = build_action_entry(self._seq, "drag", x1, y1, x2, y2, 200,
                                       time_str, self._last_saved())
        self._actions.append(entry)
        self._seq += 1
        self._last_gesture = gesture
        self._log.info(f"记录操作 [{gesture}] ({x1},{y1}) -> ({x2},{y2})")

    def _last_saved(self):
        """读取 DebugRecorder 最近保存的标注截图文件名。"""
        recorder = getattr(self._device, "_recorder", None)
        return getattr(recorder, "last_saved", None)

    def _close(self):
        """会话结束，写 JSON。"""
        if self._actions:
            data = {
                "session": self._session_id,
                "device": getattr(self._device, "device_id", ""),
                "resolution": list(self._device.size) if getattr(self._device, "size", None) else [],
                "started_at": self._started_at,
                "actions": self._actions,
            }
            path = os.path.join(self._output_dir, f"record_{self._session_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log.info(f"记录已保存: {path}")
        else:
            self._log.info("无操作，未生成记录")
        if self._root is not None:
            self._root.destroy()
