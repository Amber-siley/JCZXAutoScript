"""方案 1（纯逻辑）：ScreenshotCache TTL / invalidate / TTL=0 语义。"""
import time

import numpy as np

from jczx.jczxCli import ScreenshotCache


def _make_cache(ttl_ms, counter):
    def capture():
        counter.append(1)
        return np.zeros((10, 10, 3), np.uint8)

    return ScreenshotCache(screenshot_fn=capture, ttl_ms=ttl_ms)


class TestTtlBehavior:
    def test_within_ttl_reuses_frame(self):
        counter = []
        cache = _make_cache(ttl_ms=1000, counter=counter)
        cache.screenshot()
        cache.screenshot()
        assert len(counter) == 1, "TTL 内同帧不应重复截图"

    def test_ttl_expired_recaptures(self):
        counter = []
        cache = _make_cache(ttl_ms=10, counter=counter)
        cache.screenshot()
        time.sleep(0.02)
        cache.screenshot()
        assert len(counter) == 2, "TTL 过期应重新截图"

    def test_invalidate_forces_refresh(self):
        counter = []
        cache = _make_cache(ttl_ms=1000, counter=counter)
        cache.screenshot()
        cache.invalidate()
        cache.screenshot()
        assert len(counter) == 2, "invalidate 后应强制重新截图"

    def test_ttl_zero_always_refresh(self):
        """回归 Fix B：screen_cache_ttl=0（禁用缓存）应每次读取都重新截图。"""
        counter = []
        cache = _make_cache(ttl_ms=0, counter=counter)
        cache.screenshot()
        cache.screenshot()
        cache.screenshot()
        assert len(counter) == 3, "TTL=0 表示禁用缓存，每次都应重新截图"

    def test_gray_screenshot_is_grayscale(self):
        counter = []
        cache = _make_cache(ttl_ms=1000, counter=counter)
        gray = cache.gray_screenshot()
        assert gray.ndim == 2
        assert gray.shape == (10, 10)
