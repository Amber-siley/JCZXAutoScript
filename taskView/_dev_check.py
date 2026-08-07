"""临时自检脚本。uv run python taskView/_dev_check.py"""
import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.editor import ConfigEditor, simulate_and_validate, load_entity_pool
from jczx.configEntity import JczxSectionEntity
from jczx.CommonBuilder.CommonBuilder.FileTools.ConfigUtils import TxtConfig

SAMPLE = "[e1]\ntype: click\nname: 测试\ntarget: buttons\\home.png\nsleep: 1\n"

def _make():
    fd, p = tempfile.mkstemp(suffix=".txt"); os.close(fd)
    with open(p, "w", encoding="utf-8") as f: f.write(SAMPLE)
    return p

def test_delete_option():
    p = _make(); ed = ConfigEditor(p); ed.load()
    ed.delete_option("e1", "sleep")
    assert "sleep" not in ed.text, ed.text
    os.unlink(p)

def test_delete_option_missing_noop():
    p = _make(); ed = ConfigEditor(p); ed.load()
    ed.delete_option("e1", "nonexistent")  # 不应抛错
    assert "sleep: 1" in ed.text
    os.unlink(p)

def test_create_empty_field_filtered():
    """create 空值字段（sleep: ""）写回应跳过，不产出 `sleep: ` 空值行；
    该文本经 TxtConfig 重新加载 trans_entity_dict 不崩溃。"""
    pool, efile = load_entity_pool()
    key = "zz_dev_check_create"
    assert key not in pool, key
    ops = [{"type": "create", "key": key,
            "entity": {"type": "click", "name": "t", "sleep": ""}}]
    writes, errors = simulate_and_validate(pool, efile, "tasks/test.txt", ops)
    assert not errors, errors
    assert len(writes) == 1
    text = writes[0][1]
    assert "sleep:" not in text, text
    fd, p = tempfile.mkstemp(suffix=".txt"); os.close(fd)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    ents = TxtConfig(p).trans_entity_dict(JczxSectionEntity)
    assert key in ents, ents.keys()
    os.unlink(p)

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn): fn(); print(f"PASS {name}")
    print("ALL PASS")
