"""方案 3（回归）：基于真实 jczx/Config 只读副本的配置加载测试。"""
import cv2
import numpy as np
from os.path import join

from jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig
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

    def test_config_has_mcp_port(self, real_config_dir):
        cfg = TxtConfig(join(real_config_dir, "Config.txt"))
        assert cfg.get_config(opt="mcp.port") == "8765"


class TestDeliveryOrderSettings:
    """自动交付订单任务：multi_select_switch 订单 + 两个 bool 开关设置。"""

    def test_task_links_settings(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        task = tm.get_entity("task-delivery-order")
        assert task is not None
        assert task.type == "task"
        assert task.settings == "settings-delivery-order"

    def test_three_setting_fields(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        fields = tm.get_task_setting_entities("task-delivery-order")
        types = {f.name: f.setting_type for f in fields}
        assert types == {
            "setting-delivery-orders": "multi_select_switch",
            "setting-delivery-synth": "bool",
            "setting-delivery-check-friend": "bool",
        }

    def test_multi_switch_orders_and_sub_label(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        fields = {f.name: f for f in tm.get_task_setting_entities("task-delivery-order")}
        orders = fields["setting-delivery-orders"]
        assert orders.switch_label == "是否合成"
        assert orders.options == [
            "18-2构建", "16-2构建", "10-1构建", "8-1构建",
            "6-1构建", "10-12w技术点", "10-12w星币",
        ]

    def test_bool_defaults_are_true(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        fields = {f.name: f for f in tm.get_task_setting_entities("task-delivery-order")}
        assert fields["setting-delivery-synth"].default == "true"
        assert fields["setting-delivery-check-friend"].default == "true"

    def test_saved_values_expose_sub_switches(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        vals = tm.get_task_values("task-delivery-order")
        assert set(vals["setting-delivery-orders"].split(",")) == {
            "16-2构建", "8-1构建", "6-1构建", "10-12w技术点", "10-12w星币",
        }
        assert set(vals["setting-delivery-orders__sub"].split(",")) == {
            "16-2构建", "8-1构建", "6-1构建",
        }


class TestGetImgLazyLoad:
    """get_img 懒加载兜底：call/method 动态参数路径按需加载进图片池。"""

    def test_lazy_load_and_cache(self, real_config_dir, tmp_path):
        png = tmp_path / "lazy.png"
        cv2.imwrite(str(png), np.zeros((5, 5, 3), np.uint8))
        tm = TaskManage(real_config_dir)
        tm.get_resources_target = lambda target: str(png)  # 定向到临时图片
        key = "dynamic\\param.png"
        assert key not in tm.img_pool
        img = tm.get_img(key)
        assert img is not None, "懒加载应按需读入图片"
        assert key in tm.img_pool, "懒加载后应缓存进图片池"

    def test_missing_file_returns_none(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        tm.get_resources_target = lambda target: "nonexistent\\path.png"
        assert tm.get_img("missing\\param.png") is None
