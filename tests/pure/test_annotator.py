"""ScreenAnnotator 标注坐标扩展：点击/滑动标注应产生像素变化（标注生效）。"""
import numpy as np

from jczx.debug.annotator import ScreenAnnotator


class TestAnnotatorCoordinates:
    def test_draw_click_marks_image(self):
        img = np.zeros((100, 100, 3), np.uint8)
        out = img.copy()
        ScreenAnnotator.draw_click(out, 30, 40)
        assert not (out == img).all(), "点击标注应产生像素变化"

    def test_draw_swipe_marks_image(self):
        img = np.zeros((100, 100, 3), np.uint8)
        out = img.copy()
        ScreenAnnotator.draw_swipe(out, 10, 20, 80, 90, "滑动")
        assert not (out == img).all(), "滑动标注应产生像素变化"
