from typing import Any
from os.path import exists,join,abspath
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

DEFAULT_CONFIGS = {
    "adb_path": None,
    "adb_device": None,
    "quarry_time": None,
    "orders":{
        "build_61":{
            "enable": True,
            "time": 0,
        },
        "build_81":{
            "enable": True,
            "time": 0,
        },
        "build_101":{
            "enable": False,
            "time": 0,
        },
        "build_162":{
            "enable": True,
            "time": 0,
        },
        "build_182":{
            "enable": True,
            "time": 0,
        },
        "coin_1012":{
            "enable": False,
            "time": 0,
        },
        "exp_1012":{
            "enable": False,
            "time": 0,
        }
    }
}

class LoggerHandler(logging.Handler):
    def __init__(self, edit) -> None:
        super().__init__(logging.DEBUG)
        self.edit = edit
        self.formatter = logging.Formatter('%(asctime)s[%(lineno)d]: %(message)s', datefmt = "%H:%M:%S")
    
    def emit(self, record):
        msg = self.format(record)
        self.edit.append(msg)
        self.edit.moveCursor(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.MoveAnchor)
    
    def write(self,text):
        self.edit.append(text)
    
    def format(self, record):
        if record.levelno == logging.DEBUG:
            color = 'blue'
        elif record.levelno == logging.INFO:
            color = 'white'
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
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.form = QWidget()
        self.fileDialog = QFileDialog()
        self.config = JsonConfig("autoScriptConfig.json",DEFAULT_CONFIGS)
        self.log = logging.Logger(__name__, logging.DEBUG)
        self.adb = JCZXGame(self.adb_path, self.log, self.config)
        self.work_thread = WorkThread(self.adb, self.log, self.config)
        
    def setupUi(self):
        super().setupUi(self.form)
        self.init()
    
    def init(self):
        """初始化"""
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
        self.start_switch_work_Button.clicked.connect(self.switchWork)
        self.start_spend_order_Button.clicked.connect(self.spendOrder)
        self.stop_all_task_Button.clicked.connect(self.stopTask)
        
        self.test_button.clicked.connect(self.__debug)
    
    def __init_orderlist(self):
        self.order_build61_checkBox.setChecked(self.config.get_config(("orders","build_61","enable")))
        self.order_build61_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_61","enable"), self.order_build61_checkBox.isChecked()))
        self.order_build61_spinBox.setValue(self.config.get_config(("orders","build_61","time")))
        self.order_build61_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","build_61","time"), self.order_build61_spinBox.value()))
        
        self.order_build81_checkBox.setChecked(self.config.get_config(("orders","build_81","enable")))
        self.order_build81_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_81","enable"), self.order_build81_checkBox.isChecked()))
        self.order_build81_spinBox.setValue(self.config.get_config(("orders","build_81","time")))
        self.order_build81_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","build_81","time"), self.order_build81_spinBox.value()))
        
        self.order_build101_checkBox.setChecked(self.config.get_config(("orders","build_101","enable")))
        self.order_build101_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_101","enable"), self.order_build101_checkBox.isChecked()))
        self.order_build101_spinBox.setValue(self.config.get_config(("orders","build_101","time")))
        self.order_build101_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","build_101","time"), self.order_build101_spinBox.value()))
        
        self.order_build162_checkBox.setChecked(self.config.get_config(("orders","build_162","enable")))
        self.order_build162_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_162","enable"), self.order_build162_checkBox.isChecked()))
        self.order_build162_spinBox.setValue(self.config.get_config(("orders","build_162","time")))
        self.order_build162_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","build_162","time"), self.order_build162_spinBox.value()))
        
        self.order_build182_checkBox.setChecked(self.config.get_config(("orders","build_182","enable")))
        self.order_build182_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","build_182","enable"), self.order_build182_checkBox.isChecked()))
        self.order_build182_spinBox.setValue(self.config.get_config(("orders","build_182","time")))
        self.order_build182_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","build_182","time"), self.order_build182_spinBox.value()))
        
        self.order_coin1012w_checkBox.setChecked(self.config.get_config(("orders","coin_1012","enable")))
        self.order_coin1012w_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","coin_1012","enable"), self.order_coin1012w_checkBox.isChecked()))
        self.order_coin1012w_spinBox.setValue(self.config.get_config(("orders","coin_1012","time")))
        self.order_coin1012w_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","coin_1012","time"), self.order_coin1012w_spinBox.value()))
        
        self.order_exp1012w_checkBox.setChecked(self.config.get_config(("orders","exp_1012","enable")))
        self.order_exp1012w_checkBox.stateChanged.connect(lambda: self.config.set_config(("orders","exp_1012","enable"), self.order_exp1012w_checkBox.isChecked()))
        self.order_exp1012w_spinBox.setValue(self.config.get_config(("orders","exp_1012","time")))
        self.order_exp1012w_spinBox.valueChanged.connect(lambda: self.config.set_config(("orders","exp_1012","time"), self.order_exp1012w_spinBox.value()))
        
        #未在开发计划中，暂时隐藏
        self.order_t3HJNY_151_checkBox.setHidden(True)
        self.order_t3HJNY_151_spinBox.setHidden(True)
        self.order_t3NPJ_151_checkBox.setHidden(True)
        self.order_t3NPJ_151_spinBox.setHidden(True)
        self.order_t3YJBDT_151_checkBox.setHidden(True)
        self.order_t3YJBDT_151_spinBox.setHidden(True)
        self.order_t3YJZJ_151_checkBox.setHidden(True)
        self.order_t3YJZJ_151_spinBox.setHidden(True)
        self.order_t3YJHJ_151_checkBox.setHidden(True)
        self.order_t3YJHJ_151_spinBox.setHidden(True)
    
    def stopTask(self):
        if self.work_thread.isRunning():
            self.work_thread.stop()
            self.log.info("已停止所有任务")
    
    def switchWork(self):
        if self.work_thread.tag == self.work_thread.SWITCH and self.work_thread.isRunning():
            return
        if self.work_thread.isRunning():
            self.work_thread.stop()
            self.log.info("已停止当前任务")
        self.work_thread.setMode(WorkThread.SWITCH)
        self.work_thread.start()
    
    def spendOrder(self):
        if self.work_thread.tag == self.work_thread.ORDER and self.work_thread.isRunning():
            return
        if self.work_thread.isRunning():
            self.work_thread.stop()
        self.work_thread.setMode(WorkThread.ORDER)
        self.work_thread.start()
    
    def switchHelpTextHidden(self):
        if self.help_textBrowser.isHidden():
            self.help_textBrowser.setHidden(False)
        else:
            self.help_textBrowser.setHidden(True)
    
    def __debug(self):
        if self.work_thread.tag == self.work_thread.DEBUG and self.work_thread.isRunning():
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
    def __init__(self, path, default:dict = {}) -> None:
        self.path = path
        self.default = default
        if not exists(self.path):
            self.set_default()
            
        self._configs:dict = load(open(self.path, encoding = "utf-8"))
    
    def set_config(self,sec:str | tuple,value:Any):
        """设置配置项"""
        if isinstance(sec, str):
            self._configs[sec] = value
        else:
            option = self.get_config(sec[:-1])
            option[sec[-1]] = value
        self.save()
    
    @property
    def adb_device(self):
        return self.get_config("adb_device")
    @property
    def adb_path(self):
        return self.get_config("adb_path")
    @property
    def quarry_time(self):
        return self.get_config("quarry_time")
    @property
    def build61(self):
        return self.get_config(("orders","build_61","enable"))
    @property
    def build81(self):
        return self.get_config(("orders","build_81","enable"))
    @property
    def build101(self):
        return self.get_config(("orders","build_101","enable"))
    @property
    def build162(self):
        return self.get_config(("orders","build_162","enable"))
    @property
    def build182(self):
        return self.get_config(("orders","build_182","enable"))
    @property
    def coin1012(self):
        return self.get_config(("orders","coin_1012","enable"))
    @property
    def exp1012(self):
        return self.get_config(("orders","exp_1012","enable"))
    
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
    class Interface:
        HOME = "主界面"
        FRIEND = '好友界面'
        UNKNOWN = "未知界面"
        BUILDING_OCCUPANCY = "驻员管理"
        ROOM = "宿舍"
        BASE = "基地"
        QUARRY = "矿场"
        ORDERS = "订单库"
        ASK_NEED_SUBMIT = "询问提交订单"
    
    class Buttons:
        back_button = joinPath("resources","buttons","back.png")
        add_button = joinPath("resources","buttons","add.png")
        coinRaw_button = joinPath("resources","buttons","coinRaw.png")
        craftCoinRaw_button = joinPath("resources","buttons","craftCoinRaw.png")
        expRaw_button = joinPath("resources","buttons","expRaw.png")
        craftExpRaw_button = joinPath("resources","buttons","craftExpRaw.png")
        ticketRaw_button = joinPath("resources","buttons","ticketRaw.png")
        craftTicketRaw_button = joinPath("resources","buttons","craftTicketRaw.png")
        sure_button = joinPath("resources","buttons","sure.png")
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
        # spend_button = joinPath("resources","buttons","spend.png")
        friendOrders_button = joinPath("resources","buttons","friendOrders.png")
        tradingPost_button = joinPath("resources","buttons","tradingPost.png")
    
    class Numbers:
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
    
    class Orders:
        build61 = joinPath("resources","orders","build61.png")
        build81 = joinPath("resources","orders","build81.png")
        build101 = joinPath("resources","orders","build101.png")
        build162 = joinPath("resources","orders","build162.png")
        build182 = joinPath("resources","orders","build182.png")
        coin1012 = joinPath("resources","orders","coin1012.png")
        exp1012 = joinPath("resources","orders","exp1012.png")
        class Description:  ...
        CoinOrders = (coin1012)
        ExpOrders = (exp1012)
        BuildOrders = (build101, build162, build182, build61, build81)
        
        @staticmethod
        def amount(order:str):
            match order:
                case JCZXGame.Orders.build101: return 10
                case JCZXGame.Orders.build61: return 6
                case JCZXGame.Orders.build81: return 8
                case JCZXGame.Orders.build162: return 16
                case JCZXGame.Orders.build182: return 18
                case JCZXGame.Orders.coin1012: return 10
                case JCZXGame.Orders.exp1012: return 10
    
    def getUserOrderPaths(self) -> list[tuple[str, Orders.Description]]:
        """返回用户设置的订单路径及其介绍"""
        result = []
        if self.config.build61: result.append((self.Orders.build61, "构建6换1"))
        if self.config.build81: result.append((self.Orders.build81, "构建8换1"))
        if self.config.build101: result.append((self.Orders.build101, "构建10换1"))
        if self.config.build162: result.append((self.Orders.build162, "构建16换2"))
        if self.config.build182: result.append((self.Orders.build182, "构建18换2"))
        if self.config.coin1012: result.append((self.Orders.coin1012, "星币10换12w"))
        if self.config.exp1012: result.append((self.Orders.exp1012, "经验10换12w"))
        return result
    
    class ScreenLocs:
        friend = joinPath("resources","locations","friend.png")
        notEnough = joinPath("resources","locations","notEnough.png")
        home = joinPath("resources","buttons","friends.png")
        tradingPost = joinPath("resources","locations","tradingPost.png")
        friendTradingPost = joinPath("resources","locations","friendTradingPost.png")
        quarry = joinPath("resources","locations","quarry.png")
        base = joinPath("resources","buttons","buildingOccupancy.png")
        # orderStop = joinPath("resources","locations","orderStop.png")
        building_switch = joinPath("resources","buttons","buildingSwitch.png")
    
    def __init__(self, adb_path: str, logger:logging.Logger, config:JsonConfig) -> None:
        self.adb_path = adb_path
        self.log = logger
        self.config = config
        self.startupinfo = subprocess.STARTUPINFO()
        self.startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
        self.startupinfo.wShowWindow = subprocess.SW_HIDE
    
    @staticmethod
    def check(func):
        def wrapper(self, *args, **kwargs):
            if self.adb_path:
                return func(self, *args, **kwargs)
        return wrapper
    
    def inLocation(self, screen_loc) -> bool:
        return bool(self.findImageCenterLocations(screen_loc))
    
    def getScreenSize(self) -> tuple[int, int]:
        msg = subprocess.check_output([self.adb_path, "-s", self.device, "shell", "wm", "size"], startupinfo = self.startupinfo).decode().split(" ")[-1].replace("\r\n","")
        w, h = map(int, msg.split("x"))
        return (w, h)
    
    @check
    def screenshot(self) -> bytes:
        return subprocess.check_output([self.adb_path, "-s", self.device, "exec-out", "screencap", "-p"], startupinfo = self.startupinfo)
    
    def grayScreenshot(self):
        screenshot = cv2.imdecode(np.frombuffer(self.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        return cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    
    def click(self, x:int, y:int, wait:int = 0):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "tap", str(x), str(y)], startupinfo = self.startupinfo)
        if wait:
            sleep(wait)
    
    def clickButton(self, button_path:str, index:int = 0, wait:int = 0, log:bool = True) -> bool:
        if locations := self.findImageCenterLocations(button_path):
            self.click(*locations[index], wait)
            # self.log.info(f"点击按钮{button_path}")
            return True
        else:
            if log:
                self.log.warning(f"未找到按钮{button_path}")
            return False

    def getQuarryTime(self) -> int:
        """获取矿场结算时间"""
        self.takeOre()
        if self.config.quarry_time:
            return self.config.quarry_time
        self.log.info("未设置【矿场结算】时间正在挂机获取")
        self.switchQuarryWork()
        self.back()
        self.gotoBase()
        self.log.info("正在【挂机中】")
        while True:
            if self.inLocation(self.ScreenLocs.base):
                if self.findImageCenterLocation(self.Buttons.ore_button):
                    self.config.set_config("quarry_time",datetime.now().minute)
                    quarry_time = self.config.quarry_time
                    self.log.info(f"设置【矿场结算】时间 {quarry_time} 分")
                    self.switchQuarryWork()
                    return quarry_time
            else:
                self.gotoBase()
            sleep(60)
    
    def gotoHome(self):
        if self.inLocation(self.ScreenLocs.home):
            return
        self.__clickAndMsg(self.Buttons.home_button, "前往【主界面】", "前往【主界面】失败")
        sleep(3)
    
    def gotoFriend(self):
        if self.inLocation(self.ScreenLocs.friend):
            return
        else:
            self.gotoHome()
        if not self.__clickAndMsg(self.Buttons.friends_button, "前往【好友界面】", "前往【好友界面】失败"):
            self.gotoFriend()
        sleep(1)
    
    def gotoBase(self):
        if self.inLocation(self.ScreenLocs.base):
            return
        else:
            self.gotoHome()
        if not self.__clickAndMsg(self.Buttons.base_button, "前往【基地】", "前往【基地】失败"):
            self.gotoBase()
        sleep(3)
    
    def gotoQuarry(self):
        if self.inLocation(self.ScreenLocs.quarry):
            return
        else:
            self.gotoBase()
        if not self.__clickAndMsg(self.Buttons.quarry_button, "前往【矿场】", "前往【矿场】失败"):
            self.gotoQuarry()
        sleep(3)
    
    def gotoTradingPost(self):
        if self.inLocation(self.ScreenLocs.tradingPost):
            return
        else:
            self.gotoBase()
        if not self.__clickAndMsg(self.Buttons.tradingPost_button, "前往【原料交易所】", "前往【原料交易所】失败"):
            self.gotoTradingPost()
        sleep(1)
    
    def addAndCraft(self, num:int):
        loc = self.findImageCenterLocation(self.Buttons.add_button)
        for i in range(num - 1):
            # self.__clickAndMsg(self.Buttons.add_button, wait = 0.1)
            self.click(*loc, wait = 0.1)
        sleep(0.5)
        self.craftSure()
    
    def checkAndSpendOrders(self):
        """检查并交付订单"""
        self.__checkOrders()
        self.swipeUPScreenCenter()
        self.__checkOrders()
    
    def __checkOrders(self):
        self.log.info("正在检索【订单】")
        for img,des in self.getUserOrderPaths():
            if self.__clickAndMsg(img, wait = 0.3, log = False):
                if self.findImageCenterLocation(self.ScreenLocs.notEnough):
                    if img in self.Orders.BuildOrders:
                        ticketRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.ticketRaw_button)
                        self.makeSure(2)
                        #合成黑盒
                        self.__clickAndMsg(self.Buttons.craftTicketRaw_button, "点击【稀有黑匣】", "点击【稀有黑匣】失败", wait = 0.3)
                        self.addAndCraft(ticketRawNum)
                        self.log.info(f"合成【稀有黑匣】x{ticketRawNum}")
                    elif img in self.Orders.CoinOrders:
                        coinRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.coinRaw_button)
                        self.makeSure(2)
                        #合成星币原料
                        self.__clickAndMsg(self.Buttons.craftCoinRaw_button, "点击【星币碎片】", "点击【星币碎片】失败", wait = 0.3)
                        self.addAndCraft(coinRawNum)
                        self.log.info(f"合成【星币碎片】x{coinRawNum}")
                    elif img in self.Orders.ExpOrders:
                        expRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.expRaw_button)
                        self.makeSure(2)
                        ...#合成数据硬盘
                        self.__clickAndMsg(self.Buttons.craftExpRaw_button, "点击【数据硬盘】", "点击【数据硬盘】失败", wait = 0.3)
                        self.addAndCraft(expRawNum)
                        self.log.info(f"合成【数据硬盘】x{expRawNum}")
                    self.back(0.3)
                    self.back(0.3)
                    self.__clickAndMsg(img, wait = 0.3)
                else:
                    self.makeSure2()
                    
    
    def findRawNumbers(self, Raw_path:str) -> int | None:
        templete = cv2.imread(Raw_path, cv2.IMREAD_GRAYSCALE)
        h, w = templete.shape
        screengray = self.grayScreenshot()
        if locs := self.findImageLeftUPLocations(Raw_path):
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
        self.__clickAndMsg(self.Buttons.sure_button, wait = wait)
    
    def makeSure2(self, wait = 1):
        self.makeSure(wait)
        self.click(self.width//2, self.height//1.2, wait = 0.3)
    
    def craftSure(self):
        self.__clickAndMsg(self.Buttons.craftSure_button, wait = 1)
        self.click(self.width//2, self.height//1.2, wait = 0.5)
    
    def gotoFriendOrdersAndSpend(self):
        if self.inLocation(self.ScreenLocs.friendTradingPost):
            #check orders
            self.checkAndSpendOrders()
        if not self.inLocation(self.ScreenLocs.friend):
            self.gotoFriend()
        index = 0
        for i in range(10):
            if locations := self.findImageCenterLocations(self.Buttons.backyard_button):
                for locs in locations:
                    self.click(*locs, 0.1)
                    index += 1
                    self.__clickAndMsg(self.Buttons.friendOrders_button, f"进入【好友交易所】-{index}", f"进入【好友交易所】-{index}失败", wait=0.1)
                    #check orders
                    self.checkAndSpendOrders()
                    self.back()
                    self.click(*locs, 0.3)
                self.swipeUPScreenCenter()
            else:
                break
        self.gotoHome()
    
    def back(self, wait:int = 1):
        self.__clickAndMsg(self.Buttons.back_button, "返回上一界面", "返回上一界面失败", wait = wait)
    
    def takeOre(self):
        if self.inLocation(self.ScreenLocs.base):
            if self.__clickAndMsg(self.Buttons.ore_button, "收集矿物", log = False):
                sleep(0.7)
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
        if self.inLocation(self.ScreenLocs.building_switch):
            return
        else:
            self.gotoBase()
        if not self.__clickAndMsg(self.Buttons.building_button, "前往【驻员管理】", "前往【驻员管理】失败"):
            self.gotoBuildingOccupancy()
        sleep(1)
    
    def switchQuarryWork(self):
        if not self.inLocation(self.ScreenLocs.building_switch):
            self.gotoBuildingOccupancy()
        if self.__clickAndMsg(self.Buttons.building_switch_button, "点击【矿场预设】", "点击【矿场预设】失败",2):
            sleep(0.5)
            self.__clickAndMsg(self.Buttons.switch_button,"交换工作员工","交换工作员工失败")
    
    def __clickAndMsg(self, button_path, infoMsg:str = None, warnMsg:str = None, index:int = 0, wait:int = 0, log:bool = True):
        if self.clickButton(button_path, index, wait, log):
            if infoMsg: self.log.info(infoMsg)
            return True
        else:
            if warnMsg: self.log.warning(warnMsg)
            return False
    
    def findImageLeftUPLocations(self, button_path:str) -> list[tuple[int, int]] | None:
        screenshot_gray = self.grayScreenshot()
        template_gray = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        matcher = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(matcher > 0.9)
        w, h= template_gray.shape[0:2]
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
            result = [(x, y) for x,y in zip(tmp_x, tmp_y)]
            return result
        else:
            return None
    
    def findImageCenterLocation(self, button_path:str) -> tuple[int, int] | None:
        locations = self.findImageCenterLocations(button_path)
        if locations:
            return locations[0]
        else:
            return None

    def findImageCenterLocations(self, button_path:str) -> list[tuple[int, int]] | None:
        screenshot_gray = self.grayScreenshot()
        template_gray = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        matcher = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(matcher > 0.9)
        w, h= template_gray.shape[0:2]
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
            result = [(y+h//2,x+w//2) for x,y in zip(tmp_x,tmp_y)]
            # cv2.rectangle(screenshot_gray,(tmp_y[0],tmp_x[0]),(tmp_y[0]+h,tmp_x[0]+w),(255,0,0),3)
            # cv2.imshow("1",screenshot_gray)
            # cv2.waitKey()
            return result
        else:
            return None
    
    def swipe(self, x1:int, y1:int, x2:int, y2:int, duration:int = 200, wait:int = 0):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)], startupinfo = self.startupinfo)
        if wait:
            sleep(wait)
    
    def swipeUPScreenCenter(self):
        self.swipe(self.width//2, self.height//1.4, self.width//2, self.height//2, 200, 1.5)

    def setDevice(self, device):
        self.device = device
    
    def setADBPath(self, path):
        self.adb_path = path
    
    @property
    def width(self):
        return self.getScreenSize()[0]

    @property
    def height(self):
        return self.getScreenSize()[1]
    
    @check
    def devices(self) -> list[str]:
        return list(map(lambda x:x[:x.find("\t")], subprocess.check_output([self.adb_path, "devices"], startupinfo = self.startupinfo).decode().split("\r\n")))[1:-2]

class WorkThread(QThread):
    ORDER = 1
    SWITCH = 2
    DEBUG = 0
    
    def __init__(self, adb:JCZXGame = None, log:logging.Logger = None, config:JsonConfig = None) -> None:
        super().__init__()
        self.adb = adb
        self.log = log
        self.tag = self.DEBUG
        self.config = config
    
    def stop(self):
        self.terminate()
    
    def setMode(self, tag:int):
        self.tag = tag
    
    def run(self) -> None:
        match self.tag:
            case self.ORDER:
                self.spendOrder()
            case self.SWITCH:
                self.switchWork()
            case self.DEBUG:
                self.__debug()
            case _:
                self.log.error(f"未知tag {self.tag}")

    def __debug(self):
        self.adb.checkAndSpendOrders()
        
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
        self.adb.gotoFriend()
        self.adb.gotoFriendOrdersAndSpend()
    
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = MainManager(app)
    manager.setupUi()