"""方案 1（纯逻辑）：TxtConfig 解析/回写/merge，以及 save 双写回归（Fix B）。"""
from jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils import Config

CFG_TEXT = """[MainMenu]
desc: 主配置

[click-center]
type: func
func: click_proportion
args: 2,2

[task-values]
setting-x: 1
"""


def _write(path):
    path.write_text(CFG_TEXT, encoding="utf-8")
    return str(path)


class TestRoundtrip:
    def test_get_config(self, tmp_path):
        cfg = Config(_write(tmp_path / "a.txt")).Config
        assert cfg.get_config("task-values", "setting-x") == "1"
        assert cfg.get_config("click-center", "func") == "click_proportion"

    def test_set_and_save_roundtrip(self, tmp_path):
        p = tmp_path / "a.txt"
        _write(p)
        cfg = Config(str(p)).Config
        cfg.set_config("task-values", "setting-x", "2")
        cfg.save()
        cfg2 = Config(str(p)).Config
        assert cfg2.get_config("task-values", "setting-x") == "2"
        assert cfg2.get_config("click-center", "func") == "click_proportion"  # 其余不受影响

    def test_add_new_section(self, tmp_path):
        p = tmp_path / "a.txt"
        _write(p)
        cfg = Config(str(p)).Config
        cfg.set_config("new-section", "new-opt", "hello")
        cfg.save()
        text = p.read_text(encoding="utf-8")
        assert text.count("[new-section]") == 1
        assert Config(str(p)).Config.get_config("new-section", "new-opt") == "hello"


class TestMerge:
    def test_merge_new_entries_index_minus1(self, tmp_path):
        _write(tmp_path / "a.txt")
        (tmp_path / "b.txt").write_text("[ext]\nx: 1\n", encoding="utf-8")
        a = Config(str(tmp_path / "a.txt")).Config
        b = Config(str(tmp_path / "b.txt")).Config
        a.merge(b)
        assert a.get_config("ext", "x") == "1"
        assert a.get_section("ext")["x"].index == -1, "merge 新增条目 index 应为 -1"

    def test_merge_overwrites_existing_value(self, tmp_path):
        _write(tmp_path / "a.txt")
        (tmp_path / "b.txt").write_text("[task-values]\nsetting-x: 9\n", encoding="utf-8")
        a = Config(str(tmp_path / "a.txt")).Config
        b = Config(str(tmp_path / "b.txt")).Config
        a.merge(b)
        assert a.get_config("task-values", "setting-x") == "9"


class TestSaveFallbackNoDoubleWrite:
    """回归 Fix B：save 遇到过期索引回退全量写入时，不得追加原始行造成重复。"""

    def test_stale_index_fallback_clean(self, tmp_path):
        p = tmp_path / "a.txt"
        _write(p)
        cfg = Config(str(p)).Config
        n = len(p.read_text(encoding="utf-8").splitlines())
        cfg._change_index = {n + 99}  # 模拟过期索引
        cfg.save()
        text = p.read_text(encoding="utf-8")
        assert text.count("[MainMenu]") == 1
        assert text.count("[click-center]") == 1
        assert text.count("[task-values]") == 1
