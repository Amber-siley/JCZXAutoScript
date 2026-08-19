"""方案 2：exec_match — action 变换、级联搜索外扩区域、标注时机（on_match 收到变换后点）。

使用真实配置 receive.txt 中的通用 method+call 实体：
  if-around-click      method：params base,neighbor；neighbor 默认 locations\hasNew.png
  match-around-10      匹配 %{base} 后边向外扩 10px（up-M|10,down-M|10,left-M|10,right-M|10）
  matched-around       级联：在 match-around-10 区域搜 %{neighbor}
  call-exploration-around  base=buttons\ExplorationGuidelines.png
"""
from jczx.configEntity import JczxSectionEntity

from tests.engine.fake_device import RecordingRecorder, make_match

# make_match(10,10,20,20) 经边外扩10px 变换后的预期
EXPANDED = ((0, 0), (30, 0), (0, 30), (30, 30))


def _entity(**kw):
    e = JczxSectionEntity()
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _set_ctx(gaming, expand=10):
    gaming._context["base"] = "buttons\\ExplorationGuidelines.png"
    for k in ("expand_up", "expand_down", "expand_left", "expand_right"):
        gaming._context[k] = str(expand)


class TestTransform:
    def test_expand_edges_transform_applied(self, gaming):
        """match-around target=%{base} + action 占位符 %{expand} 解析后边外扩。"""
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        _set_ctx(gaming)  # base + expand=10
        mt = gaming.exec_match("match-around")
        assert mt is not None
        assert mt.matchTempletePoint[0] == (0, 0)
        assert mt.matchTempletePoint[3] == (30, 30)
        assert mt.matchTempleteCenterPoint == (15, 15)

    def test_asymmetric_expand(self, gaming):
        """每边独立扩展：仅上扩 10，其余 0。"""
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming._context["base"] = "buttons\\ExplorationGuidelines.png"
        gaming._context.update(expand_up="10", expand_down="0", expand_left="0", expand_right="0")
        mt = gaming.exec_match("match-around")
        assert mt is not None
        assert mt.matchTempletePoint[0] == (10, 0)
        assert mt.matchTempletePoint[3] == (20, 20)

    def test_click_targets_button_center(self, gaming):
        """method+call：命中后点击基础图中心 (15,15)，而非外扩区域中心。"""
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming.matcher.results["locations\\hasNew.png"] = make_match(15, 15, 25, 25)
        gaming.exec("call-exploration-around")
        assert gaming.clicks == [(15, 15)], f"应点击按钮中心 (15,15)，实际 {gaming.clicks}"


class TestCascade:
    def test_cascade_searches_in_expanded_region(self, gaming):
        """method+call：matched-around 在 expand 参数指定的外扩区域（cutPoints）内级联搜索 neighbor。"""
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming.matcher.results["locations\\hasNew.png"] = make_match(15, 15, 25, 25)
        call = _entity(type="call", fn="if-around-click",
                       args=["base=buttons\\ExplorationGuidelines.png",
                             "expand_up=10", "expand_down=10", "expand_left=10", "expand_right=10"])
        gaming.task_manage.entity_pool["call-exp"] = call
        gaming.exec("call-exp")
        cascade = [c for c in gaming.matcher.calls if c[0] == "locations\\hasNew.png"]
        assert cascade, "应有 hasNew 级联匹配调用"
        img, cut, per = cascade[-1]
        assert cut == ((0, 0), (30, 30)), "级联应在 expand 指定的外扩区域（cutPoints）内搜索"
        assert per == 0.8
        assert gaming.clicks, "hasNew 命中应触发点击"

    def test_then_entity_override(self, gaming):
        """method+call：then_entity 可覆盖默认 click-target，命中后执行自定义实体。"""
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        gaming.matcher.results["locations\\hasNew.png"] = make_match(15, 15, 25, 25)
        hits = []
        gaming.record_hit = lambda: hits.append("hit")
        rec = _entity(type="func", func="record_hit")
        call = _entity(type="call", fn="if-around-click",
                       args=["base=buttons\\ExplorationGuidelines.png", "then_entity=record-hit"])
        gaming.task_manage.entity_pool["record-hit"] = rec
        gaming.task_manage.entity_pool["call-custom"] = call
        gaming.exec("call-custom")
        assert hits == ["hit"], "应执行自定义 then_entity"
        assert gaming.clicks == [], "默认 click-target 不应执行"


class TestPerPlaceholder:
    def test_per_resolves_context_placeholder(self, gaming):
        """match 的 per 支持 %{} 占位符（此前直接传 e.per 字符串会破坏 cv2 匹配）。"""
        e = _entity(type="match", target="buttons\\Some.png", per="%{threshold}")
        gaming.task_manage.entity_pool["per-match"] = e
        gaming._context["threshold"] = "0.6"
        gaming.matcher.results["buttons\\Some.png"] = make_match(0, 0, 10, 10)
        gaming.exec_match("per-match")
        assert gaming.matcher.calls[-1][2] == 0.6, "per 应解析为 float 0.6"


class TestBoolContextOnFailure:
    def test_match_failure_writes_false(self, gaming):
        """context_type: bool 的 match 实体失败时应写 False（覆盖旧值，不悬空）。"""
        e = _entity(type="match", target="buttons\\missing.png",
                    context_key="found", context_type="bool")
        gaming.task_manage.entity_pool["bool-match"] = e
        gaming._context["found"] = True  # 残留旧值
        gaming.exec("bool-match")
        assert gaming._context["found"] is False

    def test_match_success_writes_true(self, gaming):
        e = _entity(type="match", target="buttons\\Some.png",
                    context_key="found", context_type="bool")
        gaming.task_manage.entity_pool["bool-match"] = e
        gaming.matcher.results["buttons\\Some.png"] = make_match(0, 0, 10, 10)
        gaming.exec("bool-match")
        assert gaming._context["found"] is True

    def test_non_bool_none_result_not_written(self, gaming):
        """非 bool 类型 result=None 时仍不写（保留原语义，防回归）。"""
        e = _entity(type="match", target="buttons\\missing.png",
                    context_key="cnt", context_type="int")
        gaming.task_manage.entity_pool["int-match"] = e
        gaming._context["cnt"] = 42
        gaming.exec("int-match")
        assert gaming._context["cnt"] == 42


class TestSleepPlaceholder:
    def test_breakpoint_sleep_resolves_context_placeholder(self, gaming):
        """exec_click break_point 路径的 sleep 应解析 %{} 占位符。"""
        e = _entity(type="click", target="missing\\never.png", break_point="on",
                    max_wait=0, sleep="%{click_sleep}")
        gaming.task_manage.entity_pool["bp-click"] = e
        gaming._context["click_sleep"] = "3"
        gaming.exec("bp-click")
        assert 3.0 in gaming.token.sleeps

    def test_breakpoint_sleep_resolves_exec_placeholder(self, gaming):
        """sleep 也支持 @{} 执行占位符。"""
        gaming.record_get = lambda: "1.5"
        f = _entity(type="func", func="record_get")
        gaming.task_manage.entity_pool["get-sleep"] = f
        e = _entity(type="click", target="missing\\never.png", break_point="on",
                    max_wait=0, sleep="@{get-sleep}")
        gaming.task_manage.entity_pool["bp-click2"] = e
        gaming.exec("bp-click2")
        assert 1.5 in gaming.token.sleeps


class TestAnnotationTiming:
    def test_on_match_receives_transformed_points(self, gaming):
        """回归：on_match 应在 action 变换之后记录，标注框=变换后区域。"""
        gaming._recorder = RecordingRecorder()
        gaming.matcher.results["buttons\\ExplorationGuidelines.png"] = make_match(10, 10, 20, 20)
        _set_ctx(gaming)
        gaming.exec_match("match-around")
        assert gaming._recorder.match_points[-1] == [EXPANDED]
