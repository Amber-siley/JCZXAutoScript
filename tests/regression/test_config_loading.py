"""方案 3（回归）：基于真实 jczx/Config 只读副本的配置加载测试。"""
from jczx.taskManage import TaskManage


class TestConfigLoading:
    def test_loads_real_config(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        assert len(tm.entity_pool) > 50, "真实配置应加载出足量实体"

    def test_key_entities_exist(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        for key in ("goto-home", "click-center", "click-upcenter", "task-favor"):
            assert tm.get_entity(key) is not None, f"关键实体缺失: {key}"

    def test_external_file_merged(self, real_config_dir):
        """type: file 引入的外部任务应进入实体池。"""
        tm = TaskManage(real_config_dir)
        favor = tm.get_entity("task-favor")
        assert favor is not None
        assert favor.type == "task"
        assert favor.settings == "favor-settings"

    def test_extend_inherits(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        up = tm.get_entity("click-upcenter")
        assert up.type == "func"
        assert up.func == "click_proportion"
        assert up.args == ["2", "4"], "子类自身的 args（list[str]）不应被父类覆盖"

    def test_cross_file_placeholder(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        val = tm._resolve_placeholder("${task-favor-values:setting-favor-times}")
        assert val == "45"

    def test_placeholder_missing_section_default(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        val = tm._resolve_placeholder("${no-such-values:no-such-opt}", "x")
        assert val == ""
