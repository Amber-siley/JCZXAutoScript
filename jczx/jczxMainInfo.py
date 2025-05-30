class WorkTags:
    ORDER = "交付订单"
    SWITCH = "矿场换班"
    DEBUG = "Debug"
    ACCEPT = "自动同意申请"
    AWARD = "刷取助战奖励"
    ONLY_THIS_ORDERS = "仅当前订单"
    SMALL_CRYSTAL = "周本虚影微晶"
    SET_ADBTOOLS = "下载ADB工具"
    ILLUSION_TO_FAVOR = "虚影刷好感度"
    TASKS_LIST = "任务列表"
    JJC_TASK = "竞技场挑战"
    JDC_TASK = "角斗场挑战"
    INIT_OCR = "初始化OCR"
    QUIT_JCZX = "关闭游戏"
    QUIT_DEVICE = "关闭模拟器"

class CreaterWorkTags:
    ORDER = WorkTags.ORDER
    AWARD = WorkTags.AWARD
    # ONLY_THIS_ORDERS = WorkTags.ONLY_THIS_ORDERS
    SMALL_CRYSTAL = WorkTags.SMALL_CRYSTAL
    ILLUSION_TO_FAVOR = WorkTags.ILLUSION_TO_FAVOR
    JJC_TASK = WorkTags.JJC_TASK
    JDC_TASK = WorkTags.JDC_TASK
    QUIT_JCZX = WorkTags.QUIT_JCZX
    
    @staticmethod
    def ls():
        tmp = CreaterWorkTags()
        return [tmp.__getattribute__(i) for i in CreaterWorkTags().__dir__() if not i.startswith("__") and i != 'ls']

VERSION = "0.1.11A"

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
    },
    "JJCTask": {
        "ThresholdValue": 25000
    },
    "DNconsoleDevices":{
        
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