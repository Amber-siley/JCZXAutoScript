from enum import Enum

class Lang(Enum):
    ZH_CN = "ZH-CN"
    EN_US = "EN-US"

translate_en_dict = {
    "请选择要执行的操作": "Please choose an action",
    "选择设备": "Choose device",
    "执行任务": "Execute tasks",
    "请选择任务": "Please choose tasks",
    "退出程序": "Quit program",
}

def translate(text: str, language: Lang = Lang.ZH_CN) -> str:
    if language == Lang.ZH_CN:
        return text
    elif language == Lang.EN_US:
        return translate_en_dict.get(text, text)
    else:
        return text