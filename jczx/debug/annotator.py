import cv2


class ScreenAnnotator:
    COLOR = (0, 255, 0)
    THICKNESS = 2
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE = 0.5
    CROSS_SIZE = 10

    @classmethod
    def _draw_label(cls, img, x, y, text):
        cv2.putText(img, text, (x + 4, y - 4),
                    cls.FONT, cls.FONT_SCALE, cls.COLOR, 1)

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
