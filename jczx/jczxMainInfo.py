class WorkTags:
    ORDER = "交付订单"
    SWITCH = "矿场换班"
    DEBUG = "Debug"
    ACCEPT = "自动同意申请"
    AWARD = "刷助战奖励"
    ONLY_THIS_ORDERS = "仅当前订单"
    SMALL_CRYSTAL = "虚影微晶任务"
    SET_ADBTOOLS = "下载ADB工具"
    ILLUSION_TO_FAVOR = "虚影刷好感度"
    TASKS_LIST = "任务列表"

VERSION = "0.1.7A"

DEFAULT_CONFIGS = {
    "adb_path": None,
    "adb_device": None,
    "quarry_time": -1,
    "orders":{
        "build_61": {
            "enable": True,
            "craft": True
        },
        "build_81": {
            "enable": True,
            "craft": True
        },
        "build_101": {
            "enable": False,
            "craft": True
        },
        "build_162": {
            "enable": True,
            "craft": True
        },
        "build_182": {
            "enable": False,
            "craft": True
        },
        "coin_1012": {
            "enable": False,
            "craft": False
        },
        "exp_1012": {
            "enable": False,
            "craft": False
        }
    },
    "illusions": {
        "level": {
            "index": 1,
            "illusionNum": 0,
            "title": "戈里刻-宙斯",
            "SwipeUP": True
        },
        "teamNum": 0
    },
    "favor": {
        "teamNum": 1,
        "time": 40
    },
    "tasks": {
        "choice": "测试",
        "list": {
            "测试": [
                ("emulator-5556", WorkTags.AWARD),
                ("emulator-5554", WorkTags.ORDER),
                ("emulator-5554", WorkTags.SMALL_CRYSTAL),
                ("emulator-5556", WorkTags.AWARD)
            ]
        }
    }
}

ILLUSION_LEVELS_SETTINGS = [
    {
        "index": 0,
        "illusionNum": 0,
        "title": "戈里刻-阿瑞斯",
        "SwipeUP": False
    },
    {
        "index": 1,
        "illusionNum": 0,
        "title": "戈里刻-宙斯",
        "SwipeUP": True
    },
    # {
    #     "index": 2,
    #     "illusionNum": 2,
    #     "title": "尼克罗-弗利亚多",
    #     "SwipeUP": True
    # }
]

ADB_TOOLS_URL = "https://googledownloads.cn/android/repository/platform-tools-latest-windows.zip"