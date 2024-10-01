from typing import Any
from sys import argv
from os.path import exists,join
from json import load,dumps
from time import sleep
from datetime import datetime
from queue import LifoQueue
from Ui_UI import Ui_Form

from PyQt6.QtWidgets import QApplication,QWidget,QFileDialog
from PyQt6.QtGui import QIntValidator,QTextCursor
from PyQt6.QtCore import QThread,QTimer

import subprocess
import logging
import cv2
import numpy as np

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
        self.work_thread = WorkThread(self.adb, self.log)
        
    def setupUi(self):
        super().setupUi(self.form)
        self.init()
    
    def init(self):
        """初始化"""
        self.__init_buttom()
        self.__init_menu()
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
        # self.test_button.setHidden(True)
    
    def __init_valueRule(self):
        self.quarry_time_lineEdit.setValidator(QIntValidator(0, 60))
    
    def __init_logger(self):
        handler = LoggerHandler(self.logger_Browser)
        self.log.addHandler(handler)
        self.log.info("程序初始化完成")
    
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
        back_button = join("resources","buttons","back.png")
        friends_button = join("resources","buttons","friends.png")
        home_button = join("resources","buttons","home.png")
        base_button = join("resources","buttons","base.png")
        quarry_button = join("resources","buttons","quarry.png")
        ore_button = join("resources","buttons","ore.png")
        building_button = join("resources","buttons","buildingOccupancy.png")
        building_switch_button = join("resources","buttons","buildingSwitch.png")
        backyard_button = join("resources","buttons","backyard.png")
        switch_button = join("resources","buttons","switch.png")
        friendOrders_button = join("resources","buttons","friendOrders.png")
        tradingPost_button = join("resources","buttons","tradingPost.png")
    
    class ScreenLocs:
        friend = join("resources","locations","friend.png")
        home = join("resources","buttons","friends.png")
        tradingPost = join("resources","locations","tradingPost.png")
        friendTradingPost = join("resources","locations","friendTradingPost.png")
        quarry = join("resources","locations","quarry.png")
        base = join("resources","buttons","buildingOccupancy.png")
        # orderStop = join("resources","locations","orderStop.png")
        building_switch = join("resources","buttons","buildingSwitch.png")
    
    def __init__(self, adb_path: str, logger:logging.Logger, config:JsonConfig) -> None:
        self.adb_path = adb_path
        self.log = logger
        self.config = config
    
    @staticmethod
    def check(func):
        def wrapper(self, *args, **kwargs):
            if self.adb_path:
                return func(self, *args, **kwargs)
        return wrapper
    
    def inLocation(self, screen_loc) -> bool:
        return bool(self.findImageCenterLocations(screen_loc))
    
    def getScreenSize(self) -> tuple[int, int]:
        msg = subprocess.check_output([self.adb_path, "-s", self.device, "shell", "wm", "size"]).decode().split(" ")[-1].replace("\r\n","")
        w, h = map(int, msg.split("x"))
        return (w, h)
    
    @check
    def screenshot(self) -> bytes:
        return subprocess.check_output([self.adb_path, "-s", self.device, "exec-out", "screencap", "-p"])
    
    def grayScreenshot(self):
        screenshot = cv2.imdecode(np.frombuffer(self.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        return cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    
    def click(self, x:int, y:int, wait:int = 0):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "tap", str(x), str(y)])
        if wait:
            sleep(wait)
    
    def clickButton(self, button_path:str, index:int = 0, wait:int = 0) -> bool:
        if locations := self.findImageCenterLocations(button_path):
            self.click(*locations[index], wait)
            # self.log.info(f"点击按钮{button_path}")
            return True
        else:
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
            if self.findImageCenterLocation(self.Buttons.ore_button):
                self.config.set_config("quarry_time",datetime.now().minute)
                quarry_time = self.config.quarry_time
                self.log.info(f"设置【矿场结算】时间 {quarry_time} 分")
                self.switchQuarryWork()
                return quarry_time
            sleep(60)
    
    def gotoHome(self):
        if self.inLocation(self.ScreenLocs.home):
            return
        if self.__clickAndMsg(self.Buttons.home_button, "前往【主界面】", "前往【主界面】失败"):
            self.loc = self.Interface.HOME
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
        if not self.__clickAndMsg(self.Buttons.tradingPost_button,"前往【原料交易所】", "前往【原料交易所】失败"):
            self.gotoTradingPost()
        sleep(1)
    
    def checkOrders(self):
        ...
    
    def gotoFriendOrdersAndSpend(self):
        if self.inLocation(self.ScreenLocs.friendTradingPost):
            ...#check orders
        if not self.inLocation(self.ScreenLocs.friend):
            self.gotoFriend()
        for i in range(15):
            if locations := self.findImageCenterLocations(self.Buttons.backyard_button):
                for locs in locations:
                    self.click(*locs, 0.1)
                    self.__clickAndMsg(self.Buttons.friendOrders_button, "进入【好友交易所】", "进入【好友交易所】失败", wait=0.3)
                    ...#check orders
                    self.back()
                    self.click(*locs, 0.3)
                self.swipeUPScreenCenter()
            else:
                break
        self.gotoHome()
    
    def back(self):
        self.__clickAndMsg(self.Buttons.back_button, "返回上一界面", "返回上一界面失败", wait = 1)
    
    def takeOre(self):
        if self.inLocation(self.ScreenLocs.base):
            if self.__clickAndMsg(self.Buttons.ore_button, "收集矿物"):
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
    
    def __clickAndMsg(self, button_path, infoMsg:str = None, warnMsg:str = None, index:int = 0, wait:int = 0):
        if self.clickButton(button_path, index, wait):
            if infoMsg: self.log.info(infoMsg)
            return True
        else:
            if warnMsg: self.log.warning(warnMsg)
            return False
    
    def findImageCenterLocation(self, button_path) -> tuple[int, int] | None:
        locations = self.findImageCenterLocations(button_path)
        if locations:
            return locations[0]
        else:
            return None

    def findImageCenterLocations(self, button_path) -> list[tuple[int, int]] | None:
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
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])
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
        return list(map(lambda x:x[:x.find("\t")], subprocess.check_output([self.adb_path, "devices"]).decode().split("\r\n")))[1:-2]

class WorkThread(QThread):
    ORDER = 1
    SWITCH = 2
    DEBUG = 0
    
    def __init__(self, adb:JCZXGame = None, log:logging.Logger = None) -> None:
        super().__init__()
        self.work_lifoqueue = LifoQueue()
        self.adb = adb
        self.log = log
        self.tag = self.DEBUG
        self.timer = QTimer()
    
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
        self.adb.swipeUPScreenCenter()
        
    def setADB(self, adb):
        self.adb = adb
    
    def setLog(self, log):
        self.log = log
    
    def spendOrder(self):
        self.log.info("开始【交付订单】任务")
        self.adb.gotoTradingPost()
        ...#check orders
        self.adb.gotoFriend()
        self.adb.gotoFriendOrdersAndSpend()
        
    def switchWork(self):
        quarry_time1 = self.adb.getQuarryTime()
        quarry_time2 = (quarry_time1+30)%60
        self.log.info("开始【矿场换班】任务")
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
    app = QApplication(argv)
    manager = MainManager(app)
    manager.setupUi()