"""临时自检脚本（非 pytest）。uv run python taskView/_dev_check.py"""
import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from taskView.editor import ConfigEditor, file_hash

SAMPLE = (
    "/ 主菜单\n"
    "\n"
    "[goto-home]\n"
    "type: click\n"
    "name: 回家\n"
    "target: buttons\\home.png\n"
    "sleep: 1\n"
    "[click-mail]\n"
    "type: click\n"
    "target: buttons\\mail.png\n"
)

def make() -> str:
    fd, path = tempfile.mkstemp(suffix=".txt", dir=tempfile.gettempdir())
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(SAMPLE)
    return path

def test_parse():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    assert ed.sections == ["goto-home", "click-mail"], ed.sections
    os.unlink(p)

def test_update_preserves_comment_and_chain():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    ed.update_value("click-mail", "target", "buttons\\new.png")
    text = ed.text
    assert "target: buttons\\new.png\n" in text, text
    assert "/ 主菜单\n" in text, text          # 行首注释保留
    os.unlink(p)

def test_add_and_delete():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    ed.add_entity("new-click", {"type": "click", "target": "buttons\\a.png"})
    assert "[new-click]\n" in ed.text
    ed.delete_entity("new-click")
    assert "[new-click]" not in ed.text
    assert "/ 主菜单\n" in ed.text             # 注释保留为孤立注释
    os.unlink(p)

def test_rename():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    ed.rename_entity("goto-home", "goto-main")
    assert "[goto-main]\n" in ed.text
    assert "[goto-home]" not in ed.text
    os.unlink(p)

def test_save_atomic_and_hash():
    p = make()
    h1 = file_hash(p)
    ed = ConfigEditor(p)
    ed.load()
    ed.update_value("goto-home", "sleep", "2")
    ed.save()
    assert file_hash(p) != h1
    with open(p, encoding="utf-8") as f:
        assert "sleep: 2\n" in f.read()
    os.unlink(p)

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
