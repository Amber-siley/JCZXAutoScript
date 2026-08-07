"""临时自检脚本（非 pytest）。uv run python taskView/_dev_check.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.graph_builder import (_load_all_files, build_graph, build_flow_tree, get_entity_detail)

def test_load_all_files_returns_entity_file():
    configs, efile = _load_all_files()
    assert len(configs) > 100, "应加载全部实体"
    assert "test" in efile or "click-center" in efile
    assert all(k in efile for k in configs), "每个实体应有来源文件"

def test_build_graph_cross_file_edge():
    # test.txt 的 test.action 引用 get-combat-power/context-check（MainMenu）
    g = build_graph("tasks/test.txt")
    ids = [n["data"]["id"] for n in g["nodes"]]
    assert "get-combat-power" in ids or "context-check" in ids, "跨文件引用实体应出现在节点"
    edges = [e["data"] for e in g["edges"]]
    assert any(e["source"] == "test" and e["target"] in ("get-combat-power", "context-check") for e in edges), "应有跨文件引用边"

def test_flow_node_has_file():
    tree = build_flow_tree("tasks/test.txt", "test")
    nodes = tree["nodes"]
    assert nodes, "flow 树应非空"
    assert any("file" in n["data"] for n in nodes), "flow 节点应带 file 字段"

def test_detail_has_settings_fields():
    d = get_entity_detail("tasks/test.txt", "test")
    for f in ("fields", "setting_type", "label", "options", "default", "min", "max"):
        assert f in d, f"detail 应含 {f}"
    # settings/setting 专有字段应有实际值（非空，防假绿灯）
    ds = get_entity_detail("MainMenu.txt", "screenshot-task-settings")
    assert ds["fields"] == ["screenshot-name"], "settings 实体 fields 应有值"
    dn = get_entity_detail("MainMenu.txt", "screenshot-name")
    assert dn["setting_type"] == "input", "setting 实体 setting_type 应有值"
    assert dn["label"] == "截图名称", "setting 实体 label 应有值"
    assert dn["default"] == "name", "setting 实体 default 应有值"
    # 专有字段应并入 explicit（前端复制 settings/setting 实体不丢字段）
    assert "fields" in ds["explicit"], "settings 实体 explicit 应含 fields"
    assert "setting_type" in dn["explicit"], "setting 实体 explicit 应含 setting_type"
    assert "default" in dn["explicit"], "setting 实体 explicit 应含 default"

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"PASS {name}")
    print("ALL PASS")
