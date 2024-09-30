from typing import Any
from sys import argv
from os.path import exists,join
from json import load,dumps
from time import sleep
from queue import LifoQueue
from Ui_UI import Ui_Form

from PyQt6.QtWidgets import QApplication,QWidget,QFileDialog
from PyQt6.QtGui import QIntValidator
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
        self.adb = JCZXGame(self.adb_path, self.log)
        self.work_thread = WorkThread(self.adb, self.log)
        
    def setupUi(self):
        super().setupUi(self.form)
        self.init()
    
    def init(self):
        """初始化"""
        self.__init_buttom()
        self.__init_valueRule()
        self.__init_devices()
        self.referMenuConfig()
        self.__init_logger()
        self.__start_app()
    
    @property
    def adb_device(self) -> str: return self.config.get_config("adb_device")
    @property
    def adb_path(self) -> str:  return self.config.get_config("adb_path")
    @property
    def quarry_time(self) -> int: return self.config.get_config("quarry_time")
    
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
        self.adb_devices_comboBox.currentTextChanged.connect(self.setDeviceConfig)
        self.test_button.clicked.connect(self.__debug)
    
    def __debug(self):
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
    
    class ScreenLocs:
        friend = join("resources","locations","friend.png")
        quarry = join("resources","locations","quarry.png")
        base = join("resources","buttons","buildingOccupancy.png")
        building_switch = join("resources","buttons","buildingSwitch.png")
    
    def __init__(self, adb_path: str, logger:logging.Logger) -> None:
        self.adb_path = adb_path
        self.log = logger
    
    @staticmethod
    def check(func):
        def wrapper(self, *args, **kwargs):
            if self.adb_path:
                return func(self, *args, **kwargs)
        return wrapper
    
    def inLocation(self, screen_loc) -> bool:
        return bool(self.findImageCenterLocation(screen_loc))
    
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
    
    def click(self, x:int, y:int):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "tap", str(x), str(y)])
    
    def clickButton(self, button_path:str) -> bool:
        if location := self.findImageCenterLocation(button_path):
            self.click(*location)
            # self.log.info(f"点击按钮{button_path}")
            return True
        else:
            self.log.warning(f"未找到按钮{button_path}")
            return False

    def gotoHome(self):
        if self.__clickAndMsg(self.Buttons.home_button, "前往【主界面】", "前往【主界面】失败"):
            self.loc = self.Interface.HOME
            sleep(3)
    
    def gotoFriend(self):
        if self.inLocation(self.ScreenLocs.friend): return
        else:   self.gotoHome()
        if not self.__clickAndMsg(self.Buttons.friends_button, "前往【好友界面】", "前往【好友界面】失败"):
            self.gotoFriend()
        sleep(1)
    
    def gotoBase(self):
        if self.inLocation(self.ScreenLocs.base):   return
        else:   self.gotoHome()
        if not self.__clickAndMsg(self.Buttons.base_button, "前往【基地】", "前往【基地】失败"):
            self.gotoBase()
        sleep(3)
    
    def gotoQuarry(self):
        if self.inLocation(self.ScreenLocs.quarry): return
        else:   self.gotoBase()
        if not self.__clickAndMsg(self.Buttons.quarry_button, "前往【矿场】", "前往【矿场】失败"):
            self.gotoQuarry()
        sleep(3)
    
    def takeOre(self):
        if self.inLocation(self.ScreenLocs.base):
            if self.__clickAndMsg(self.Buttons.ore_button, "收集矿物"):
                sleep(0.5)
                self.click(self.width//2, self.height//1.2)
            else:
                self.log.info("暂未发现矿物")
        else:
            self.gotoBase()
            self.takeOre()
        sleep(1)
    
    def gotoBuildingOccupancy(self):
        if self.inLocation(self.ScreenLocs.building_switch):   return
        else:   self.gotoBase()
        if not self.__clickAndMsg(self.Buttons.building_button, "前往【驻员管理】", "前往【驻员管理】失败"):
            self.gotoBuildingOccupancy()
        sleep(1)
    
    def switchWork(self):
        ...
    
    def __clickAndMsg(self, button_path, infoMsg:str = None, warnMsg:str = None):
        if self.clickButton(button_path):
            if infoMsg: self.log.info(infoMsg)
            return True
        else:
            if warnMsg: self.log.warning(warnMsg)
            return False
    
    def findImageCenterLocation(self, button_path) -> tuple[int,int] | None:
        screenshot_gray = self.grayScreenshot()
        template_gray = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        matcher = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(matcher > 0.9)
        h, w = template_gray.shape[0:2]
        xs, ys = locations
        if xs.any() and ys.any():
            return (ys[-1]+w//2, xs[-1]+h//2)
        else:
            return None
    
    def swipe(self, x1:int, y1:int, x2:int, y2:int, duration:int = 200):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])
    
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
        self.adb.gotoBuildingOccupancy()
    
    def setADB(self, adb):
        self.adb = adb
    
    def setLog(self, log):
        self.log = log
    
    def spendOrder(self):
        ...
    
    def switchWork(self):
        ...
    
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

if __name__ == "__main__":
    app = QApplication(argv)
    manager = MainManager(app)
    manager.setupUi()