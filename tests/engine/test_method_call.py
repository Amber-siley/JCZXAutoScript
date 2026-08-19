"""method / call 回归测试：body 执行 / 位置+kwargs 绑定 / 校验 / 默认值 / 嵌套 / context.values。"""
import logging

from jczx.configEntity import JczxSectionEntity


def _entity(**kw):
    e = JczxSectionEntity()
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def _register(gaming, **entities):
    """entity_pool 是 DictVariable，不支持 update()，逐个赋值。"""
    for key, ent in entities.items():
        gaming.task_manage.entity_pool[key] = ent


class TestMethod:
    def test_method_executes_body_chain(self, gaming):
        order = []
        gaming.record_step = lambda tag: order.append(tag)
        s1 = _entity(type="func", func="record_step", args=["a"])
        s2 = _entity(type="func", func="record_step", args=["b"])
        m = _entity(type="method", action=["m-step-1", "m-step-2"])
        _register(gaming, **{"m-step-1": s1, "m-step-2": s2, "my-method": m})
        gaming.exec("my-method")
        assert order == ["a", "b"]


class TestCallBinding:
    def test_kwargs_bind_and_body_reads(self, gaming):
        values = []
        gaming.record_value = lambda a, b: values.append((a, b))
        show = _entity(type="func", func="record_value", args=["%{x}", "%{y}"])
        m = _entity(type="method", params=["x", "y"], action=["show-x"])
        c = _entity(type="call", fn="m1", args=["x=hello", "y=world"])
        _register(gaming, **{"show-x": show, "m1": m, "c1": c})
        gaming.exec("c1")
        assert values == [("hello", "world")]

    def test_positional_args_bind_by_params_order(self, gaming):
        values = []
        gaming.record_value = lambda a, b: values.append((a, b))
        show = _entity(type="func", func="record_value", args=["%{x}", "%{y}"])
        m = _entity(type="method", params=["x", "y"], action=["show-x"])
        c = _entity(type="call", fn="m1", args=["alpha", "beta"])
        _register(gaming, **{"show-x": show, "m1": m, "c1": c})
        gaming.exec("c1")
        assert values == [("alpha", "beta")]

    def test_mixed_positional_and_kwargs(self, gaming):
        values = []
        gaming.record_value = lambda a, b, c: values.append((a, b, c))
        show = _entity(type="func", func="record_value", args=["%{x}", "%{y}", "%{z}"])
        m = _entity(type="method", params=["x", "y", "z"], action=["show-x"])
        c = _entity(type="call", fn="m1", args=["alpha", "z=zeta"])
        _register(gaming, **{"show-x": show, "m1": m, "c1": c})
        gaming.exec("c1")
        assert values == [("alpha", "", "zeta")]

    def test_param_defaults_then_override(self, gaming):
        values = []
        gaming.record_value = lambda a, b: values.append((a, b))
        show = _entity(type="func", func="record_value", args=["%{x}", "%{y}"])
        m = _entity(type="method", params=["x", "y"],
                   param_defaults=["y=def-y"], action=["show-x"])
        _register(gaming, **{"show-x": show, "m1": m})
        c1 = _entity(type="call", fn="m1", args=["x=hello"])
        _register(gaming, c1=c1)
        gaming.exec("c1")
        assert values[-1] == ("hello", "def-y")
        c2 = _entity(type="call", fn="m1", args=["x=hello", "y=ovr"])
        _register(gaming, c2=c2)
        gaming.exec("c2")
        assert values[-1] == ("hello", "ovr")


class TestValidation:
    def test_missing_param_warns(self, gaming, caplog):
        m = _entity(type="method", params=["x"], action=[])
        c = _entity(type="call", fn="m1", args=[])
        _register(gaming, m1=m, c1=c)
        with caplog.at_level(logging.WARNING):
            gaming.exec("c1")
        assert "缺少参数" in caplog.text

    def test_extra_param_warns(self, gaming, caplog):
        m = _entity(type="method", params=["x"], action=[])
        c = _entity(type="call", fn="m1", args=["x=a", "extra=b"])
        _register(gaming, m1=m, c1=c)
        with caplog.at_level(logging.WARNING):
            gaming.exec("c1")
        assert "多余参数" in caplog.text

    def test_call_non_method_target_warns(self, gaming, caplog):
        t = _entity(type="task", action=[])
        c = _entity(type="call", fn="t1", args=["x=a"])
        _register(gaming, t1=t, c1=c)
        with caplog.at_level(logging.WARNING):
            gaming.exec("c1")
        assert "不是 method" in caplog.text


class TestNestedCall:
    def test_method_calls_another_method(self, gaming):
        """嵌套：内层 call 用位置参数引用外层 %{outer}，绑定前解析。"""
        values = []
        gaming.record_value = lambda v: values.append(v)
        show = _entity(type="func", func="record_value", args=["%{x}"])
        m1 = _entity(type="method", params=["x"], action=["show-x"])
        inner = _entity(type="call", fn="m1", args=["%{outer}"])
        m2 = _entity(type="method", params=["outer"], action=["inner-call"])
        c = _entity(type="call", fn="m2", args=["outer=deep"])
        _register(gaming, **{"show-x": show, "m1": m1, "inner-call": inner, "m2": m2, "c1": c})
        gaming.exec("c1")
        assert values == ["deep"]


class TestContextValues:
    def test_batch_init(self, gaming):
        ctx = _entity(type="context", values=["a=1", "b=hello"])
        _register(gaming, init=ctx)
        gaming.exec("init")
        assert gaming._context["a"] == "1"
        assert gaming._context["b"] == "hello"

    def test_values_resolve_placeholders(self, gaming):
        gaming._context["base"] = "buttons\\a.png"
        ctx = _entity(type="context", values=["path=%{base}"])
        _register(gaming, init=ctx)
        gaming.exec("init")
        assert gaming._context["path"] == "buttons\\a.png"
