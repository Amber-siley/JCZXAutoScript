from cv2.typing import MatLike

class _OCR:
    def readtext(self, img: MatLike, det = True, rec = True, cls = False, bin = False, inv = False) -> list[str]: ...

