from typing import Any
from sys import argv
from os.path import exists
from json import load,dumps

from Ui_UI import Ui_Form
from PyQt6.QtWidgets import QApplication,QWidget,QFileDialog

import subprocess

DEFAULT_CONFIGS = {
    "adb_path": None,
    "adb_device": None,
    "quarry_time": 30,
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

class MainManager(Ui_Form):
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.form = QWidget()
        self.fileDialog = QFileDialog()
        self.config = JsonConfig("autoScriptConfig.json",DEFAULT_CONFIGS)
        self.adb = JCZXGame(self.adb_path)
    
    def setupUi(self):
        super().setupUi(self.form)
        self.init()
    
    def init(self):
        """初始化"""
        self.__init_buttom()
        self.__init_valueRule()
        self.__init_devices()
        self.referMenuConfig()
        self.__start_app()
    
    @property
    def adb_device(self) -> int: return self.config.get_config("adb_device")
    @property
    def adb_path(self) -> str:  return self.config.get_config("adb_path")
    @property
    def quarry_time(self) -> int: return self.config.get_config("quarry_time")
    
    def __init_valueRule(self):
        # self.adb_port_lineEdit.setValidator(QIntValidator(1, 65525))
        ...
    
    def __init_buttom(self):
        """初始化按钮"""
        self.choice_adbpath_Button.clicked.connect(self.choiceADBPath)
        self.save_config_Button.clicked.connect(self.saveConfig)
    
    def __init_devices(self):
        if devices := self.adb.devices():
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
        self.adb = JCZXGame(adb_path)
        self.__init_devices()
        self.setDeviceConfig(self.adb_devices_comboBox.currentText())
    
    def setDeviceConfig(self, device:str):
        self.adb_devices_comboBox.setCurrentText(device)
        self.config.set_config("adb_device",device)
    
    def setQuarryTimeConig(self,quarry_time):
        self.config.set_config("quarry_time", int(quarry_time))
    
    def saveConfig(self):
        if adb_path := self.adb_path_lineEdit.text():
            if exists(adb_path):
                self.setADBPathConfig(adb_path)
        
        if quarry_time := self.quarry_time_lineEdit.text():
            if quarry_time.isdigit():
                self.setQuarryTimeConig(quarry_time)
        
        self.referMenuConfig()
        

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
    
class JCZXGame:
    def __init__(self, adb_path: str) -> None:
        self.adb_path = adb_path
    
    @staticmethod
    def check(func):
        def wrapper(self, *args, **kwargs):
            if self.adb_path:
                return func(self, *args, **kwargs)
        return wrapper
    
    @check
    def screenshot(self):
        ...
    
    def setDevices(self, device):
        self.device = device
    
    @check
    def devices(self):
        return list(map(lambda x:x[:x.find("\t")], subprocess.check_output([self.adb_path, "devices"]).decode().split("\r\n")))[1:-2]

if __name__ == "__main__":
    app = QApplication(argv)
    manager = MainManager(app)
    manager.setupUi()