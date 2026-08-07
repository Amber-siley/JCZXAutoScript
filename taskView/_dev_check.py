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

def test_delete_no_leftover_blank():
    p = make()
    ed = ConfigEditor(p)
    ed.load()
    orig = ed.text
    ed.add_entity("zz-tmp", {"type": "click", "target": "buttons\\a.png"})
    ed.delete_entity("zz-tmp")
    assert ed.text == orig, "create→delete 往返应无残留空行/内容"
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

# ---- Task 2: 校验层断言 ----
from taskView.editor import load_entity_pool, simulate_and_validate

def test_load_pool():
    pool, efile = load_entity_pool()
    assert "goto-home" in pool or "click-center" in pool, "MainMenu 公共实体应存在"
    assert len(pool) > 5
    # 每个实体都能定位到定义文件
    assert all(k in efile for k in pool)

def test_validate_bad_ref_and_dup():
    pool, efile = load_entity_pool()
    # update 一个 action 指向不存在实体 -> 应报错
    writes, errors = simulate_and_validate(pool, efile, "tasks/receive.txt", [
        {"type": "update", "key": "task-receive-everyday", "fields": {"action": "no-such-entity"}}
    ])
    assert errors, "应产生引用错误"
    assert any("no-such-entity" in e["message"] for e in errors)
    assert writes == [], "校验失败时不得产生写回"

def test_validate_ok_and_create():
    pool, efile = load_entity_pool()
    writes, errors = simulate_and_validate(pool, efile, "tasks/receive.txt", [
        {"type": "create", "key": "_zz_dev_new", "entity": {"type": "click", "target": "buttons\\home.png"}},
        {"type": "delete", "key": "_zz_dev_new"},
    ])
    assert not errors, errors
    assert writes, "应产生写回"


def _section_block(text, key):
    """提取文本中 [key] section 的行（含头行，直到下一个 section 头）。"""
    lines = text.splitlines()
    start = None
    end = len(lines)
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("[") and s.endswith("]"):
            if s == f"[{key}]":
                start = i
            elif start is not None:
                end = i
                break
    return lines[start:end] if start is not None else []

def _count_options(block):
    """统计 section 内 option 行数（跳过注释与 section 头）。"""
    n = 0
    for ln in block:
        s = ln.strip()
        if s and not s.startswith("/") and not (s.startswith("[") and s.endswith("]")):
            if ":" in s:
                n += 1
    return n

def test_update_no_field_pollution():
    pool, efile = load_entity_pool()
    key = "task-receive-everyday"
    raw = open(efile[key], encoding="utf-8").read()
    before = _count_options(_section_block(raw, key))
    writes, errors = simulate_and_validate(pool, efile, "tasks/receive.txt", [
        {"type": "update", "key": key, "fields": {"sleep": "7"}}
    ])
    assert not errors, errors
    assert writes, "应产生写回"
    recv = next(t for p, t in writes if os.path.basename(p) == "receive.txt")
    block = _section_block(recv, key)
    after = _count_options(block)
    assert after < before + 5, f"update 写回污染配置: option 行数 {before} -> {after}"
    assert any("sleep: 7" in ln for ln in block), "应只追加变更字段 sleep: 7"
    # 不应出现未变更的默认字段落盘
    for bad in ("index: 0", "break_point: off", "queueable: on", "log_level: info",
                "screen_cache_ttl: -1.0", "condition_else:", "condition_then:", "wait_sec:", "args:"):
        assert not any(bad in ln for ln in block), f"写回出现未变更默认字段行: {bad}"

def test_rename_writes_rename():
    pool, efile = load_entity_pool()
    assert "click-claimAll" in pool, "前置：click-claimAll 实体存在"
    writes, errors = simulate_and_validate(pool, efile, "tasks/receive.txt", [
        {"type": "rename", "old": "click-claimAll", "new": "click-claimAll2"}
    ])
    assert not errors, errors
    assert writes, "应产生写回"
    recv = next(t for p, t in writes if os.path.basename(p) == "receive.txt")
    assert "[click-claimAll2]\n" in recv, "新 key section 头应存在"
    assert "[click-claimAll]\n" not in recv, "旧 key section 头应被重命名（不得残留副本）"
    # 引用 old 的 action/condition_then 应被同步更新
    assert "click-claimAll2,condition-to-get-item" in recv, "引用旧 key 的字段应同步为 new"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASS")
