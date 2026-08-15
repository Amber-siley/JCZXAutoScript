"""方案 1（纯逻辑）：PlaceholderResolver 四类占位符解析顺序与条件求值。"""
from jczx.jczxCli import PlaceholderResolver


class StubTaskManage:
    """只实现 _resolve_placeholder，供 ${...} 解析。"""

    def __init__(self, config_values: dict):
        self._values = config_values

    def _resolve_placeholder(self, arg: str, task_key: str = None) -> str:
        return self._values.get(arg, "")


class StubGaming:
    def __init__(self, *, exec_results=None, context=None, config_values=None):
        self._context = dict(context or {})
        self.exec = lambda k: (exec_results or {}).get(k, False)
        self.task_manage = StubTaskManage(config_values or {})


def _resolver(stub: StubGaming) -> PlaceholderResolver:
    return PlaceholderResolver(stub)


class TestConfigPlaceholder:
    def test_resolves_section_option(self):
        g = StubGaming(config_values={"${cfg:key}": "hello"})
        r = _resolver(g)
        assert r._resolve_config("${cfg:key}", "") == "hello"


class TestExecPlaceholder:
    def test_calls_gaming_exec(self):
        g = StubGaming(exec_results={"get-x": 42})
        assert _resolver(g).resolve("@{get-x}", "") == "42"


class TestContextPlaceholder:
    def test_reads_context(self):
        g = StubGaming(context={"name": "abc"})
        assert _resolver(g).resolve("%{name}", "") == "abc"

    def test_missing_context_empty(self):
        g = StubGaming(context={})
        assert _resolver(g).resolve("%{missing}", "") == ""


class TestResolutionOrder:
    def test_config_then_exec_then_context(self):
        g = StubGaming(
            exec_results={"get-b": "B"},
            context={"c": "C"},
            config_values={"${a}": "A"},
        )
        r = _resolver(g)
        assert r.resolve("${a}-@{get-b}-%{c}", "") == "A-B-C"


class TestCondition:
    def test_compare_exec_result(self):
        g = StubGaming(exec_results={"get-times": 5})
        r = _resolver(g)
        assert r.resolve("&{@{get-times} > 1}", "") == "True"
        assert r.resolve("&{@{get-times} <= 1}", "") == "False"

    def test_compare_context(self):
        g = StubGaming(context={"combat_power": 30000})
        r = _resolver(g)
        assert r.resolve("&{%{combat_power} > 25000}", "") == "True"

    def test_logical_or(self):
        g = StubGaming(exec_results={"a": 0, "b": 1})
        r = _resolver(g)
        assert r.resolve("&{@{a} > 0 | @{b} > 0}", "") == "True"

    def test_evaluate_condition_bare_entity(self):
        g = StubGaming(exec_results={"some-condition": True})
        r = _resolver(g)
        assert r.evaluate_condition("some-condition", "") == "True"


class TestResolveList:
    def test_batch_resolve(self):
        g = StubGaming(exec_results={"a": "A"}, context={"b": "B"})
        r = _resolver(g)
        assert r.resolve_list(["@{a}", "%{b}", "plain"], "") == ["A", "B", "plain"]
