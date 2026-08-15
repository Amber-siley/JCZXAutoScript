"""方案 2：exec_match — action 变换、级联搜索变换后区域、标注时机（on_match 收到变换后点）。

使用真实配置 receive.txt 中的实体：
  match-exploration-to-new        target=ExplorationGuidelines, action=left|1,up-M|10,left-M|-50
  matched-exploration-guidelines-new  match 引用上述实体 + target=hasNew（级联）
"""
from tests.engine.fake_device import RecordingRecorder, make_match

# make_match(10,10,20,20) 经 left|1,up-M|10,left-M|-50 变换后的预期
TRANSFORMED = ((50, 0), (10, 0), (50, 20), (10, 20))


class TestTransform:
    def test_transform_applied_to_result(self, gaming):
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        mt = gaming.exec_match("match-exploration-to-new")
        assert mt is not None
        assert mt.matchTempletePoint[0] == (50, 0)
        assert mt.matchTempletePoint[3] == (10, 20)
        assert mt.matchTempleteCenterPoint == (30, 10)

    def test_no_action_match_keeps_raw_points(self, gaming):
        """matched-exploration-guidelines-new 自身无 action，级联结果保持原始匹配区域。"""
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming.matcher.results["locations\\hasNew.png"] = make_match(15, 15, 25, 25)
        outer = gaming.exec_match("matched-exploration-guidelines-new")
        assert outer is not None
        assert outer.matchTempletePoint[0] == (15, 15)


class TestCascade:
    def test_cascade_searches_in_transformed_region(self, gaming):
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming.matcher.results["locations\\hasNew.png"] = make_match(15, 15, 25, 25)
        outer = gaming.exec_match("matched-exploration-guidelines-new")
        assert outer is not None
        img, cut, per = gaming.matcher.calls[-1]
        assert img == "locations\\hasNew.png"
        assert cut == ((50, 0), (10, 20)), "级联应在 action 变换后的区域（cutPoints）内搜索"
        assert per == 0.8


class TestAnnotationTiming:
    def test_on_match_receives_transformed_points(self, gaming):
        """回归：on_match 应在 action 变换之后记录，标注框=变换后区域。"""
        gaming._recorder = RecordingRecorder()
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming.exec_match("match-exploration-to-new")
        assert gaming._recorder.match_points[-1] == [TRANSFORMED]
