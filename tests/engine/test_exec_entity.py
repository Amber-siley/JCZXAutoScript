"""方案 2：_exec_entity 模板流程 — times / testFor 门控 / wait_target / action 链 / testFor_after 重试。"""
from jczx.configEntity import JczxSectionEntity

from tests.engine.fake_device import make_match, patch_clock


def _entity(**kw):
    e = JczxSectionEntity()
    for k, v in kw.items():
        setattr(e, k, v)
    return e


class TestTimes:
    def test_times_repeats_on_exec(self, gaming):
        calls = []
        e = _entity(type="task", times=3)
        gaming._exec_entity(e, lambda ent: calls.append(1), action_chain=False)
        assert calls == [1, 1, 1]


class TestTestForBeforeGate:
    def test_gate_blocks_when_not_visible(self, gaming, monkeypatch):
        patch_clock(monkeypatch, gaming)
        e = _entity(type="task", testFor_before="buttons\\fight.png",
                    testFor_max_wait=0.6, testFor_per=0.8)
        calls = []
        gaming._exec_entity(e, lambda ent: calls.append(1), testFor=True, default_max_wait=0.6)
        assert calls == [], "testFor_before 不可见应跳过实体"

    def test_gate_passes_when_visible(self, gaming):
        gaming.matcher.results["buttons\\fight.png"] = make_match(10, 10, 20, 20)
        e = _entity(type="task", testFor_before="buttons\\fight.png", testFor_max_wait=1.0)
        calls = []
        gaming._exec_entity(e, lambda ent: calls.append(1), testFor=True)
        assert calls == [1]


class TestWaitTarget:
    def test_wait_target_sleep_recorded_on_match(self, gaming):
        gaming.matcher.results["buttons\\giftPackage.png"] = make_match(0, 0, 10, 10)
        e = _entity(type="task", wait_target="buttons\\giftPackage.png",
                    max_wait=2, wait_target_sleep=1.5)
        gaming._exec_entity(e, lambda ent: None)
        assert 1.5 in gaming.token.sleeps, "wait_target 匹配到后应 sleep(wait_target_sleep)"

    def test_wait_target_timeout_continues(self, gaming, monkeypatch):
        patch_clock(monkeypatch, gaming)  # matcher 无该图 → 超时
        e = _entity(type="task", wait_target="buttons\\missing.png", max_wait=0.6)
        gaming._exec_entity(e, lambda ent: None)
        assert 1.5 not in gaming.token.sleeps


class TestActionChain:
    def test_chain_executed_in_order(self, gaming):
        order = []
        gaming.record_step = lambda tag: order.append(tag)
        a = _entity(type="task", action=["step-1", "step-2"])
        s1 = _entity(type="func", func="record_step", args=["first"])
        s2 = _entity(type="func", func="record_step", args=["second"])
        gaming.task_manage.entity_pool["step-1"] = s1
        gaming.task_manage.entity_pool["step-2"] = s2
        gaming.exec(a)
        assert order == ["first", "second"]


class TestTestForAfter:
    def test_retries_when_not_visible(self, gaming):
        """testFor_after 一直不可见 → 每个 times 迭代都重新执行实体。"""
        count = []
        e = _entity(type="task", testFor_after="buttons\\home.png", times=2)
        gaming._exec_entity(e, lambda ent: count.append(1), testFor=True)
        assert len(count) == 2

    def test_no_retry_when_visible(self, gaming):
        gaming.matcher.results["buttons\\home.png"] = make_match(10, 10, 20, 20)
        count = []
        e = _entity(type="task", testFor_after="buttons\\home.png", times=2)
        gaming._exec_entity(e, lambda ent: count.append(1), testFor=True)
        assert len(count) == 2  # 可见则不再重试，times 正常执行
