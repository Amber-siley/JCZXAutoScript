from typing import Any,Callable
from os.path import exists,join,abspath
from os import startfile
from json import load,dumps
from time import sleep
from datetime import datetime
from Ui_UI import Ui_Form

from PyQt6.QtWidgets import QApplication,QWidget,QFileDialog
from PyQt6.QtGui import QIntValidator,QTextCursor
from PyQt6.QtCore import QThread

import subprocess
import logging
import cv2
import sys
import numpy as np

def joinPath(*args):
    if hasattr(sys, '_MEIPASS'):
        return join(sys._MEIPASS, *args)
    return join(abspath("."), *args)

LOG_LEVEL = logging.INFO
# LOG_LEVEL = logging.DEBUG

DEFAULT_CONFIGS = {
    "adb_path": None,
    "adb_device": None,
    "quarry_time": None,
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
    "illusions":{
        "level": {
            "index": 1,
            "illusionNum": 0,
            "title": "戈里刻-宙斯",
            "SwipeUP": True
        },
        "teamNum": 0
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

class LoggerHandler(logging.Handler):
    def __init__(self, edit) -> None:
        super().__init__(logging.DEBUG)
        self.edit = edit
        self.formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt = "%H:%M:%S")
    
    def emit(self, record):
        msg = self.format(record)
        self.edit.append(msg)
        sleep(0.01)
        self.edit.moveCursor(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.MoveAnchor)
    
    def write(self,text):
        self.edit.append(text)
    
    def format(self, record):
        if record.levelno == logging.DEBUG:
            color = 'blue'
        elif record.levelno == logging.INFO:
            color = 'black'
        elif record.levelno == logging.WARNING:
            color = 'orange'
        elif record.levelno == logging.ERROR:
            color = 'red'
        else:
            color = 'gray'
        new_msg = self.formatter.format(record)
        msg = '<span style="color:{}">{}</span>'.format(color, new_msg)
        return msg
    
class MainManager(Ui_Form):
    class _Chart:
        GrowthItems = joinPath("resources","toolChart","养成材料一览.png")
        ItemsEX = joinPath("resources","toolChart","材料掉率一图流.jpg")
        Chips = joinPath("resources","toolChart","芯片获得途径.jpg")
        ChoiceChips = joinPath("resources","toolChart","自选芯片.jpg")
    
    Chart = _Chart()
    
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.form = QWidget()
        self.fileDialog = QFileDialog()
        self.config = JsonConfig("autoScriptConfig.json", DEFAULT_CONFIGS)
        self.log = logging.Logger(__name__, LOG_LEVEL)
        self.adb = JCZXGame(self.adb_path, self.log, self.config)
        self.work_thread = WorkThread(self.adb, self.log, self.config)
        
    def setupUi(self):
        super().setupUi(self.form)
        self.init()
    
    def init(self):
        """初始化"""
        self.__init_illusionSettings()
        self.__init_buttom()
        self.__init_menu()
        self.__init_orderlist()
        self.__init_valueRule()
        self.__init_devices()
        self.referMenuConfig()
        self.__init_logger()
        self.__start_app()
    
    @property
    def adb_device(self) -> str: return self.config.adb_device
    @property
    def adb_path(self) -> str:  return self.config.adb_path
    @property
    def quarry_time(self) -> int: return self.config.quarry_time
    
    def __init_menu(self):
        self.help_textBrowser.setHidden(True)
        self.logger_Browser.setFocus()
        if LOG_LEVEL != logging.DEBUG:
            self.test_button.setHidden(True)
    
    def __init_valueRule(self):
        self.quarry_time_lineEdit.setValidator(QIntValidator(0, 60))
    
    def __init_logger(self):
        handler = LoggerHandler(self.logger_Browser)
        self.log.addHandler(handler)
        self.log.info("程序初始化完成")
        sys.stdout = handler
    
    def __init_buttom(self):
        """初始化按钮"""
        self.choice_adbpath_Button.clicked.connect(self.choiceADBPath)
        self.save_config_Button.clicked.connect(self.saveConfig)
        self.help_button.clicked.connect(self.switchHelpTextHidden)
        self.adb_devices_comboBox.currentTextChanged.connect(self.setDeviceConfig)
        self.start_switch_work_Button.clicked.connect(lambda: self.createWork(self.work_thread.SWITCH))
        self.start_spend_order_Button.clicked.connect(lambda: self.createWork(self.work_thread.ORDER))
        self.start_spend_order_settings_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(0))
        self.stop_all_task_Button.clicked.connect(self.stopTask)
        self.auto_agree_friend_Button.clicked.connect(lambda: self.createWork(self.work_thread.ACCEPT))
        self.brushing_surportAwards_Button.clicked.connect(lambda: self.createWork(self.work_thread.AWARD))
        self.only_checkSpendThisTradingPost_Button.clicked.connect(lambda: self.createWork(self.work_thread.ONLY_THIS_ORDERS))
        self.start_smallCrystal_Button.clicked.connect(lambda: self.createWork(self.work_thread.SMALL_CRYSTAL))
        self.refresh_devices_Button.clicked.connect(self.__init_devices)
        self.growthItems_Button.clicked.connect(lambda: startfile(self.Chart.GrowthItems))
        self.ItemsEX_Button.clicked.connect(lambda: startfile(self.Chart.ItemsEX))
        self.Chips_Button.clicked.connect(lambda: startfile(self.Chart.Chips))
        self.choice_Chips_Button.clicked.connect(lambda: startfile(self.Chart.ChoiceChips))
        self.start_smallCrystal_settings_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))
        self.IllusionChoice_comboBox.currentIndexChanged.connect(lambda: self.config.illusion.setLevel(self.IllusionChoice_comboBox.currentIndex()))
        self.IllusionChoiceTeam_comboBox.currentIndexChanged.connect(lambda: self.config.illusion.setTeamNum(self.IllusionChoiceTeam_comboBox.currentIndex()))
        
        self.test_button.clicked.connect(self.__debug)
    
    def __init_orderlist(self):
        self.order_build61_checkBox.setChecked(self.config.build61.enable)
        self.craft_build61_enable_checkBox.setChecked(self.config.build61.craft)
        self.order_build61_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_61","enable"), self.order_build61_checkBox.isChecked()))
        self.craft_build61_enable_checkBox.stateChanged.connect(lambda: self.config.build61.setCraftEnable(self.craft_build61_enable_checkBox.isChecked()))
        
        self.order_build81_checkBox.setChecked(self.config.get_config(("orders","build_81","enable")))
        self.craft_build81_enable_checkBox.setChecked(self.config.build81.craft)
        self.order_build81_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_81","enable"), self.order_build81_checkBox.isChecked()))
        self.craft_build81_enable_checkBox.stateChanged.connect(lambda: self.config.build81.setCraftEnable(self.craft_build81_enable_checkBox.isChecked()))
        
        self.order_build101_checkBox.setChecked(self.config.get_config(("orders","build_101","enable")))
        self.craft_build101_enable_checkBox.setChecked(self.config.build101.craft)
        self.order_build101_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_101","enable"), self.order_build101_checkBox.isChecked()))
        self.craft_build101_enable_checkBox.stateChanged.connect(lambda: self.config.build101.setCraftEnable(self.craft_build101_enable_checkBox.isChecked()))
        
        self.order_build162_checkBox.setChecked(self.config.get_config(("orders","build_162","enable")))
        self.craft_build162_enable_checkBox.setChecked(self.config.build162.craft)
        self.order_build162_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_162","enable"), self.order_build162_checkBox.isChecked()))
        self.craft_build162_enable_checkBox.stateChanged.connect(lambda: self.config.build162.setCraftEnable(self.craft_build162_enable_checkBox.isChecked()))
        
        self.order_build182_checkBox.setChecked(self.config.get_config(("orders","build_182","enable")))
        self.craft_build182_enable_checkBox.setChecked(self.config.build182.craft)
        self.order_build182_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_182","enable"), self.order_build182_checkBox.isChecked()))
        self.craft_build182_enable_checkBox.stateChanged.connect(lambda: self.config.build182.setCraftEnable(self.craft_build182_enable_checkBox.isChecked()))
        
        self.order_coin1012w_checkBox.setChecked(self.config.get_config(("orders","coin_1012","enable")))
        self.craft_coin1012w_enable_checkBox.setChecked(self.config.coin1012.craft)
        self.order_coin1012w_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","coin_1012","enable"), self.order_coin1012w_checkBox.isChecked()))
        self.craft_coin1012w_enable_checkBox.stateChanged.connect(lambda: self.config.coin1012.setCraftEnable(self.craft_coin1012w_enable_checkBox.isChecked()))
        
        self.order_exp1012w_checkBox.setChecked(self.config.get_config(("orders","exp_1012","enable")))
        self.craft_exp1012w_enable_checkBox.setChecked(self.config.exp1012.craft)
        self.order_exp1012w_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","exp_1012","enable"), self.order_exp1012w_checkBox.isChecked()))
        self.craft_exp1012w_enable_checkBox.stateChanged.connect(lambda: self.config.exp1012.setCraftEnable(self.craft_exp1012w_enable_checkBox.isChecked()))
    
    def __init_illusionSettings(self):
        self.IllusionChoice_comboBox.addItems([i["title"] for i in ILLUSION_LEVELS_SETTINGS])
        self.IllusionChoice_comboBox.setCurrentIndex(self.config.illusion.level.index)
        self.IllusionChoiceTeam_comboBox.addItems(["1号队伍", "2号队伍"])
        self.IllusionChoiceTeam_comboBox.setCurrentIndex(self.config.illusion.teamNum)
    
    def stopTask(self):
        if self.work_thread.isRunning():
            self.work_thread.stop()
            self.log.info(f"已停止【{self.work_thread.mode}】")
        else:
            self.log.info("当前无任务运行")
        
    def createWork(self, mode):
        if self.work_thread.mode == mode and self.work_thread.isRunning():
            return
        if self.work_thread.isRunning():
            self.work_thread.stop()
            self.log.info(f"已停止【{self.work_thread.mode}】")
        self.work_thread.setMode(mode)
        self.work_thread.start()
    
    def switchHelpTextHidden(self):
        if self.help_textBrowser.isHidden():
            self.help_textBrowser.setHidden(False)
        else:
            self.help_textBrowser.setHidden(True)
    
    def __debug(self):
        if self.work_thread.mode == self.work_thread.DEBUG and self.work_thread.isRunning():
            return
        if self.work_thread.isRunning():
            self.work_thread.stop()
        self.work_thread.setMode(WorkThread.DEBUG)
        self.work_thread.start()
    
    def __init_devices(self):
        if devices := self.adb.devices():
            self.adb_devices_comboBox.clear()
            self.adb_devices_comboBox.addItems(devices)
    
    def __start_app(self):
        """初始化app"""
        self.form.show()
        self.app.exec()

    def choiceADBPath(self):
        paths = self.fileDialog.getOpenFileName(filter = "*.exe")
        if paths != ('',''):
            path = paths[0]
            self.setADBPathConfig(path)
            self.referMenuConfig()
    
    def referMenuConfig(self):
        """从配置文件刷新界面"""
        self.adb_path_lineEdit.setText(self.adb_path)
        self.adb_devices_comboBox.setCurrentText(self.adb_device)
        self.quarry_time_lineEdit.setText(str(self.quarry_time))
    
    def setADBPathConfig(self,adb_path):
        self.config.set_config("adb_path", adb_path)
        self.adb.setADBPath(adb_path)
        self.__init_devices()
        self.setDeviceConfig(self.adb_devices_comboBox.currentText())
    
    def setDeviceConfig(self, device:str):
        if device:
            self.adb_devices_comboBox.setCurrentText(device)
            self.config.set_config("adb_device",device)
            self.adb.setDevice(device)
    
    def setQuarryTimeConfig(self,quarry_time):
        self.config.set_config("quarry_time", int(quarry_time))
    
    def saveConfig(self):
        if adb_path := self.adb_path_lineEdit.text():
            if exists(adb_path):
                self.setADBPathConfig(adb_path)
        
        if quarry_time := self.quarry_time_lineEdit.text():
            if quarry_time.isdigit():
                self.setQuarryTimeConfig(quarry_time)
        
        self.referMenuConfig()
        self.log.info("完成保存配置")

class JsonConfig:
    class Order:
        class OrderType: ...
        def __init__(self, config, opt:OrderType | str) -> None:
            self.__config = config
            self.opt = opt
            self.enable = self.__config.get_config(("orders", self.opt, "enable"))
            self.craft = self.__config.get_config(("orders", self.opt, "craft"))
        
        def setEnable(self, enable:bool) -> None:
            self.__config.set_config(("orders", self.opt, "enable"), enable)
        
        def setCraftEnable(self, enable:bool) -> None:
            self.__config.set_config(("orders", self.opt, "craft"), enable)
    
    class IllusionSetting:
        class Level:
            def __init__(self, configs) -> None:
                self.index = configs["index"]
                self.title = configs["title"]
                self.illusionNum = configs["illusionNum"]
                self.swipeUP = configs["SwipeUP"]
            
        def __init__(self, config) -> None:
            self.__config = config
        
        @property
        def level(self) -> Level:
            return self.Level(self.__config.get_config(("illusions", "level")))

        def setLevel(self, index:int):
            self.__config.set_config(("illusions", "level"), ILLUSION_LEVELS_SETTINGS[index])
        
        def setTeamNum(self, num:int):
            self.__config.set_config(("illusions", "teamNum"), num)
        
        @property
        def teamNum(self) -> int:
            return self.__config.get_config(("illusions", "teamNum"))
        
    def __init__(self, path, default:dict = {}) -> None:
        self.path = path
        self.default = default
        if not exists(self.path):
            self.set_default()
            
        self._configs:dict = load(open(self.path, encoding = "utf-8"))
        self.illusion = self.IllusionSetting(self)
    
    def set_config(self,sec:str | tuple,value:Any):
        """设置配置项"""
        if isinstance(sec, str):
            self._configs[sec] = value
        else:
            option = self.get_config(sec[:-1])
            option[sec[-1]] = value
        self.save()
    
    @property
    def adb_device(self):   return self.get_config("adb_device")
    @property
    def adb_path(self): return self.get_config("adb_path")
    @property
    def quarry_time(self):  return self.get_config("quarry_time")
    @property
    def build61(self):  return self.Order(self, "build_61")
    @property
    def build81(self):  return self.Order(self, "build_81")
    @property
    def build101(self): return self.Order(self, "build_101")
    @property
    def build162(self): return self.Order(self, "build_162")
    @property
    def build182(self): return self.Order(self, "build_182")
    @property
    def coin1012(self): return self.Order(self, "coin_1012")
    @property
    def exp1012(self):  return self.Order(self, "exp_1012")
    
    def save(self):
        with open(self.path,"w",encoding="utf-8") as fp:
            fp.write(dumps(self._configs, indent = 4, ensure_ascii = False))

    def get_config(self,sec:str | tuple) -> Any:
        """获取配置项值"""
        if isinstance(sec,str):
            return self._configs[sec]
        elif isinstance(sec,tuple):
            tmp = self._configs
            for key in sec:
                tmp = tmp[key]
            return tmp
    
    def set_default(self):
        with open(self.path,"w",encoding="utf-8") as fp:
            fp.write(dumps(self.default, indent = 4, ensure_ascii = False))

class JCZXGame:
    class _ScreenCut:
        class Point: ...
        def __init__(self, w, h) -> None:
            self.w = w
            self.h = h
        
        def cut(self, cx, cy, x, y) ->tuple[Point, Point]:
            w = self.w//cx
            h = self.h//cy
            return ((w*x, h*y), (w*(x+1), h*(y+1)))

        def cut1x2(self, x, y): return self.cut(1, 2, x, y)
        def cut2x1(self, x, y): return self.cut(2, 1, x, y)
        def cut2x2(self, x, y): return self.cut(2, 2, x, y)
        def cut2x3(self, x, y): return self.cut(2, 3, x, y)
        def cut3x1(self, x, y): return self.cut(3, 1, x, y)
        def cut3x2(self, x, y): return self.cut(3, 2, x, y)
        def cut3x3(self, x, y): return self.cut(3, 3, x, y)
        def cut3x4(self, x, y): return self.cut(3, 4, x, y)
        def cut3x7(self, x, y): return self.cut(3, 7, x, y)
        def cut4x1(self, x, y): return self.cut(4, 1, x, y)
        def cut4x2(self, x, y): return self.cut(4, 2, x, y)
        def cut4x3(self, x, y): return self.cut(4, 3, x, y)
        def cut7x1(self, x, y): return self.cut(7, 1, x, y)
        def cut7x3(self, x, y): return self.cut(7, 3, x, y)
        def cut7x2(self, x, y): return self.cut(7, 2, x, y)
        def cut9x2(self, x, y): return self.cut(9, 2, x, y)
        def cut9x9(self, x, y): return self.cut(9, 9, x, y)
        
    class _Buttons:
        back_button = joinPath("resources","buttons","back.png")
        visit_button = joinPath("resources","buttons","visit.png")
        choiceFriendTP_button = joinPath("resources","locations","whateverTradingPost.png")
        skipAnimation_button = joinPath("resources","buttons","skipAnimation.png")
        fightAuto_button = joinPath("resources","buttons","fightAuto.png")
        plane_button = joinPath("resources","buttons","plane.png")
        ZhouSi_button = joinPath("resources","buttons","ZhouSi.png")
        ARuiSi_button = joinPath("resources","buttons","ARuiSi.png")
        sureQuit_button = joinPath("resources","buttons","sureQuit.png")
        startToAct_button = joinPath("resources","buttons","startToAct.png")
        fight_button = joinPath("resources","buttons","fight.png")
        useTeam_button = joinPath("resources","buttons","useTeam.png")
        helpFight_button = joinPath("resources","buttons","helpFight.png")
        sureEnter_button = joinPath("resources","buttons","sureEnter.png")
        startFight_button = joinPath("resources","buttons","startFight.png")
        GeLiKe_button = joinPath("resources","buttons","GeLiKe.png")
        NiKeLuo_button = joinPath("resources","buttons","NiKeLuo.png")
        FuLiYaDuo_button = joinPath("resources","buttons","FuLiYaDuo.png")
        illusions_button = joinPath("resources","buttons","illusions.png")
        activities_button = joinPath("resources","buttons","activities.png")
        apply_button = joinPath("resources","buttons","apply.png")
        accept_button = joinPath("resources","buttons","accept.png")
        submit_button = joinPath("resources","buttons","submit.png")
        getItem_button = joinPath("resources","buttons","getItem.png")
        closeNotice_button = joinPath("resources","buttons","closeNotice.png")
        noReminders_button = joinPath("resources","buttons","noReminders.png")
        add_button = joinPath("resources","buttons","add.png")
        coinRaw_button = joinPath("resources","buttons","coinRaw.png")
        craftCoinRaw_button = joinPath("resources","buttons","craftCoinRaw.png")
        expRaw_button = joinPath("resources","buttons","expRaw.png")
        craftExpRaw_button = joinPath("resources","buttons","craftExpRaw.png")
        ticketRaw_button = joinPath("resources","buttons","ticketRaw.png")
        craftTicketRaw_button = joinPath("resources","buttons","craftTicketRaw.png")
        sure_button = joinPath("resources","buttons","sure.png")
        cancel_button = joinPath("resources","buttons","cancel.png")
        craftSure_button = joinPath("resources","buttons","craftSure.png")
        friends_button = joinPath("resources","buttons","friends.png")
        home_button = joinPath("resources","buttons","home.png")
        base_button = joinPath("resources","buttons","base.png")
        quarry_button = joinPath("resources","buttons","quarry.png")
        ore_button = joinPath("resources","buttons","ore.png")
        building_button = joinPath("resources","buttons","buildingOccupancy.png")
        building_switch_button = joinPath("resources","buttons","buildingSwitch.png")
        backyard_button = joinPath("resources","buttons","backyard.png")
        switch_button = joinPath("resources","buttons","switch.png")
        friendOrders_button = joinPath("resources","buttons","friendOrders.png")
        tradingPost_button = joinPath("resources","buttons","tradingPost.png")
    
    class _Numbers:
        a0 = joinPath("resources","numbers","0.png")
        a1 = joinPath("resources","numbers","1.png")
        a2 = joinPath("resources","numbers","2.png")
        a3 = joinPath("resources","numbers","3.png")
        a4 = joinPath("resources","numbers","4.png")
        a5 = joinPath("resources","numbers","5.png")
        a6 = joinPath("resources","numbers","6.png")
        a7 = joinPath("resources","numbers","7.png")
        a8 = joinPath("resources","numbers","8.png")
        a9 = joinPath("resources","numbers","9.png")
        a10 = joinPath("resources","numbers","10.png")
        a11 = joinPath("resources","numbers","11.png")
        a12 = joinPath("resources","numbers","12.png")
        a13 = joinPath("resources","numbers","13.png")
        a14 = joinPath("resources","numbers","14.png")
        a15 = joinPath("resources","numbers","15.png")
        a16 = joinPath("resources","numbers","16.png")
        a17 = joinPath("resources","numbers","17.png")
        a18 = joinPath("resources","numbers","18.png")
    
    class _Orders:
        build61 = joinPath("resources","orders","build61.png")
        build81 = joinPath("resources","orders","build81.png")
        build101 = joinPath("resources","orders","build101.png")
        build162 = joinPath("resources","orders","build162.png")
        build182 = joinPath("resources","orders","build182.png")
        coin1012 = joinPath("resources","orders","coin1012.png")
        exp1012 = joinPath("resources","orders","exp1012.png")
        class Description:  ...
        class CraftEnable: ...
        CoinOrders = (coin1012)
        ExpOrders = (exp1012)
        BuildOrders = (build101, build162, build182, build61, build81)
        
        @staticmethod
        def amount(order:str):
            match order:
                case JCZXGame._Orders.build101: return 10
                case JCZXGame._Orders.build61: return 6
                case JCZXGame._Orders.build81: return 8
                case JCZXGame._Orders.build162: return 16
                case JCZXGame._Orders.build182: return 18
                case JCZXGame._Orders.coin1012: return 10
                case JCZXGame._Orders.exp1012: return 10
    
    def getUserOrderPaths(self) -> list[tuple[str, _Orders.Description, _Orders.CraftEnable]]:
        """返回用户设置的订单路径及其介绍"""
        result = []
        if self.config.build61.enable: result.append((self._Orders.build61, "构建6换1", self.config.build61.craft))
        if self.config.build81.enable: result.append((self._Orders.build81, "构建8换1", self.config.build81.craft))
        if self.config.build101.enable: result.append((self._Orders.build101, "构建10换1", self.config.build101.craft))
        if self.config.build162.enable: result.append((self._Orders.build162, "构建16换2", self.config.build162.craft))
        if self.config.build182.enable: result.append((self._Orders.build182, "构建18换2", self.config.build182.craft))
        if self.config.coin1012.enable: result.append((self._Orders.coin1012, "星币10换12w", self.config.coin1012.craft))
        if self.config.exp1012.enable: result.append((self._Orders.exp1012, "经验10换12w", self.config.exp1012.craft))
        return result
    
    class _ScreenLocs:
        friend = joinPath("resources","locations","friend.png")
        levels = joinPath("resources","locations","levels.png")
        visiting = joinPath("resources","locations","visiting.png")
        choiceFriendTP = joinPath("resources","locations","choiceFriendTP.png")
        enoughSmallCrytal = joinPath("resources","locations","enoughSmallCrytal.png")
        fightWin = joinPath("resources","locations","fightWin.png")
        onFight = joinPath("resources","locations","onFight.png")
        inIllusions = joinPath("resources","locations","inIllusions.png")
        ZhouSiDun = joinPath("resources","locations","ZhouSiDun.png")
        ZhouSi_a_1 = joinPath("resources","locations","ZhouSi_a_1.png")
        ZhouSi_a_3 = joinPath("resources","locations","ZhouSi_a_3.png")
        ZhouSi_b_1 = joinPath("resources","locations","ZhouSi_b_1.png")
        ZhouSi_b_2 = joinPath("resources","locations","ZhouSi_b_2.png")
        ZhouSi_b_3 = joinPath("resources","locations","ZhouSi_b_3.png")
        ARuiSi_1 = joinPath("resources","locations","ARuiSi_1.png")
        ARuiSi_2 = joinPath("resources","locations","ARuiSi_2.png")
        ARuiSi_3 = joinPath("resources","locations","ARuiSi_3.png")
        ARuiSi_4 = joinPath("resources","locations","ARuiSi_4.png")
        ZhouSiBoss_a = joinPath("resources","locations","ZhouSiBoss_a.png")
        ZhouSiBoss_b = joinPath("resources","locations","ZhouSiBoss_b.png")
        GeLiKeIllusionSwipe = joinPath("resources","locations","GeLiKeIllusionSwipe.png")
        notEnough = joinPath("resources","locations","notEnough.png")
        whateverTradingPost = joinPath("resources","locations","whateverTradingPost.png")
        illusionAward = joinPath("resources","locations","illusionAward.png")
        emptyPlace2x2 = joinPath("resources","locations","emptyPlace2x2.png")
        helpFriend = joinPath("resources","locations","helpFriend.png")
        sureEnter = joinPath("resources","buttons","sureEnter.png")
        illusions = joinPath("resources","locations","illusions.png")
        activities = joinPath("resources","locations","activities.png")
        notEnoughAsk = joinPath("resources","locations","notEnoughAsk.png")
        tabBar = joinPath("resources","locations","tabBar.png")
        getItem= joinPath("resources","buttons","getItem.png")
        home = joinPath("resources","buttons","friends.png")
        tradingPost = joinPath("resources","locations","tradingPost.png")
        friendTradingPost = joinPath("resources","locations","friendTradingPost.png")
        quarry = joinPath("resources","locations","quarry.png")
        billboard = joinPath("resources","buttons","noReminders.png")
        base = joinPath("resources","buttons","buildingOccupancy.png")
        # orderStop = joinPath("resources","locations","orderStop.png")
        building_switch = joinPath("resources","buttons","buildingSwitch.png")
    
    class _Pos:
        choiceFriendTPPos = None
        acceptPos = None
        fightPos = None
        activitiesPos = None
        homePos = None
        backPos = None
        cancelPos = None
        surePos = None
        craftPos = None
        friendPos = None
        basePos = None
        tradingPos = None
        buildingOccupancyPos = None
    
    def __init__(self, adb_path: str, logger:logging.Logger, config:JsonConfig) -> None:
        self.adb_path = adb_path
        self.log = logger
        self.config = config
        self.startupinfo = subprocess.STARTUPINFO()
        self.startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
        self.startupinfo.wShowWindow = subprocess.SW_HIDE
        self.submitOrders = []
        self.size = None
    
    def initDeviceInfor(self):
        """更新设备信息"""
        self.size = None
        self.getScreenSize()
        self.Pos = self._Pos()
        self.ScreenCut= self._ScreenCut(self.width, self.height)
    
    @property
    def width(self):    return self.getScreenSize()[0]
    @property
    def height(self):   return self.getScreenSize()[1]
    @property
    def inLocationLevels(self): return self.inLocation(self.ScreenLocs.levels, self.ScreenCut.cut3x3(1, 1))
    @property
    def inLocationActivities(self): return self.inLocation(self.ScreenLocs.activities, self.ScreenCut.cut3x3(1, 0))
    @property
    def inLocationIllusions(self): return self.inLocation(self.ScreenLocs.illusions, self.ScreenCut.cut3x4(0, 3))
    @property
    def inLocationWhateverIllusion(self): return self.inLocation(self.ScreenLocs.illusionAward, self.ScreenCut.cut9x2(8, 0))
    @property
    def needSureEnterFight(self): return self.inLocation(self.ScreenLocs.sureEnter, self.ScreenCut.cut2x2(1, 1))
    @property
    def inLocationFriendTradingPost(self): return self.inLocation(self.ScreenLocs.friendTradingPost, self.ScreenCut.cut7x2(0, 1))
    @property
    def inLocationTradingPost(self): return self.inLocation(self.ScreenLocs.tradingPost, self.ScreenCut.cut7x2(0, 1))
    @property
    def inLocationONfight(self): return self.inLocation(self.ScreenLocs.onFight, self.ScreenCut.cut4x3(0, 0), 0.5)
    @property
    def inLocationFightWin(self): return self.inLocation(self.ScreenLocs.fightWin, self.ScreenCut.cut2x2(0, 0))
    @property
    def inLocationGetItems(self): return self.inLocation(self.ScreenLocs.getItem, self.ScreenCut.cut3x2(1, 0), 0.8)
    @property
    def inLocationEnoughSmallCrystal(self): return self.inLocation(self.ScreenLocs.enoughSmallCrytal, self.ScreenCut.cut3x7(0, 6))
    @property
    def inLocationWhateverTradingPost(self): return self.inLocation(self.ScreenLocs.whateverTradingPost, self.ScreenCut.cut7x2(0, 1))
    @property
    def inLocationChoiceTradingPost(self):  return self.inLocation(self.ScreenLocs.choiceFriendTP, self.ScreenCut.cut3x3(0, 0))
    
    def inLocationWhateverIllusionLevelsFget(self): return self.inLocation(self.ScreenLocs.inIllusions, self.ScreenCut.cut4x3(0, 2))
    @property
    def inLocationWhateverIllusionLevels(self):  return self.inLocationWhateverIllusionLevelsFget()

    Buttons = _Buttons()
    Numbers = _Numbers()
    Orders = _Orders()
    ScreenLocs = _ScreenLocs()
    Pos = _Pos()
    
    @staticmethod
    def check(func):
        def wrapper(self, *args, **kwargs):
            if self.adb_path:
                return func(self, *args, **kwargs)
        return wrapper
    
    def inLocation(self, screen_loc, cutPoints:tuple[tuple[int, int]] = None, per = 0.9) -> bool:
        return bool(self.findImageCenterLocations(screen_loc, cutPoints, per))
    
    def getScreenSize(self) -> tuple[int, int]:
        if self.size:
            return self.size
        else:
            msg = subprocess.check_output([self.adb_path, "-s", self.device, "shell", "wm", "size"], startupinfo = self.startupinfo).decode().split(" ")[-1].replace("\r\n","")
            w, h = map(int, msg.split("x"))
            self.size = (w, h)
        return (w, h)
    
    @check
    def screenshot(self) -> bytes:
        return subprocess.check_output([self.adb_path, "-s", self.device, "exec-out", "screencap", "-p"], startupinfo = self.startupinfo)
    
    def grayScreenshot(self, cutPoints = None):
        screenshot = cv2.imdecode(np.frombuffer(self.screenshot(), np.uint8), cv2.IMREAD_GRAYSCALE)
        if cutPoints:
            (x0, y0), (x1, y1) = cutPoints
            return screenshot[y0:y1, x0:x1]
        else:
            return screenshot
    
    def click(self, x:int, y:int, wait:int = 0):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "tap", str(x), str(y)], startupinfo = self.startupinfo)
        sleep(wait)
    
    def waitClick(self, x:int, y:int, newLocation:str | Callable, wait = 0):
        while True:
            self.click(x, y)
            if isinstance(newLocation, str):
                if self.inLocation(newLocation):
                    break
            else:
                if newLocation():
                    break
            sleep(0.3)
        sleep(wait)
                    
    def clickButton(self, button_path:str, index:int = 0, wait:int = 0, log:bool = True, cutPoints = None, per = 0.9) -> tuple[int, int] | None:
        if locations := self.findImageCenterLocations(button_path, cutPoints, per):
            self.click(*locations[index], wait)
            self.log.debug(f"{locations}")
            # self.log.info(f"点击按钮{button_path}")
            return locations[index]
        else:
            if log:
                self.log.warning(f"未找到按钮{button_path}")
            return None

    def clickFightButton(self):
        return self._clickAndMsg(self.Buttons.fight_button, "前往【关卡界面】", "前往【关卡界面】失败", wait = 1, cutPoints = self.ScreenCut.cut4x2(3, 0))

    def clickActivitiesButton(self):
        return self._clickAndMsg(self.Buttons.activities_button, "前往【活动探索】", "前往【活动探索】失败", wait = 1, cutPoints = self.ScreenCut.cut3x3(1, 0))
    
    def clickIllusionsButton(self):
        return self._clickAndMsg(self.Buttons.illusions_button, "前往【碎星虚影】", "前往【碎星虚影】失败", wait = 1, cutPoints = self.ScreenCut.cut1x2(0, 1))
    
    def clickGeLiKeIllusion(self):
        return self._clickAndMsg(self.Buttons.GeLiKe_button, "前往【戈里克虚影】", "前往【戈里克虚影】失败", wait = 1, cutPoints = self.ScreenCut.cut1x2(0, 1))
    
    def clickNiKeLuoIllsuon(self):
        return self._clickAndMsg(self.Buttons.NiKeLuo_button, "前往【尼克罗虚影】", "前往【尼克罗虚影】失败", wait = 1, cutPoints = self.ScreenCut.cut2x1(1, 0))
    
    def clickIllusionZhouSi(self):
        return self._clickAndMsg(self.Buttons.ZhouSi_button, wait = 1, cutPoints = self.ScreenCut.cut3x1(1, 0))
    
    def clickIllusionARuiSi(self):
        return self._clickAndMsg(self.Buttons.ARuiSi_button, wait = 1, cutPoints = self.ScreenCut.cut3x1(1, 0))
    
    def clickIllusionFuLiYaDuo(self):
        return self._clickAndMsg(self.Buttons.FuLiYaDuo_button, wait = 1 ,cutPoints = self.ScreenCut.cut3x1(1, 0))
    
    def clickStartFight(self):
        if loc := self._clickAndMsg(self.Buttons.startFight_button, "准备战斗", "准备战斗异常", wait = 1, cutPoints = self.ScreenCut.cut3x4(2, 3)):
            if self.needSureEnterFight: self.makeSureEnter(2)
        return loc

    def clickHelpFight(self, index:int = None):
        return self._clickAndMsg(self.Buttons.helpFight_button, index = index, wait = 0.5, cutPoints = self.ScreenCut.cut2x1(1, 0))
    
    def clickCloseUseThisTeam(self, index:int = None):
        return self._clickAndMsg(self.Buttons.useTeam_button, index = index, wait = 0.1, cutPoints = self.ScreenCut.cut4x1(3, 0))
    
    def clickStartToAct(self, wait = 0, log = True):
        if log:
            return self._waitClickAndMsg(self.Buttons.startToAct_button, self.inLocationWhateverIllusionLevelsFget, "开始战斗", "开始战斗异常", wait = wait, cutPoints = self.ScreenCut.cut3x4(2, 3))
        else:
            return self._waitClickAndMsg(self.Buttons.startToAct_button, self.inLocationWhateverIllusionLevelsFget, wait = wait, cutPoints = self.ScreenCut.cut3x4(2, 3))
    
    def clickSkipAnimation(self, log = False):
        return self._clickAndMsg(self.Buttons.skipAnimation_button, log = log, cutPoints = self.ScreenCut.cut4x3(3, 0), per = 0.8)
    
    def clickReadyTeamPlane(self):
        return self._clickAndMsg(self.Buttons.plane_button, wait = 0.7, log = False, cutPoints = self.ScreenCut.cut3x7(1, 6))
    
    def clickGetItems(self, wait = 0.3, log = False):
        return self._clickAndMsg(self.ScreenLocs.getItem, wait = wait, log = log, cutPoints = self.ScreenCut.cut3x2(1, 0), per = 0.8)
    
    def getQuarryTime(self) -> int:
        """获取矿场结算时间"""
        self.takeOre()
        if self.config.quarry_time:
            self.log.info("正在等待【矿场结算时间】")
            return self.config.quarry_time
        self.log.info("未设置【矿场结算】时间正在挂机获取")
        self.switchQuarryWork()
        self.back()
        self.gotoBase()
        self.log.info("正在【挂机中】")
        while True:
            if self.inLocation(self.ScreenLocs.base, self.ScreenCut.cut7x3(0, 2)):
                if self.findImageCenterLocation(self.Buttons.ore_button, self.ScreenCut.cut3x2(1, 1)):
                    self.config.set_config("quarry_time",datetime.now().minute)
                    quarry_time = self.config.quarry_time
                    self.log.info(f"设置【矿场结算】时间 {quarry_time} 分")
                    self.switchQuarryWork()
                    return quarry_time
            else:
                self.gotoBase()
            sleep(60)
    
    def gotoHome(self):
        if self.inLocation(self.ScreenLocs.home, self.ScreenCut.cut3x7(0,6)):
            return
        if self.Pos.homePos:
            self.click(*self.Pos.homePos)
            self.log.info("前往【主界面】")
        else:
            if loc := self._clickAndMsg(self.Buttons.home_button, "前往【主界面】", "前往【主界面】失败", cutPoints = self.ScreenCut.cut3x7(0,0)):
                self.Pos.homePos = loc
            else:
                self.back(1)
                self.makeSure(5)
                self.gotoHome()
        sleep(3)
    
    def gotoLevels(self):
        if self.inLocationLevels:
            return
        else:
            self.gotoHome()
        if self.Pos.fightPos:
            self.click(*self.Pos.fightPos, 1)
            self.log.info("前往【关卡界面】")
        else:
            if loc := self.clickFightButton():
                self.Pos.fightPos = loc
            else:
                self.gotoLevels()
    
    def gotoActivities(self):
        if self.inLocationActivities:
            return
        else:
            self.gotoLevels()
        if self.Pos.acceptPos:
            self.click(*self.Pos.acceptPos, 1)
            self.log.info("前往【活动探索】")
        else:
            if loc := self.clickActivitiesButton():
                self.Pos.acceptPos = loc
            else:
                self.gotoActivities()
    
    def gotoGeLiKeIllusion(self):
        if self.inLocationWhateverIllusion:
            return
        else:
            self.gotoIllusions()
            self.clickGeLiKeIllusion()
            self.gotoGeLiKeIllusion()
    
    def gotoNiKeLuoIllusion(self):
        if self.inLocationWhateverIllusion:
            return
        else:
            self.gotoIllusions()
            self.click
    
    def gotoIllusionZhouSi(self):
        self.gotoGeLiKeIllusion()
        self.swipeUPIllusionList()
        self.clickIllusionZhouSi()
    
    def gotoIllusionARuiSi(self):
        self.gotoGeLiKeIllusion()
        self.clickIllusionARuiSi()
    
    def gotoIllusionFuLiYaDuo(self):
        self.gotoNiKeLuoIllusion()
        self.swipeUPIllusionList()
        self.clickIllusionFuLiYaDuo()
    
    def playIllusionZhouSi(self):
        if loc := self.findImageCenterLocation(self.ScreenLocs.ZhouSi_a_1, cutPoints = self.ScreenCut.cut2x1(1, 0), per = 0.95):
            self.click(*loc, wait = 3)
            # self.waitClick(loc[0], loc[1]+60, self.ScreenLocs.ZhouSi_a_3)
            self.click(self.width//2, self.height//1.7, 7)
            if not self._clickAndMsg(self.ScreenLocs.ZhouSi_a_3, wait = 3, log = False, cutPoints = self.ScreenCut.cut1x2(0, 0)):
                self.autoPlayLevels()
                self._clickAndMsg(self.ScreenLocs.ZhouSi_a_3, wait = 3, log = False, cutPoints = self.ScreenCut.cut1x2(0, 0))
            self._clickAndMsg(self.ScreenLocs.ZhouSiBoss_a,  wait = 3, cutPoints = self.ScreenCut.cut1x2(0, 0), per = 0.8)
            self.autoPlayLevels()
        else:
            self._clickAndMsg(self.ScreenLocs.ZhouSi_b_1, wait = 3, log = False, cutPoints = self.ScreenCut.cut2x1(0, 0))
            self._clickAndMsg(self.ScreenLocs.ZhouSi_b_2, wait = 7, log = False, cutPoints = self.ScreenCut.cut3x3(1, 1))
            if not self._clickAndMsg(self.ScreenLocs.ZhouSi_b_3, wait = 3, log = False, cutPoints = self.ScreenCut.cut1x2(0, 0)):
                self.autoPlayLevels()
                self._clickAndMsg(self.ScreenLocs.ZhouSi_b_3, wait = 3, log = False, cutPoints = self.ScreenCut.cut1x2(0, 0))
            self._clickAndMsg(self.ScreenLocs.ZhouSiBoss_b, wait = 3, cutPoints = self.ScreenCut.cut1x2(0, 0), per = 0.8)
            self.autoPlayLevels()
    
    def playIllusionARuiSi(self):
        self._clickAndMsg(self.ScreenLocs.ARuiSi_1, wait = 3, log = False)
        self._clickAndMsg(self.ScreenLocs.ARuiSi_2, wait = 3, log = False)
        self._clickAndMsg(self.ScreenLocs.ARuiSi_3, wait = 3, log = False)
        self.autoPlayLevels()
        self._clickAndMsg(self.ScreenLocs.ARuiSi_4, wait = 3, log = False)
        self.autoPlayLevels()
        self.click(self.width//2, self.height//4, 3)
        self.autoPlayLevels()
    
    def autoPlayLevels(self):
        while not self.inLocationONfight:
            self.clickSkipAnimation()
            sleep(0.3)
        self._clickAndMsg(self.Buttons.fightAuto_button, log = False, cutPoints = self.ScreenCut.cut4x3(3, 0), per = 0.8)
        while not self.inLocationFightWin:
            if self.inLocationGetItems:
                self.click(self.width//2, self.height//2, 1)
            sleep(0.3)
        self.click(self.width//2, self.height//2, 1)
        self.click(self.width//2, self.height//2, 7)
        
    def gotoIllusions(self):
        if self.inLocationIllusions:
            return
        else:
            self.gotoActivities()
        if not self.clickIllusionsButton():
            self.gotoIllusions()
    
    def gotoFriend(self):
        if self.inLocation(self.ScreenLocs.friend, self.ScreenCut.cut9x9(0, 8)):
            return
        else:
            self.gotoHome()
        if self.Pos.friendPos:
            self.click(*self.Pos.friendPos)
            self.log.info("前往【好友界面】")
        else:
            if loc := self._clickAndMsg(self.Buttons.friends_button, "前往【好友界面】", "前往【好友界面】失败", cutPoints = self.ScreenCut.cut3x7(0,6)):
                self.Pos.friendPos = loc
            else:
                self.gotoFriend()
        sleep(1)
    
    def gotoBase(self):
        if self.inLocation(self.ScreenLocs.base, self.ScreenCut.cut4x3(0, 2)):
            return
        else:
            self.gotoHome()
        if self.Pos.basePos:
            self.click(*self.Pos.basePos)
            self.log.info("前往【基地】")
        else:
            if loc := self._clickAndMsg(self.Buttons.base_button, "前往【基地】", "前往【基地】失败", cutPoints = self.ScreenCut.cut3x7(2, 6)):
                self.Pos.basePos = loc
            else:
                self.gotoBase()
        sleep(3)
    
    def gotoTradingPost(self):
        if self.inLocation(self.ScreenLocs.tradingPost, self.ScreenCut.cut7x2(0, 1)):
            return
        else:
            self.gotoBase()
        if not self._clickAndMsg(self.Buttons.tradingPost_button, "前往【原料交易所】", "前往【原料交易所】失败", cutPoints = self.ScreenCut.cut2x3(1, 1)):
            self.gotoTradingPost()
        sleep(1)
    
    def gotoChoiceFriendTradingPost(self):
        if self.inLocationChoiceTradingPost:
            return
        else:
            if not self.inLocationWhateverTradingPost:
                self.gotoTradingPost()
        if loc := self.Pos.choiceFriendTPPos:
            self.click(*loc)
        else:
            if loc := self._clickAndMsg(self.Buttons.choiceFriendTP_button, cutPoints = self.ScreenCut.cut7x2(0, 1)):
                self.Pos.choiceFriendTPPos = loc
            else:
                self.gotoChoiceFriendTradingPost()
        sleep(0.3)
    
    def addAndCraft(self, num:int):
        loc = self.findImageCenterLocation(self.Buttons.add_button, cutPoints = self.ScreenCut.cut3x3(2, 1))
        for i in range(num - 1):
            self.click(*loc, wait = 0.1)
        sleep(0.5)
        self.craftSure()
    
    def checkAndSpendOrders(self):
        """检查并交付订单"""
        self.__checkOrders()
        if self.inLocation(self.ScreenLocs.tabBar, self.ScreenCut.cut7x1(6, 0)):
            self.swipeUPScreenCenter()
            self.__checkOrders(self.ScreenCut.cut1x2(0, 1))
    
    def __checkOrders(self, cutPoints = None):
        self.log.info("正在检索【订单】")
        grayScreenshot = self.grayScreenshot()
        for img,des,craft in self.getUserOrderPaths():
            # if self._clickAndMsg(img, wait = 0.3, log = False, per = 0.95):
            if locality := self.findImageCenterLocation(img, cutPoints, per = 0.95, grayScreenshot = grayScreenshot):
                self.log.info(f"发现订单【{des}】")
                # if self.findImageCenterLocation(self.ScreenLocs.notEnough, self.ScreenCut.cut3x3(1, 1)):
                templete = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
                h, w = templete.shape
                x, y = locality
                x0, y0 = x-w//2, y+h//2
                x1, y1 = x+w//2, y+h//2+h
                if self.findImageCenterLocation(self.ScreenLocs.notEnough, ((x0, y0), (x1, y1)), 0.8):
                    if not craft:
                        self.log.info("当前订单材料不足")
                        # self._clickAndMsg(self.Buttons.cancel_button, wait = 0.3, cutPoints = self.ScreenCut.cut4x2(1, 1))
                        continue
                    self.click(*locality, 0.3)
                    if img in self.Orders.BuildOrders:
                        ticketRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.ticketRaw_button)
                        self.makeSure(2)
                        #合成黑盒
                        self._clickAndMsg(self.Buttons.craftTicketRaw_button, "点击【稀有黑匣】", "点击【稀有黑匣】失败", wait = 0.3, cutPoints = self.ScreenCut.cut4x2(1, 1))
                        self.addAndCraft(ticketRawNum)
                        self.log.info(f"合成【稀有黑匣】x{ticketRawNum}")
                    elif img in self.Orders.CoinOrders:
                        coinRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.coinRaw_button)
                        self.makeSure(2)
                        #合成星币原料
                        self._clickAndMsg(self.Buttons.craftCoinRaw_button, "点击【星币碎片】", "点击【星币碎片】失败", wait = 0.3, cutPoints = self.ScreenCut.cut4x1(1, 0))
                        self.addAndCraft(coinRawNum)
                        self.log.info(f"合成【星币碎片】x{coinRawNum}")
                    elif img in self.Orders.ExpOrders:
                        expRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.expRaw_button)
                        self.makeSure(2)
                        #合成数据硬盘
                        self._clickAndMsg(self.Buttons.craftExpRaw_button, "点击【数据硬盘】", "点击【数据硬盘】失败", wait = 0.3, cutPoints = self.ScreenCut.cut4x1(2, 0))
                        self.addAndCraft(expRawNum)
                        self.log.info(f"合成【数据硬盘】x{expRawNum}")
                    self.back(0.3)
                    self.back(0.5)
                    # self._clickAndMsg(img, wait = 1)
                    self.click(*locality, 1)
                    self.makeSure2(2)
                    self.submitOrders.append(des)
                else:
                    self.click(*locality, 0.3)
                    self.makeSure2()
                    self.submitOrders.append(des)
                    
    def findRawNumbers(self, Raw_path:str) -> int | None:
        templete = cv2.imread(Raw_path, cv2.IMREAD_GRAYSCALE)
        h, w = templete.shape
        screengray = self.grayScreenshot()
        if locs := self.findImageLeftUPLocations(Raw_path, self.ScreenCut.cut7x1(0, 0)):
            x, y = locs[0]
            y += h
            locality = screengray[x:x+w, y:y+h]
            return self.translateNumber(locality)
        else:
            return None
    
    def translateNumber(self, Raw_num:cv2.typing.MatLike) -> int | None:
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a18, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 18
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a17, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 17
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a16, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 16
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a15, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 15
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a14, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 14
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a13, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 13
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a12, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 12
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a11, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 11
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a10, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 10
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a9, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 9
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a8, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 8
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a7, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 7
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a6, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 6
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a5, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 5
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a4, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 4
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a3, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 3
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a2, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 2
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a1, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 1
        if any(np.where(cv2.matchTemplate(Raw_num, cv2.imread(self.Numbers.a0, cv2.IMREAD_GRAYSCALE), cv2.TM_CCOEFF_NORMED) > 0.9)[0]): return 0
    
    def makeSure(self, wait = 0.3):
        if self.Pos.surePos:
            self.click(*self.Pos.surePos, wait)
        else:
            loc = self._clickAndMsg(self.Buttons.sure_button, wait = wait, cutPoints = self.ScreenCut.cut4x2(2, 1))
            self.Pos.surePos = loc
    
    def makeSureEnter(self, wait = 0.5):
        if self.Pos.surePos:
            self.click(*self.Pos.surePos, wait)
        else:
            loc = self._clickAndMsg(self.Buttons.sureEnter_button, wait = wait, cutPoints = self.ScreenCut.cut2x2(1, 1))
            self.Pos.surePos = loc
    
    def makeSureQuit(self, wait = 3):
        if self.Pos.surePos:
            self.click(*self.Pos.surePos, wait)
        else:
            loc = self._clickAndMsg(self.Buttons.sureQuit_button, wait = wait, cutPoints = self.ScreenCut.cut2x2(1, 1))
            self.Pos.surePos = loc
    
    def quitLevels(self):
        self.back()
        self.makeSureQuit()
    
    def makeSure2(self, wait = 1):
        self.makeSure(wait)
        # self.click(self.width//2, self.height//2, wait = 0.3)
        self.clickGetItems()
    
    def craftSure(self):
        if self.Pos.craftPos:
            self.click(*self.Pos.craftPos, wait = 1)
        else:
            loc = self._clickAndMsg(self.Buttons.craftSure_button, wait = 1, cutPoints = self.ScreenCut.cut3x3(2, 2))
            self.Pos.craftPos = loc
        self.click(self.width//2, self.height//1.2, wait = 0.5)
    
    def tellMeSubmitOrders(self):
        """告知我已交付订单"""
        if self.submitOrders:
            self.log.info("已提交订单"+" ".join(self.submitOrders))
            self.submitOrders.clear()
        else:
            self.log.info("无满足条件订单提交")
    
    def gotoFriendOrdersAndSpend(self):
        # self.useFriendListCheckOrderAndSpend()
        self.useChoiceFriendCheckOrderAndSpend()
        self.tellMeSubmitOrders()

    def useChoiceFriendCheckOrderAndSpend(self):
        """使用订单库选择好友进入订单库进行检测交付"""
        index = 0
        while True:
            self.gotoChoiceFriendTradingPost()
            grayScreenshot = self.grayScreenshot()
            visits = self.findImageCenterLocations(self.Buttons.visit_button, cutPoints = self.ScreenCut.cut1x2(0, 1), grayScreenshot = grayScreenshot)
            visiting = self.findImageCenterLocation(self.ScreenLocs.visiting, cutPoints = self.ScreenCut.cut1x2(0, 1), grayScreenshot = grayScreenshot)
            if not visits:
                break
            if visiting:
                visits = [(x, y) for x, y in visits if x > visiting[0]]
            if not visits:
                break
            else:
                self.log.debug(visits)
                for loc in visits:
                    index += 1
                    self.click(*loc, wait = 1.5)
                    self.log.info(f"进入【好友交易所】{index}")
                    self.checkAndSpendOrders()
                    self.gotoChoiceFriendTradingPost()
                self.swipeLeftScreenCenter()
        self.gotoHome()
        self.gotoHome()
    
    def useFriendListCheckOrderAndSpend(self):
        """使用好友列表进入订单库进行检测交付，稳定性较差，只是固定次数进入好友订单库进行检测，不建议使用"""
        if self.inLocation(self.ScreenLocs.friendTradingPost, self.ScreenCut.cut7x2(0, 1)):
            #check orders
            self.checkAndSpendOrders()
        if not self.inLocation(self.ScreenLocs.friend, self.ScreenCut.cut9x9(0, 8)):
            self.gotoFriend()
        index = 0
        for i in range(11):
            if locations := self.findImageCenterLocations(self.Buttons.backyard_button, self.ScreenCut.cut3x1(2, 0)):
                for locs in locations:
                    self.click(*locs, 0.1)
                    index += 1
                    if not self._clickAndMsg(self.Buttons.friendOrders_button, f"进入【好友交易所】{index}", f"进入【好友交易所】{index}失败", wait=0.1, cutPoints = self.ScreenCut.cut4x1(2, 0)):
                        self.gotoHome()
                        self.log.warning(f"未处于【好友列表】 任务结束")
                        self.tellMeSubmitOrders()
                        return
                    #check orders
                    self.checkAndSpendOrders()
                    self.back()
                    self.click(*locs, 0.2)
                self.swipeUPScreenCenter()
            else:
                break
        self.gotoHome()
    
    def back(self, wait:int = 1):
        if self.Pos.backPos:
            self.click(*self.Pos.backPos, wait)
            self.log.info("返回上一界面")
        else:
            loc = self._clickAndMsg(self.Buttons.back_button, "返回上一界面", "返回上一界面失败", wait = wait, cutPoints = self.ScreenCut.cut3x7(0, 0))
            self.Pos.backPos = loc
    
    def takeOre(self):
        if self.inLocation(self.ScreenLocs.base, self.ScreenCut.cut4x3(0, 2)):
            if self._clickAndMsg(self.Buttons.ore_button, "收集矿物", log = False, cutPoints = self.ScreenCut.cut3x2(1, 1)):
                sleep(1)
                self.click(self.width//2, self.height//1.2)
                sleep(0.7)
                return True
            else:
                self.log.info("暂未发现矿物")
                sleep(0.7)
                return False
        else:
            self.gotoBase()
            self.takeOre()
        sleep(1)
    
    def waitTakeOre(self):
        while True:
            if self.takeOre():
                return True
            else:
                sleep(60)
    
    def gotoBuildingOccupancy(self):
        if self.inLocation(self.ScreenLocs.building_switch, cutPoints = self.ScreenCut.cut4x1(2, 0)):
            return
        else:
            self.gotoBase()
        if self.Pos.buildingOccupancyPos:
            self.click(*self.Pos.buildingOccupancyPos)
            self.log.info("前往【驻员管理】")
        else:
            if loc := self._clickAndMsg(self.Buttons.building_button, "前往【驻员管理】", "前往【驻员管理】失败", cutPoints = self.ScreenCut.cut4x3(0, 2)):
                self.Pos.buildingOccupancyPos = loc
            else:
                self.gotoBuildingOccupancy()
        sleep(1)
    
    def switchQuarryWork(self):
        if not self.inLocation(self.ScreenLocs.building_switch, cutPoints = self.ScreenCut.cut4x1(2, 0)):
            self.gotoBuildingOccupancy()
        if self._clickAndMsg(self.Buttons.building_switch_button, "点击【矿场预设】", "点击【矿场预设】失败", 2, cutPoints = self.ScreenCut.cut3x1(2, 0)):
            sleep(0.5)
            self._clickAndMsg(self.Buttons.switch_button, "交换工作员工", "交换工作员工失败", cutPoints = self.ScreenCut.cut2x1(1, 0))
    
    def _clickAndMsg(self, button_path, infoMsg:str = None, warnMsg:str = None, index:int = 0, wait:int = 0, log:bool = True, cutPoints = None, per = 0.9) -> tuple[int, int] | None:
        if loc := self.clickButton(button_path, index, wait, log, cutPoints, per):
            if infoMsg: self.log.info(infoMsg)
            return loc
        else:
            if warnMsg: self.log.warning(warnMsg)
            return None
    
    def _waitClickAndMsg(self, button_path, newLocation: Callable | str, infoMsg:str = None, warnMsg:str = None, index:int = 0, wait:int = 0, log:bool = False, cutPoints = None, per = 0.9) -> None:
        """等待并点击按钮，性能消耗较大,稳定性较差
        - newLocation 点击按钮后前往的界面
        """
        while True:
            self._clickAndMsg(button_path, infoMsg, warnMsg, index, 0, log, cutPoints, per)
            if isinstance(newLocation, str):
                if self.inLocation(newLocation):
                    break
            else:
                if newLocation():
                    break
            sleep(0.3)
        sleep(wait)
    
    def findImageLeftUPLocations(self, button_path:str, cutPoints = None) -> list[tuple[int, int]] | None:
        if cutPoints:
            x0, y0 = cutPoints[0]
        else:
            x0, y0 = 0, 0
        screenshot_gray = self.grayScreenshot(cutPoints)
        template_gray = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        matcher = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(matcher > 0.9)
        if any(locations[0]):
            tmp_x = [locations[0][0]]
            tmp_y = [locations[1][0]]
            for x,y in zip(*locations):
                if y-10 >= tmp_y[-1]:
                    tmp_x.append(x)
                    tmp_y.append(y)
                    continue
                if x-10 >= tmp_x[-1]:
                    tmp_x.append(x)
                    tmp_y.append(y)
                    continue
            result = [(x+x0, y+y0) for x,y in zip(tmp_x, tmp_y)]
            return result
        else:
            return None
    
    def findImageCenterLocation(self, button_path:str, cutPoints = None, per = 0.9, grayScreenshot = None) -> tuple[int, int] | None:
        locations = self.findImageCenterLocations(button_path, cutPoints, per, grayScreenshot)
        if locations:
            return locations[0]
        else:
            return None

    def findHelpFightFriendsWifeLocations(self) -> list[tuple[int, int]] | None:
        def _(z:tuple):
            z = list(z)
            z[1] += 60
            return tuple(z)
        if tmp := self.findImageCenterLocations(self.ScreenLocs.helpFriend, cutPoints = self.ScreenCut.cut2x1(1, 0)):
            return list(map(_, tmp))
        else:
            return None
    
    def findImageCenterLocations(self, button_path:str, cutPoints:tuple[tuple[int, int]] = None, per:float = 0.9, grayScreenshot = None) -> list[tuple[int, int]] | None:
        if cutPoints:
            x0, y0 = cutPoints[0]
        else:
            x0, y0 = 0, 0
        if grayScreenshot is None:
            screenshot_gray = self.grayScreenshot(cutPoints)
        else:
            if cutPoints:
                (x0, y0), (x1, y1) = cutPoints
                screenshot_gray = grayScreenshot[y0:y1, x0:x1]
            else:
                screenshot_gray = grayScreenshot
        template_gray = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        matcher = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(matcher > per)
        h, w= template_gray.shape[0:2]
        if any(locations[0]):
            tmp_y = [locations[0][0]]
            tmp_x = [locations[1][0]]
            for y,x in zip(*locations):
                if x-10 >= tmp_x[-1]:
                    tmp_x.append(x)
                    tmp_y.append(y)
                    continue
                if y-10 >= tmp_y[-1]:
                    tmp_x.append(x)
                    tmp_y.append(y)
                    continue
            result = [((x+w//2)+x0,(y+h//2)+y0) for x,y in zip(tmp_x,tmp_y)]
            return result
        else:
            return None
    
    def accept(self):
        if self.Pos.acceptPos:
            self.click(*self.Pos.acceptPos, 0.7)
        else:
            if loc := self._clickAndMsg(self.Buttons.accept_button, "点击【同意】x∞", wait = 0.7, log = False, cutPoints = self.ScreenCut.cut3x2(2, 0)):
                self.Pos.acceptPos = loc
    
    def swipe(self, x1:int, y1:int, x2:int, y2:int, duration:int = 200, wait:int = 0):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)], startupinfo = self.startupinfo)
        sleep(wait)
    
    def dragAndDrop(self, x1:int, y1:int, x2:int, y2:int, duration:int = 200, wait:int = 0):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "draganddrop", str(x1), str(y1), str(x2), str(y2), str(duration)], startupinfo = self.startupinfo)
        if wait:
            sleep(wait)
    
    def swipeUPScreenCenter(self, wait = 1.5):
        self.swipe(self.width//2, self.height//1.4, self.width//2, self.height//2, 200, wait)

    def swipeLeftScreenCenter(self, wait = 1.5):
        self.swipe(self.width//1.6, self.height//2, self.width//2, self.height//2, 200, wait)
    
    def swipeUPIllusionList(self):
        if loc := self.findImageCenterLocations(self.ScreenLocs.GeLiKeIllusionSwipe, cutPoints = self.ScreenCut.cut3x1(1, 0), per = 0.8):
            x, y = loc[-1]
            self.log.debug(f"{loc}")
            self.swipe(x, y, x, y-200, wait = 0.5)
        return loc
    
    def setDevice(self, device):
        self.device = device
        self.initDeviceInfor()
    
    def setADBPath(self, path):
        self.adb_path = path
    
    @check
    def devices(self) -> list[str]:
        try:
            info = subprocess.check_output([self.adb_path, "devices"], startupinfo = self.startupinfo)
            return list(map(lambda x:x[:x.find("\t")], info.decode().split("\r\n")))[1:-2]
        except:
            self.log.error("adb端口占用，或者模拟器未打开，请重启\打开模拟器，亦或者电脑")
            return []
            
class WorkThread(QThread):
    ORDER = "交付订单"
    SWITCH = "矿场换班"
    DEBUG = "Debug"
    ACCEPT = "自动同意申请"
    AWARD = "刷助战奖励"
    ONLY_THIS_ORDERS = "仅当前订单"
    SMALL_CRYSTAL = "虚影微晶任务"
    
    def __init__(self, adb:JCZXGame = None, log:logging.Logger = None, config:JsonConfig = None) -> None:
        super().__init__()
        self.adb = adb
        self.log = log
        self.mode = self.DEBUG
        self.config = config
    
    def stop(self):
        if not self.isRunning(): return
        match self.mode:
            case self.ORDER:
                self.adb.tellMeSubmitOrders()
            case self.SWITCH:
                ...
        self.terminate()
    
    def setMode(self, mode:str):
        self.mode = mode
    
    def run(self) -> None:
        try:
            match self.mode:
                case self.ORDER:
                    self.spendOrder()
                case self.SWITCH:
                    self.switchWork()
                case self.DEBUG:
                    self.__debug()
                case self.ACCEPT:
                    self.autoAccept()
                case self.AWARD:
                    self.award()
                case self.ONLY_THIS_ORDERS:
                    self.only_ths_orders()
                case self.SMALL_CRYSTAL:
                    self.small_crystal()
                case _:
                    self.log.error(f"未知模式 {self.mode}")
        except Exception as e:
            self.log.error(f"捕获到错误抛出 {e}")

    def __debug(self):
        self.adb.gotoChoiceFriendTradingPost()
        self.adb.swipeLeftScreenCenter()
        ...
        
    def setADB(self, adb):
        self.adb = adb
    
    def setLog(self, log):
        self.log = log
    
    @staticmethod
    def check(func):
        def _(self, *args, **kwargs):
            if self.config.adb_path:
                if self.config.adb_device:
                    func(self, *args, **kwargs)
                else:
                    self.log.error("当前未设置【设备】")
            else:
                self.log.error("当前未选择【ADB调试路径】")
        return _
        
    @check
    def spendOrder(self):
        self.log.info("开始【交付订单】任务")
        self.adb.gotoTradingPost()
        #check orders
        self.adb.checkAndSpendOrders()
        self.adb.gotoFriendOrdersAndSpend()
        self.log.info("【交付订单】任务结束")
    
    @check
    def switchWork(self):
        self.log.info("开始【矿场换班】任务")
        quarry_time1 = self.adb.getQuarryTime()
        quarry_time2 = (quarry_time1+30)%60
        while True:
            now_minute = datetime.now().minute
            # self.log.debug(f"{now_minute} {quarry_time1} {quarry_time2}")
            if now_minute in (quarry_time1, quarry_time1-1, quarry_time1-2, quarry_time2, quarry_time2-1,quarry_time2-2):
                self.log.info("即将到达【矿场结算】时间")
                self.adb.switchQuarryWork()
                self.adb.back()
                self.adb.waitTakeOre()
                self.adb.switchQuarryWork()
                self.adb.back()
            sleep(60)

    @check
    def autoAccept(self):
        self.log.info("开始【自动同意申请】任务")
        self.adb.gotoFriend()
        self.adb._clickAndMsg(self.adb.Buttons.apply_button, "前往【申请】界面", wait = 0.3, log = False, cutPoints = self.adb.ScreenCut.cut4x1(0, 0))
        while True:
            self.adb.accept()
    
    @check
    def award(self):
        self.log.info("开始【刷取助战奖励】任务")
        for i in range(20):
            self.adb.gotoGeLiKeIllusion()
            if i == 0:  sleep(2)
            self.adb.clickStartFight()
            # self.adb.clickCloseUseThisTeam(1)
            self.adb.clickHelpFight(0)
            self.adb.clickReadyTeamPlane()
            if FriendsWifeLocations := self.adb.findHelpFightFriendsWifeLocations():
                if emptyLocation := self.adb.findImageCenterLocation(self.adb.ScreenLocs.emptyPlace2x2):
                    self.adb.dragAndDrop(*FriendsWifeLocations[0], *emptyLocation, 500, wait = 0.5)
                else:
                    self.adb.gotoHome()
                    self.log.info("当前1号队伍无2x2空位 已停止任务")
                    break
            else:
                self.adb.gotoHome()
                self.log.info("当前无好友 或 今日好友助战已超过50次 已停止任务")
                break
            self.adb.back(0.5)
            self.adb.clickStartToAct(log = False)
            self.adb.quitLevels()
            self.log.info(f"助战 {i+1}次")
        self.adb.gotoHome()
        self.log.info("【助战任务】结束")
    
    @check
    def only_ths_orders(self):
        self.log.info("开始【检索交付当前订单】任务")
        if self.adb.inLocationWhateverTradingPost:
            self.adb.checkAndSpendOrders()
        else:
            self.adb.gotoTradingPost()
            self.adb.checkAndSpendOrders()
        self.adb.tellMeSubmitOrders()
        self.log.info("【检索交付当前订单】结束")
    
    @check
    def small_crystal(self):
        self.log.info("开始【虚影微晶】任务")
        adb = self.adb
        match self.config.illusion.level.index:
            case 0:
                #阿瑞斯
                adb.gotoGeLiKeIllusion()
                while not adb.inLocationEnoughSmallCrystal:
                    adb.gotoIllusionARuiSi()
                    adb.clickStartFight()
                    adb.clickCloseUseThisTeam(0 if self.config.illusion.teamNum else 1)
                    adb.clickStartToAct(0, False)
                    adb.playIllusionARuiSi()
                self.log.info("微晶已满【虚影微晶】任务结束")
            case 1:
                #宙斯
                adb.gotoGeLiKeIllusion()
                while not adb.inLocationEnoughSmallCrystal:
                    adb.gotoIllusionZhouSi()
                    adb.clickStartFight()
                    adb.clickCloseUseThisTeam(0 if self.config.illusion.teamNum else 1)
                    adb.clickStartToAct(0, False)
                    adb.playIllusionZhouSi()
                self.log.info("微晶已满【虚影微晶】任务结束")
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = MainManager(app)
    manager.setupUi()