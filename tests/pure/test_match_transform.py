"""方案 1（纯逻辑）：MatchTemplete.transform 几何变换数学。"""
import numpy as np

from jczx.CommonBuilder.CommonBuilder.Android.Adb import MatchTemplete


def _make_mt():
    """模板位于 (10,10)-(20,20)，尺寸 10x10。"""
    gray = np.zeros((100, 100), np.uint8)
    return MatchTemplete(
        baseGrayScreenshot=gray,
        grayScreenshot=gray,
        templeteSize=(10, 10),
        matchTempletePoints=[((10, 10), (20, 10), (10, 20), (20, 20))],
        matchTempleteCenterPoints=[(15, 15)],
    )


class TestShiftOperators:
    def test_left_1(self):
        mt = _make_mt().transform("left|1")  # shift_x = -10
        assert mt.matchTempletePoint[0] == (0, 10)
        assert mt.matchTempletePoint[3] == (10, 20)

    def test_right_half(self):
        mt = _make_mt().transform("right|0.5")  # shift_x = +5
        assert mt.matchTempletePoint[0] == (15, 10)
        assert mt.matchTempletePoint[3] == (25, 20)

    def test_up_1(self):
        mt = _make_mt().transform("up|1")  # shift_y = -10
        assert mt.matchTempletePoint[0] == (10, 0)

    def test_down_0_5(self):
        mt = _make_mt().transform("down|0.5")  # shift_y = +5
        assert mt.matchTempletePoint[0] == (10, 15)


class TestMarginOperators:
    def test_up_m_10(self):
        mt = _make_mt().transform("up-M|10")  # edge_y0 = -10
        assert mt.matchTempletePoint[0] == (10, 0)
        assert mt.matchTempletePoint[3] == (20, 20)  # 下边不动

    def test_left_m_minus50(self):
        mt = _make_mt().transform("left-M|-50")  # edge_x0 = +50
        assert mt.matchTempletePoint[0] == (60, 10)
        assert mt.matchTempletePoint[1] == (20, 10)  # x1 不变

    def test_right_m_20(self):
        mt = _make_mt().transform("right-M|20")  # edge_x1 = +20
        assert mt.matchTempletePoint[3] == (40, 20)


class TestScaleOperators:
    def test_reW_2(self):
        mt = _make_mt().transform("reW|2")  # 宽翻倍
        assert mt.matchTempletePoint[3] == (30, 20)
        assert mt.matchTempletePoint[0] == (10, 10)


class TestChainingAndInvalid:
    def test_chain_transforms(self):
        mt = _make_mt()
        mt.transform("left|1").transform("up-M|10")
        assert mt.matchTempletePoint[0] == (0, 0)
        assert mt.matchTempletePoint[3] == (10, 20)

    def test_invalid_op_returns_self_unchanged(self):
        mt = _make_mt()
        before = mt.matchTempletePoints
        assert mt.transform("foo|1") is mt
        assert mt.matchTempletePoints == before

    def test_invalid_value_returns_self_unchanged(self):
        mt = _make_mt()
        before = mt.matchTempletePoints
        assert mt.transform("left|abc") is mt
        assert mt.matchTempletePoints == before

    def test_no_pipe_returns_self_unchanged(self):
        mt = _make_mt()
        before = mt.matchTempletePoints
        assert mt.transform("left") is mt
        assert mt.matchTempletePoints == before

    def test_center_and_range_updated(self):
        mt = _make_mt().transform("left|1")
        assert mt.matchTempleteCenterPoint == (5, 15)
        assert mt.matchTempletePointRange == ((0, 10), (10, 20))
