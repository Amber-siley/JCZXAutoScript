"""classify_gesture 三态判定 + build_action_entry 条目构造。"""
from jczx.debug.recordWindow import build_action_entry, classify_gesture


class TestClassifyGesture:
    def test_small_move_is_click(self):
        assert classify_gesture(0, 10, 10, 0.1, 12, 12, 0.02, 15, 300) == "click"

    def test_move_without_hold_is_swipe(self):
        assert classify_gesture(0, 10, 10, 0.4, 200, 200, 0.01, 15, 300) == "swipe"

    def test_move_with_hold_is_drag(self):
        assert classify_gesture(0, 10, 10, 0.8, 200, 200, 0.5, 15, 300) == "drag"

    def test_move_distance_equal_threshold_is_not_click(self):
        assert classify_gesture(0, 0, 0, 0.1, 15, 0, 0.05, 15, 300) == "swipe"

    def test_hold_equal_threshold_is_drag(self):
        assert classify_gesture(0, 0, 0, 0.8, 200, 0, 0.3, 15, 300) == "drag"


class TestBuildActionEntry:
    def test_click_entry(self):
        e = build_action_entry(1, "click", 100, 200, None, None, None, "15:30:01", "12.png")
        assert e == {
            "seq": 1, "type": "click", "x": 100, "y": 200,
            "x2": None, "y2": None, "duration": None,
            "time": "15:30:01", "screenshot": "12.png",
        }

    def test_swipe_entry_has_end_and_duration(self):
        e = build_action_entry(2, "swipe", 10, 20, 30, 40, 200, "15:30:02", "13.png")
        assert e["type"] == "swipe"
        assert e["x2"] == 30 and e["y2"] == 40 and e["duration"] == 200
