"""方案 1（纯逻辑）：configEntity 类型强转 / list 拆分 / 占位符保留 / SectionType。"""
from jczx.configEntity import JczxSectionEntity, SectionType


class TestSetAttrCoercion:
    """BaseEntity.__setattr__ 的类型强转逻辑。"""

    def test_str_to_int(self):
        e = JczxSectionEntity()
        e.times = "3"
        assert e.times == 3
        assert isinstance(e.times, int)

    def test_str_to_float(self):
        e = JczxSectionEntity()
        e.per = "0.8"
        assert e.per == 0.8
        assert isinstance(e.per, float)

    def test_csv_to_list(self):
        e = JczxSectionEntity()
        e.action = "goto-home,click-fight,wait-1"
        assert e.action == ["goto-home", "click-fight", "wait-1"]

    def test_none_stays_none(self):
        e = JczxSectionEntity()
        e.wait_target = None
        assert e.wait_target is None

    def test_placeholder_value_kept_as_str(self):
        """含占位符的字段不强制转换，留给运行时 PlaceholderResolver 解析。"""
        e = JczxSectionEntity()
        e.times = "${task-favor-values:setting-favor-times}"
        assert isinstance(e.times, str)
        assert e.times == "${task-favor-values:setting-favor-times}"

    def test_plain_str_value(self):
        e = JczxSectionEntity()
        e.target = "buttons\\fight.png"
        assert e.target == "buttons\\fight.png"


class TestSectionType:
    def test_membership(self):
        assert "click" in SectionType
        assert "task" in SectionType
        assert "file" in SectionType
        assert "not-a-type" not in SectionType

    def test_is_img_types(self):
        assert SectionType.is_img_types("click") is True
        assert SectionType.is_img_types("match") is False
        assert SectionType.is_img_types("ocr") is False
