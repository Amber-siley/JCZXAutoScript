"""方案 2 共享 fixture：FakeDevice 引擎实例。"""
import pytest

from tests.engine.fake_device import FakeMatcher, make_gaming


@pytest.fixture
def gaming(real_config_dir):
    """构造已注入 FakeMatcher/FakeToken 的引擎，附带 matcher/clicks 引用。"""
    matcher = FakeMatcher()
    clicks = []
    g = make_gaming(real_config_dir, matcher=matcher, clicks=clicks)
    return g
