import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _get_cjk_font(size: int = 20) -> ImageFont.FreeTypeFont:
    for path in ("C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc",
                 "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


class ScreenAnnotator:
    COLOR = (0, 0, 255)       # BGR 红色
    THICKNESS = 3
    CROSS_SIZE = 25
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE = 0.6
    FONT_THICKNESS = 2
    _PIL_FONT = _get_cjk_font(22)

    @classmethod
    def _draw_label(cls, img, x, y, text):
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        draw.text((x + 4, max(y - 26, 2)), text, font=cls._PIL_FONT, fill=(255, 0, 0))
        img[:] = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    @classmethod
    def draw_click(cls, img, x, y):
        cv2.drawMarker(img, (x, y), cls.COLOR,
                       cv2.MARKER_CROSS, cls.CROSS_SIZE, cls.THICKNESS)
        cls._draw_label(img, x, y, "点击")

    @classmethod
    def draw_match(cls, img, pts, index):
        (x0, y0), (x1, _y0), (_x0, y1), (_x1, _y1) = pts
        cv2.rectangle(img, (x0, y0), (x1, y1), cls.COLOR, cls.THICKNESS)
        cls._draw_label(img, x0, y0, f"匹配:{index}")

    @classmethod
    def draw_swipe(cls, img, x1, y1, x2, y2, label):
        cv2.arrowedLine(img, (x1, y1), (x2, y2), cls.COLOR,
                        cls.THICKNESS, tipLength=0.1)
        cls._draw_label(img, x1, y1, label)

    @classmethod
    def draw_ocr(cls, img, pt_range, text):
        if pt_range is None:
            return
        (x0, y0), (x1, y1) = pt_range
        cv2.rectangle(img, (x0, y0), (x1, y1), cls.COLOR, cls.THICKNESS)
        cls._draw_label(img, x0, y0, f"OCR: {text}")
