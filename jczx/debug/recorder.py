import os
import re
import cv2
from logging import Logger
from cv2.typing import MatLike

from ..CommoneBuilder.CommonBuilder.Android.Adb import MatchTemplete
from .annotator import ScreenAnnotator


class DebugRecorder:
    MODE_OFF = "off"
    MODE_SIMPLE = "simple"
    MODE_ANNOTATED = "annotated"

    def __init__(self, mode: str, output_dir: str, log: Logger):
        self._mode = mode
        self._output_dir = output_dir
        self._index = 1
        self._log = log
        self._annotator = ScreenAnnotator()

    _NUMERIC_PNG = re.compile(r"^\d+\.png$")

    def ensure_dir(self):
        if os.path.isdir(self._output_dir):
            for f in os.listdir(self._output_dir):
                if self._NUMERIC_PNG.match(f):
                    os.remove(os.path.join(self._output_dir, f))
            self._log.debug(f"已清空调试截图目录 {self._output_dir}")
        else:
            os.makedirs(self._output_dir, exist_ok=True)

    def _save(self, img):
        path = os.path.join(self._output_dir, f"{self._index}.png")
        cv2.imwrite(path, img)
        self._log.debug(f"调试截图 #{self._index} 已保存")
        self._index += 1

    def on_step(self, screenshot: MatLike):
        if self._mode == self.MODE_SIMPLE:
            self._save(screenshot)

    def on_match(self, screenshot: MatLike, mt: MatchTemplete):
        if self._mode != self.MODE_ANNOTATED or not mt.matched:
            return
        for idx, pts in enumerate(mt.matchTempletePoints):
            self._annotator.draw_match(screenshot, pts, idx)
        self._save(screenshot)

    def on_click(self, screenshot: MatLike, x: int, y: int):
        if self._mode != self.MODE_ANNOTATED:
            return
        self._annotator.draw_click(screenshot, x, y)
        self._save(screenshot)

    def on_swipe(self, screenshot: MatLike, x1, y1, x2, y2, label: str):
        if self._mode != self.MODE_ANNOTATED:
            return
        self._annotator.draw_swipe(screenshot, x1, y1, x2, y2, label)
        self._save(screenshot)

    def on_ocr(self, screenshot: MatLike, mt: MatchTemplete, text: str):
        if self._mode != self.MODE_ANNOTATED or not mt.matched:
            return
        self._annotator.draw_ocr(screenshot, mt.matchTempletePointRange, text)
        self._save(screenshot)
