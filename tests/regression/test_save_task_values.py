"""方案 3（回归）：save_task_values — Fix A（外部不污染 MainMenu）/ Fix B（不重复写入）。"""
import os

from jczx.taskManage import TaskManage


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestExternalTaskSave:
    """task-favor 定义在 tasks/Favor.txt，保存值只应落盘 Favor.txt。"""

    def test_mainmenu_untouched(self, real_config_dir):
        main = os.path.join(real_config_dir, "MainMenu.txt")
        before = _read(main)
        tm = TaskManage(real_config_dir)
        tm.save_task_values("task-favor", {"setting-favor-times": "50"})
        after = _read(main)
        assert after == before, "外部任务保存不应改动 MainMenu.txt（Fix A）"
        assert "[task-favor]" not in after
        assert "[favor-settings]" not in after

    def test_value_persisted_in_external_file(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        tm.save_task_values("task-favor", {"setting-favor-times": "50"})
        favor = _read(os.path.join(real_config_dir, "tasks", "Favor.txt"))
        assert "setting-favor-times: 50" in favor or "setting-favor-times:50" in favor

    def test_reload_resolves_new_value(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        tm.save_task_values("task-favor", {"setting-favor-times": "50"})
        tm2 = TaskManage(real_config_dir)  # 重载不应有 duplicate-key 冲突
        assert tm2.menu_config.get_config("task-favor-values", "setting-favor-times") == "50"


class TestNativeTaskSave:
    """emu 定义在 MainMenu.txt，保存值应回写 MainMenu.txt。"""

    def test_writes_back_to_mainmenu_no_duplicate_no_leak(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        tm.save_task_values("emu", {"emu-setting-index": "3"})
        main = _read(os.path.join(real_config_dir, "MainMenu.txt"))
        assert "emu-setting-index: 3" in main or "emu-setting-index:3" in main
        assert main.count("[MainMenu]") == 1, "MainMenu 不应被重复写入（Fix B）"
        assert "[task-favor]" not in main, "外部 section 不应泄漏进 MainMenu"
        assert "[favor-settings]" not in main

    def test_reload_native_value(self, real_config_dir):
        tm = TaskManage(real_config_dir)
        tm.save_task_values("emu", {"emu-setting-index": "3"})
        tm2 = TaskManage(real_config_dir)
        assert tm2.menu_config.get_config("emu-values", "emu-setting-index") == "3"
