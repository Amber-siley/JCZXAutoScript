"""临时自检脚本。uv run python taskView/_dev_check.py"""
import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.editor import ConfigEditor

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

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn): fn(); print(f"PASS {name}")
    print("ALL PASS")
