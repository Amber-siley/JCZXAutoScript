from typing import Any,Callable,Literal
from os.path import exists,join
from os import startfile
from json import load,dumps
from time import sleep,time
from copy import copy
from datetime import datetime
from threading import Lock

from PyQt6.QtWidgets import QApplication,QWidget,QFileDialog,QHBoxLayout,QLabel,QListWidgetItem,QPushButton,QDialog
from PyQt6.QtGui import QIntValidator,QTextCursor,QFont
from PyQt6.QtCore import QThread,pyqtSignal,QSize
from cv2.typing import MatLike

from Ui_jczxUI import Ui_Form
from jczxFM import FileManage,UrlManage
from resources.icon.icon import *
from Ui_jczxQuarryCalculator import Ui_QuarryCalculator
from jczxQuarry import Quarry,floor
from jczxMainInfo import *
from Ui_jczxTaskCreater import Ui_jczxTaskCreater

import subprocess
import logging
import sys
import ctypes

import cv2
import numpy as np

def joinPath(*args):
    if hasattr(sys, '_MEIPASS'):
        return join(sys._MEIPASS, *args)
    return join(FileManage(file_path = __file__).save_path, *args)

def isadmin():
    return ctypes.windll.shell32.IsUserAnAdmin()

LOG_LEVEL = logging.INFO
# LOG_LEVEL = logging.DEBUG

class LoggerHandler(logging.Handler):
    def __init__(self, edit) -> None:
        super().__init__(LOG_LEVEL)
        self.edit = edit
        self.formatter = logging.Formatter('%(asctime)s: %(message)s', datefmt = "%H:%M:%S")
    
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
        roleRecommend = joinPath("resources","toolChart","角色养成推荐.png")
    
    Chart = _Chart()
    
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.form = QWidget()
        self.fileDialog = QFileDialog()
        self.config = JsonConfig("JCZXAutoScriptConfig.json", DEFAULT_CONFIGS)
        self.log = logging.Logger(__name__, logging.DEBUG)
        self.adb = JCZXGame(self.adb_path, self.log, self.config)
        self.work_thread = WorkThread(self.adb, self.log, self.config)
        self.quarryCalculators = []
        self.createrTaskUI = None
        
    def setupUi(self):
        super().setupUi(self.form)
        self.init()
    
    def init(self):
        """初始化"""
        self.__init_title()
        self.__init_illusionSettings()
        self.__init_favorSettings()
        self.__init_quarryCalculatorCharacters()
        self.__init_taskList()
        self.__init_button()
        self.__init_menu()
        self.__init_orderlist()
        self.__init_valueRule()
        self.__init_JJCTask()
        self.__init_logger()
        self.__init_devices()
        self.referMenuConfig()
        self.__start_app()
    
    @property
    def adb_device(self) -> str: return self.config.adb_device
    @property
    def adb_path(self) -> str:  return self.config.adb_path
    @property
    def quarry_time(self) -> int: return self.config.quarry_time
    
    def __init_title(self):
        self.form.setWindowTitle(f"交错战线AutoScript Ver-{VERSION}")
    
    def __init_menu(self):
        self.help_textBrowser.setHidden(True)
        self.logger_Browser.setFocus()
        if LOG_LEVEL != logging.DEBUG:
            self.test_button.setHidden(True)
    
    def __init_valueRule(self):
        self.quarry_time_lineEdit.setValidator(QIntValidator(-1, 60))
        self.ThresholdValue_lineEdit.setValidator(QIntValidator(1000, 50000))
    
    def __init_logger(self):
        handler = LoggerHandler(self.logger_Browser)
        fileHandler = logging.FileHandler("JCZXAutoScriptLog.log", "w", "utf-8")
        fileHandler.setFormatter(logging.Formatter('%(asctime)s [%(lineno)d] : %(message)s', datefmt = "%H:%M:%S"))
        fileHandler.setLevel(logging.DEBUG)
        self.log.addHandler(handler)
        self.log.addHandler(fileHandler)
        sys.stdout = handler
        self.log.info("程序初始化")
    
    def __init_ocr(self):
        self.createWork(self.work_thread.INIT_OCR, True)
    
    def __init_button(self):
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
        self.useIllusion2_favor_Button.clicked.connect(lambda: self.createWork(self.work_thread.ILLUSION_TO_FAVOR))
        self.startTask_Button.clicked.connect(lambda: self.createWork(self.work_thread.TASKS_LIST))
        self.start_JJCTask_Button.clicked.connect(lambda: self.createWork(self.work_thread.JJC_TASK))
        
        self.start_smallCrystal_Button.clicked.connect(lambda: self.createWork(self.work_thread.SMALL_CRYSTAL))
        self.refresh_devices_Button.clicked.connect(self.__init_devices)
        self.growthItems_Button.clicked.connect(lambda: startfile(self.Chart.GrowthItems))
        self.ItemsEX_Button.clicked.connect(lambda: startfile(self.Chart.ItemsEX))
        self.Chips_Button.clicked.connect(lambda: startfile(self.Chart.Chips))
        self.choice_Chips_Button.clicked.connect(lambda: startfile(self.Chart.ChoiceChips))
        self.role_recommend_Button.clicked.connect(lambda: startfile(self.Chart.roleRecommend))
        self.start_smallCrystal_settings_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(2))
        self.start_switch_work_settings_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(1))
        self.useIllusion2_favor_settings_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(3))
        self.quarry_calculator_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(4))
        self.tasks_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(5))
        self.start_JJCTask_settings_Button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(6))
        self.IllusionChoice_comboBox.currentIndexChanged.connect(lambda: self.config.illusion.setLevel(self.IllusionChoice_comboBox.currentIndex()))
        self.IllusionChoiceTeam_comboBox.currentIndexChanged.connect(lambda: self.config.illusion.setTeamNum(self.IllusionChoiceTeam_comboBox.currentIndex()))
        self.quarry_start_operation_Button.clicked.connect(self.startQuarryOperate)
        self.TaskCreater_Button.clicked.connect(self.showTaskCreater)
        
        self.work_thread.referADBSignal.connect(lambda x: (self.setADBPathConfig(x), self.referMenuConfig()))
        
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
    
    def __init_favorSettings(self):
        self.choiceTeam_comboBox.addItems([f"第{i}队伍" for i in range(1, 9)])
        self.choiceTeam_comboBox.setCurrentIndex(self.config.favor.teamNum - 1)
        self.choiceTeam_comboBox.currentIndexChanged.connect(lambda: self.config.favor.setTeamNum(self.choiceTeam_comboBox.currentIndex()+1))
        self.favor_illusionToFavor_spinBox.setValue(self.config.favor.time)
        self.favor_illusionToFavor_spinBox.valueChanged.connect(lambda: self.config.favor.setTime(self.favor_illusionToFavor_spinBox.value()))
    
    def __init_quarryCalculatorCharacters(self):
        dirs = Quarry.Skills.dirs()
        self.quarry_position1_comboBox.addItems(dirs)
        self.quarry_position2_comboBox.addItems(dirs)
        self.quarry_position3_comboBox.addItems(dirs)
        self.quarry_position3_comboBox.setCurrentIndex(1)
        self.quarry_position4_comboBox.addItems(dirs)
        self.quarry_position4_comboBox.setCurrentIndex(3)
        self.quarry_position5_comboBox.addItems(dirs)
        self.quarry_position5_comboBox.setCurrentIndex(3)
    
    def __init_taskList(self):
        self.choiceTask_comboBox.currentTextChanged.connect(lambda: None)
        self.choiceTask_comboBox.currentTextChanged.disconnect()
        self.choiceTask_comboBox.clear()
        self.choiceTask_comboBox.addItems(self.config.tasks.tasks.keys())
        self.choiceTask_comboBox.setCurrentText(self.config.tasks.choice)
        self.choiceTask_comboBox.currentTextChanged.connect(lambda: (self.config.tasks.setChoice(self.choiceTask_comboBox.currentText()), \
            self.taskInfor_label.clear(),\
            self.taskInfor_label.setText(str(self.config.tasks))))
        self.taskInfor_label.clear()
        self.taskInfor_label.setText(str(self.config.tasks))
    
    def __init_JJCTask(self):
        self.ThresholdValue_lineEdit.setText(str(self.config.JJCThresholdValue))
        self.ThresholdValue_lineEdit.textChanged.connect(lambda: (self.config.set_config(("JJCTask", "ThresholdValue"), int(self.ThresholdValue_lineEdit.text()) if self.ThresholdValue_lineEdit.text().isdigit() else 0)))
      
    def stopTask(self):
        if self.work_thread.isRunning():
            if self.work_thread.stop():
                self.log.info(f"已停止【{self.work_thread.mode}】")
            else:
                self.log.info(f"当前不能停止【{self.work_thread.mode}】")
        else:
            self.log.info("当前无任务运行")
        
    def createWork(self, mode, addQueue:bool = False):
        if self.work_thread.mode == mode and self.work_thread.isRunning():
            return
        if self.work_thread.isRunning() and addQueue == False:
            self.log.info(f"当前在运行【{self.work_thread.mode}】,若想切换任务请强制停止当前任务")
            return
        self.work_thread.setMode(mode, addQueue)
        self.work_thread.start()
    
    def getQuarrySkills(self) -> list[Quarry.Skills.Skill]:
        skills = Quarry.Skills.ls()
        pos1 = self.quarry_position1_comboBox.currentIndex()
        pos2 = self.quarry_position2_comboBox.currentIndex()
        pos3 = self.quarry_position3_comboBox.currentIndex()
        pos4 = self.quarry_position4_comboBox.currentIndex()
        pos5 = self.quarry_position5_comboBox.currentIndex()
        return [skills[pos1], skills[pos2], skills[pos3], skills[pos4], skills[pos5]]
    
    def startQuarryOperate(self):
        '''没写垃圾回收'''
        wt = Ui_QuarryCalculator()
        form = QWidget()
        wt.setupUi(form)
        quarry = Quarry()
        quarry.setEmplotees(*self.getQuarrySkills())
        workers = [wt.label_1, wt.label_2, wt.label_3, wt.label_4, wt.label_5]
        workTimes = [wt.label_1_1, wt.label_2_1, wt.label_3_1, wt.label_4_1, wt.label_5_1]
        for label,character,timeLabel,time in zip(workers, quarry.workers, workTimes, quarry.workeTime()):
            label.setText(character.name)
            timeLabel.setText(time)
        base, elec, smelt = quarry.details()
        base_sum, elec_sum, smelt_sum = sum(map(floor, base)), sum(map(floor, elec)), sum((map(floor, smelt)))
        score = quarry.price(base_sum, elec_sum, smelt_sum)
        start_base, start_elec, start_smelt = quarry.earnings
        base_his, elec_his, smelt_his = quarry.totalHistory()
        
        wt.score_lineEdit.setText(str(score))
        wt.money_lineEdit.setText(str(int(((base_sum-((elec_sum+smelt_sum)*3.5)))*0.7)*2.5))
        wt.base_lineEdit.setText(str(base_sum))
        wt.base_store_lineEdit.setText(f"{'{:.2f}'.format((base_sum/quarry.base_limit)*100)}% ({quarry.base_limit})")
        wt.elec_lineEdit.setText(str(elec_sum))
        wt.elec_store_lineEdit.setText(f"{'{:.2f}'.format((elec_sum/quarry.elec_limit)*100)}% ({quarry.elec_limit})")
        wt.smelt_lineEdit.setText(str(smelt_sum))
        wt.smelt_store_lineEdit.setText(f"{'{:.2f}'.format((smelt_sum/quarry.smelt_limit)*100)}% ({quarry.smelt_limit})")
        
        def listItemWidget(data: list) -> QWidget:
            widget = QWidget()
            layout = QHBoxLayout()
            for i in data:
                label = QLabel(str(i))
                ft = QFont()
                ft.setPointSize(6)
                label.setFont(ft)
                layout.addWidget(label)
            widget.setLayout(layout)
            return widget
        
        datas = [
                list(map(str, range(0, len(base)+1))),
                list(map(lambda x:"{}h{}m".format(x//60, x%60), range(0, (len(base)+1)*30, 30))),
                [start_base]+list(map(lambda x:"{:.2f}".format(x), base)),
                [start_elec]+list(map(lambda x:"{:.2f}".format(x), elec)),
                [start_smelt]+list(map(lambda x:"{:.2f}".format(x), smelt)),
                [quarry.price(*quarry.earnings)]+list(map(lambda x:"{:.2f}".format(quarry.price(*x)), zip(base, elec, smelt))),
                list(map(lambda x:"{:.2f}".format(x), base_his)),
                list(map(lambda x:"{:.2f}".format(x), elec_his)),
                list(map(lambda x:"{:.2f}".format(x), smelt_his))
        ]
        datas = np.array(datas).T
        for data in datas:
            listItem = QListWidgetItem()
            listItem.setSizeHint(QSize(398, 24))
            wt.listWidget.addItem(listItem)
            wt.listWidget.setItemWidget(listItem, listItemWidget(data))
        
        form.show()
        self.quarryCalculators.append(form)
    
    def switchHelpTextHidden(self):
        if self.help_textBrowser.isHidden():
            self.help_textBrowser.setHidden(False)
        else:
            self.help_textBrowser.setHidden(True)
    
    def showTaskCreater(self):
        self.createrTaskUI = QDialog()
        jczxTaskCreater(self.createrTaskUI, self.config, self.adb)
        self.__init_taskList()
    
    def __debug(self):
        if self.work_thread.mode == self.work_thread.DEBUG and self.work_thread.isRunning():
            return
        if self.work_thread.isRunning():
            self.work_thread.stop()
        self.work_thread.setMode(WorkThread.DEBUG)
        self.work_thread.start()
    
    def __init_devices(self):
        if not self.adb.adb_path:
            self.work_thread.setMode(WorkThread.SET_ADBTOOLS)
            self.work_thread.start()
        elif not exists(self.adb.adb_path):
            self.work_thread.setMode(WorkThread.SET_ADBTOOLS)
            self.work_thread.start()
        if devices := self.adb.devices():
            self.adb_devices_comboBox.clear()
            self.adb_devices_comboBox.addItems(devices)
        self.adb.setDNconsoleDevices()

    def __start_app(self):
        """初始化app"""
        self.form.show()
        self.__init_ocr()
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
    
    def setADBPathConfig(self, adb_path):
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
    
    class Favor:
        def __init__(self, config) -> None:
            self.__config = config
            
        @property
        def teamNum(self):  return self.__config.get_config(("favor", "teamNum"))
        @property
        def time(self): return self.__config.get_config(("favor", "time"))
        
        def setTeamNum(self, Num: int):
            self.__config.set_config(("favor", "teamNum"), Num)
        
        def setTime(self, time: int):
            self.__config.set_config(("favor", "time"), time)
        
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
    
    class Tasks:
        def __init__(self, config) -> None:
            self.__config = config
            self.tasks: dict = self.__config.get_config(("tasks", "list"))

        def __getitem__(self, name: str) -> list:
            return self.tasks[name]
        
        def setTask(self, name: str, task: list):
            self.tasks[name] = task
            self.__config.save()
        
        def removeTask(self, name: str):
            self.tasks.pop(name)
            self.__config.save()
        
        def setChoice(self, name: str):
            self.__config.set_config(("tasks", "choice"), name)
        
        def addTask(self, name:str, task:list):
            self.setTask(name, task)

        def __str__(self):
            return "\n".join(list(map(lambda x: f"{x[0]}=>{x[1]}", self.tasks[self.choice] if self.choice else [(None, None)])))
        
        def renameTask(self, name: str, newName: str):
            taskInfor = self.tasks[name]
            self.removeTask(name)
            self.addTask(newName, taskInfor)
            if name == self.choice:
                self.setChoice(newName)
        
        @property
        def choice(self) -> str:
            if not self.__config.get_config(("tasks", "choice")) or self.__config.get_config(("tasks", "choice")) not in self.tasks.keys():
                if self.tasks:
                    self.setChoice(list(self.tasks.keys())[0])
            return self.__config.get_config(("tasks", "choice"))
    
    class DNconsoleDevices:
        def __init__(self, config) -> None:
            self.__config = config
            self.Devices:dict = self.__config.get_config("DNconsoleDevices")
        
        def setDevice(self, emulator, index):
            self.Devices[emulator] = index
            self.__config.save()
    
    def __init__(self, path, default:dict = {}) -> None:
        self.path = path
        self.default = default
        if not exists(self.path):
            self.set_default()
            
        self._configs:dict = load(open(self.path, encoding = "utf-8"))
        self.illusion = self.IllusionSetting(self)
        self.favor = self.Favor(self)
        self.tasks = self.Tasks(self)
        self.dnconsoleDevices = self.DNconsoleDevices(self)
    
    def set_config(self,sec:str | tuple,value:Any):
        """设置配置项"""
        if isinstance(sec, str):
            self._configs[sec] = value
        else:
            option = self.get_config(sec[:-1])
            option[sec[-1]] = value
        self.save()
    
    @property
    def JJCThresholdValue(self):    return self.get_config(("JJCTask", "ThresholdValue"))
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
        try:
            if isinstance(sec,str):
                return self._configs[sec]
            elif isinstance(sec,tuple):
                tmp = self._configs
                for key in sec:
                    tmp = tmp[key]
                return tmp
        except KeyError:
            if isinstance(sec,str):
                self._configs[sec] = DEFAULT_CONFIGS[sec]
                data = self._configs[sec]
            elif isinstance(sec,tuple):
                self._configs[sec[0]] = DEFAULT_CONFIGS[sec[0]]
                data = self._configs
                for key in sec:
                    data = data[key]
            self.save()
            return data
    
    def set_default(self):
        with open(self.path,"w",encoding="utf-8") as fp:
            fp.write(dumps(self.default, indent = 4, ensure_ascii = False))

class TaskListItem(QWidget):
    delSignal = pyqtSignal(int) # 删除编号为int的任务
    moveItemSignal = pyqtSignal(int, int) # 将编号为int的任务移动, -1向下, 1向上
    
    def __init__(self, emulator:str, taskName:str, num:int):
        super().__init__()
        self.emulator = emulator
        self.taskName = taskName
        self.num = num
        #显示内容
        title = f"{emulator}=>{taskName}"
        self.titleLabel = QLabel(title)
        self.upButton = QPushButton("↑")
        self.upButton.setMinimumWidth(20)
        self.downButton = QPushButton("↓")
        self.downButton.setMinimumWidth(20)
        self.deleteButton = QPushButton("×")
        self.deleteButton.setMinimumWidth(20)
        
        #布局
        layout = QHBoxLayout()
        layout.addWidget(self.titleLabel)
        layout.addStretch() # 自动调整空白区
        layout.addWidget(self.upButton)
        layout.addWidget(self.downButton)
        layout.addWidget(self.deleteButton)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # signal
        self.initSignal()
    
    def initSignal(self):
        self.upButton.clicked.connect(lambda: self.moveItemSignal.emit(self.num, 1))
        self.downButton.clicked.connect(lambda: self.moveItemSignal.emit(self.num, -1))
        self.deleteButton.clicked.connect(lambda: self.delSignal.emit(self.num))
    
class jczxTaskCreater(Ui_jczxTaskCreater):
    def __init__(self, Twidget:QDialog, config:JsonConfig, adb): # type: ignore
        super().__init__()
        self.config = config
        self.adb = adb
        self.taskList = []
        self.Twidget = Twidget
        self.setupUi(Twidget)
        self.emulator_comboBox.addItems(list(set(list(self.config.dnconsoleDevices.Devices.keys()) + self.adb.devices())))
        self.initTaskCreater()
        self.initButton()
        self.Twidget.exec()
    
    def initButton(self):
        self.renameTask_Button.clicked.connect(self.renameTask)
        self.newNameTask_Button.clicked.connect(self.newNameTask)
        self.delTask_Button.clicked.connect(self.delTask)
        self.newTaskItem_Button.clicked.connect(lambda: self.addTaskListItem(self.emulator_comboBox.currentText(), self.newTaskItem_comboBox.currentText()) if self.emulator_comboBox.currentText() and self.newTaskItem_comboBox.currentText() else ...)
        self.saveTaskList_Button.clicked.connect(self.save)
        self.saveAndQuit_Button.clicked.connect(lambda: (self.save(), self.Twidget.close()))
        
    def initTaskCreater(self):
        # init comboBox
        self.TaskList_comboBox.clear()
        self.newTaskItem_comboBox.clear()
        self.TaskList_comboBox.addItems(self.config.tasks.tasks.keys())
        self.TaskList_comboBox.currentTextChanged.connect(self.initViewTaskList)
        self.newTaskItem_comboBox.addItems(CreaterWorkTags.ls())
        if self.adb.DNConsole.CAN_RUN:
            self.newTaskItem_comboBox.addItem(WorkTags.QUIT_DEVICE)
        
        # init viewTaskList
        self.initViewTaskList()
    
    def initViewTaskList(self):
        title = self.TaskList_comboBox.currentText()
        self.taskList = []
        if title:
            self.nowViewTaskList_lineEdit.setText(title)
            self.listWidget.clear()
            self.addTaskListItems(self.config.tasks.tasks[title])
    
    def renameTask(self):
        if new_name := self.renameTask_lineEdit.text():
            choice = self.TaskList_comboBox.currentText()
            self.config.tasks.renameTask(choice, new_name)
            self.initTaskCreater()
            self.TaskList_comboBox.setCurrentText(new_name)
            self.initViewTaskList()
        else:
            ...
        self.renameTask_lineEdit.clear()
    
    def newNameTask(self):
        newName = self.newNameTask_lineEdit.text()
        if newName and newName not in self.config.tasks.tasks.keys():
            self.config.tasks.addTask(newName, [])
            self.newNameTask_lineEdit.clear()
            self.initTaskCreater()
            self.TaskList_comboBox.setCurrentText(newName)
    
    def delTask(self):
        self.config.tasks.removeTask(self.TaskList_comboBox.currentText())
        self.initTaskCreater()
    
    def moveTaskItem(self, num:int, face:int):
        # 数据
        item = self.taskList[num]
        l = len(self.taskList)
        self.taskList.pop(num)
        match face:
            case 1:
                self.taskList.insert(num - 1 if num > 0 else l - 1, item)
            case -1:
                self.taskList.insert(num + 1 if num < l - 1 else 0, item)
        
        # ui
        self.referViewTaskList()

    def referViewTaskList(self):
        self.listWidget.clear()
        newlist = copy(self.taskList)
        self.taskList = []
        self.addTaskListItems(newlist)
    
    def delTaskItem(self, num:int):
        self.taskList.pop(num)
        self.referViewTaskList()
    
    def save(self):
        self.config.tasks.setTask(self.nowViewTaskList_lineEdit.text(), self.taskList)
    
    def addTaskListItem(self, emulator:str, task:str):
        listItem = QListWidgetItem()
        listItem.setSizeHint(QSize(230, 24))
        num = len(self.taskList)
        self.listWidget.addItem(listItem)
        widget = TaskListItem(emulator, task, num)
        widget.moveItemSignal.connect(self.moveTaskItem)
        widget.delSignal.connect(self.delTaskItem)
        self.listWidget.setItemWidget(listItem, widget)
        self.taskList.append((emulator, task))
    
    def addTaskListItems(self, taskList:list[tuple[str, str]]):
        for emulator,task in taskList:
            self.addTaskListItem(emulator, task)
    
class JCZXGame:
    class _ScreenCut:
        class Point: ...
        def __init__(self, w, h) -> None:
            self.w = max(w, h)
            self.h = min(w, h)
        
        def cut(self, cx, cy, x, y) ->tuple[Point, Point]:
            w = self.w//cx
            h = self.h//cy
            return ((w*x, h*y), (w*(x+1), h*(y+1)))

        def cut1x2(self, x, y): return self.cut(1, 2, x, y)
        def cut1x3(self, x, y): return self.cut(1, 3, x, y)
        def cut1x4(self, x, y): return self.cut(1, 4, x, y)
        def cut1x5(self, x, y): return self.cut(1, 5, x, y)
        def cut2x1(self, x, y): return self.cut(2, 1, x, y)
        def cut2x2(self, x, y): return self.cut(2, 2, x, y)
        def cut2x3(self, x, y): return self.cut(2, 3, x, y)
        def cut2x4(self, x, y): return self.cut(2, 4, x, y)
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
        login_button = joinPath("resources","buttons","login.png")
        choiceTeam_button = joinPath("resources","buttons","choiceTeam.png")
        signIn_button = joinPath("resources","buttons","sign-in.png")
        userLogin_button = joinPath("resources","buttons","userLogin.png")
        choiceFriendTP_button = joinPath("resources","locations","whateverTradingPost.png")
        rightSwitchTradingPost_buttion = joinPath("resources","buttons","rightSwitchTradingPost.png")
        leftSwitchTradingPost_buttion = joinPath("resources","buttons","leftSwitchTradingPost.png")
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
        simulatedMilitaryExercises_button = joinPath("resources","buttons","simulatedMilitaryExercises.png")
        competition_button = joinPath("resources","buttons","competition.png")
        challenge_button = joinPath("resources","buttons","challenge.png")
        fightLossBack_button = joinPath("resources","buttons","fightLossBack.png")
        competitionCancel_button = joinPath("resources","buttons","competitionCancel.png")
        closeNotice_button = joinPath("resources","buttons","closeNotice.png")
        noReminders_button = joinPath("resources","buttons","noReminders.png")
        noRemindersBase_button = joinPath("resources","buttons","noRemindersBase.png")
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
        menu_button = joinPath("resources","buttons","menu.png")
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
        team1 = joinPath("resources","numbers","team1.png")
        team2 = joinPath("resources","numbers","team2.png")
        team3 = joinPath("resources","numbers","team3.png")
        team4 = joinPath("resources","numbers","team4.png")
        team5 = joinPath("resources","numbers","team5.png")
        team6 = joinPath("resources","numbers","team6.png")
        team7 = joinPath("resources","numbers","team7.png")
        team8 = joinPath("resources","numbers","team8.png")
        JJC0 = joinPath("resources","numbers","JJC0.png")
        JJC1 = joinPath("resources","numbers","JJC1.png")
        JJC2 = joinPath("resources","numbers","JJC2.png")
        JJC3 = joinPath("resources","numbers","JJC3.png")
        JJC4 = joinPath("resources","numbers","JJC4.png")
        JJC5 = joinPath("resources","numbers","JJC5.png")
        JJC6 = joinPath("resources","numbers","JJC6.png")
        JJC7 = joinPath("resources","numbers","JJC7.png")
        JJC8 = joinPath("resources","numbers","JJC8.png")
        JJC9 = joinPath("resources","numbers","JJC9.png")
        JJC10 = joinPath("resources","numbers","JJC10.png")
        cancel0 = joinPath("resources","numbers","cancel0.png")
        cancel1 = joinPath("resources","numbers","cancel1.png")
        cancel2 = joinPath("resources","numbers","cancel2.png")
        cancel3 = joinPath("resources","numbers","cancel3.png")
        cancel4 = joinPath("resources","numbers","cancel4.png")
        cancel5 = joinPath("resources","numbers","cancel5.png")
        cancel6 = joinPath("resources","numbers","cancel6.png")
        cancel7 = joinPath("resources","numbers","cancel7.png")
        cancel8 = joinPath("resources","numbers","cancel8.png")
        cancel9 = joinPath("resources","numbers","cancel9.png")
        cancel10 = joinPath("resources","numbers","cancel10.png")
        cancel11 = joinPath("resources","numbers","cancel11.png")
        cancel12 = joinPath("resources","numbers","cancel12.png")
        cancel13 = joinPath("resources","numbers","cancel13.png")
        cancel14 = joinPath("resources","numbers","cancel14.png")
        cancel15 = joinPath("resources","numbers","cancel15.png")
        score26 = joinPath("resources","numbers","score26.png")
        score28 = joinPath("resources","numbers","score28.png")
    
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
    
    class MatchTempleteDetailInfo:
        # 这里的类型标识并不规范。。。。
        def __init__(
                self,\
                baseGrayScreenshot: MatLike,\
                grayScreenshot: MatLike,\
                templeteSize:tuple[int, int],\
                matchTempletePoints:list[tuple[int, ...]],\
                matchTempleteCenterPoints:list[tuple[int, int]]
            ):
            self.baseGrayScreenshot = baseGrayScreenshot
            self.grayScreenshot = grayScreenshot
            self.templeteSize = templeteSize
            self.templeteWidth = templeteSize[0]
            self.templeteHeight = templeteSize[1]
            self.matchTempletePoints = matchTempletePoints
            self.matchTempletePointRanges = list(map(lambda point : (point[0], point[-1]), matchTempletePoints)) if matchTempletePoints else None
            self.matchTempletePointRange = self.matchTempletePointRanges[0] if self.matchTempletePointRanges else None
            self.matchTempletePoint = matchTempletePoints[0] if matchTempletePoints else None
            self.matchTempleteCenterPoints = matchTempleteCenterPoints
            self.matchTempleteCenterPoint = matchTempleteCenterPoints[0] if matchTempleteCenterPoints else None

        def _transformMatchTempletePointBase(self, matchTempletePoint:tuple[int, ...] | None = None, upMove:int = 0, downMove:int = 0, leftMove:int = 0, rightMove:int = 0) -> tuple[int, ...]:
            if not matchTempletePoint:
                matchTempletePoint = copy(self.matchTempletePoint)
            upMove = upMove - downMove
            rightMove = rightMove - leftMove
            return tuple(map(lambda point : (point[0] + rightMove, point[1] - upMove), matchTempletePoint))
        
        def transMoveFromTemleteSize(self, matchTempletePoint:tuple[int, ...] | None = None, upMoveTimes:int = 0, downMoveTimes:int = 0, leftMoveTImes:int = 0, rightMoveTimes:int = 0):
            if not matchTempletePoint:
                matchTempletePoint = copy(self.matchTempletePoint)
                height = self.templeteHeight
                width = self.templeteWidth
            else:
                height = matchTempletePoint[2][1] - matchTempletePoint[0][1]
                width = matchTempletePoint[1][0] - matchTempletePoint[0][0]
            return self._transformMatchTempletePointBase(matchTempletePoint, upMove = height*(upMoveTimes - downMoveTimes), rightMove = width*(rightMoveTimes - leftMoveTImes))
        
        def transMatchTempletePointFromSize(self, matchTempletePoint = None, upAddWidthTimes:int = 0, downWidthTimes:int = 0, leftHeightTimes:int = 0, rightHeightTimes:int = 0):
            if not matchTempletePoint:
                matchTempletePoint = copy(self.matchTempletePoint)
                height = self.templeteHeight
                width = self.templeteWidth
            else:
                height = matchTempletePoint[2][1] - matchTempletePoint[0][1]
                width = matchTempletePoint[1][0] - matchTempletePoint[0][0]
            upAddWidth = upAddWidthTimes*width
            downWidth = downWidthTimes*width
            leftHeight = leftHeightTimes*height
            rightHeight = rightHeightTimes*height
            return self._transMatchTempletePoint(matchTempletePoint, upAddWidth, downWidth, leftHeight, rightHeight)
        
        def _transMatchTempletePoint(self, matchTempletePoint:tuple[int, ...] | None = None, upAdd:int = 0, downAdd:int = 0, leftAdd:int = 0, rightAdd:int = 0) -> tuple[int, ...]:
            if not matchTempletePoint:
                matchTempletePoint = copy(self.matchTempletePoint)
            m = matchTempletePoint
            p1 = m[0]
            p2 = m[1]
            p3 = m[2]
            p4 = m[3]
            p1 = (p1[0] - leftAdd, p1[1] - upAdd)
            p2 = (p2[0] + rightAdd, p2[1] - upAdd)
            p3 = (p3[0] - leftAdd, p3[1] + downAdd)
            p4 = (p4[0] + rightAdd, p4[1] + downAdd)
            return (p1, p2, p3, p4)
        
        def transRange(self, points:tuple[int, ...]) -> tuple[tuple[int, int]]:
            return (points[0], points[-1])
        
        def transCenterPoint(self, points:tuple[int, ...]) -> tuple[int, int]:
            p1, p2 = self.transRange(points)
            return ((p1[0]+p2[0])//2, (p1[1]+p2[1])//2)
    
    class DNConsoleExe:
        def __init__(self, dnconsolePath:str):
            self.dnconsolePath = dnconsolePath
            self.startupinfo = subprocess.STARTUPINFO()
            self.startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
            self.startupinfo.wShowWindow = subprocess.SW_HIDE
            self.CAN_RUN = isadmin() & self.isexists()
        
        @staticmethod
        def check(func):
            def _(self, *args, **kwargs):
                if self.CAN_RUN:
                    return func(self, *args, **kwargs)
            return _
        
        def isexists(self) -> bool:
            return exists(self.dnconsolePath)
        
        @check
        def isrunning(self, index) -> bool:
            match subprocess.check_output([self.dnconsolePath, "isrunning", "--index", index], shell = True, startupinfo = self.startupinfo).decode("gbk"):
                case 'running':
                    return True
                case "stop":
                    return False
        
        @check
        def getEmulatorName(self, index) -> str | None:
            emulator = subprocess.check_output([self.dnconsolePath, "adb", "--index", index, "--command", "get-serialno"], shell = True, startupinfo = self.startupinfo).decode("gbk")[:-3]
            if emulator.endswith("not found") or emulator.startswith("error"):
                return None
            else:
                return emulator
        
        @check
        def getEmulatorIndexs(self) -> list:
            dataText = subprocess.check_output([self.dnconsolePath, "list2"], shell = True, startupinfo = self.startupinfo).decode("gbk")
            data = dataText.split("\r\n")
            if data:
                emulatorIndexs = [i.split(',')[0] for i in dataText.split("\r\n")[:-1]]
                return emulatorIndexs
            else:
                return []
        
        @check
        def launchDevice(self, index):
            if not self.isrunning(index):
                subprocess.run([self.dnconsolePath, "launch", "--index", index], shell = True, startupinfo = self.startupinfo)
        
        @check
        def quitDevice(self, index):
            if self.isrunning(index):
                subprocess.run([self.dnconsolePath, "quit", "--index", index], shell = True, startupinfo = self.startupinfo)
    
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
        menu = joinPath("resources","buttons", "friends.png")
        levels = joinPath("resources","locations","levels.png")
        visiting = joinPath("resources","locations","visiting.png")
        choiceFriendTP = joinPath("resources","locations","choiceFriendTP.png")
        enoughSmallCrytal = joinPath("resources","locations","enoughSmallCrytal.png")
        fightWin = joinPath("resources","locations","fightWin.png")
        fightLoss1 = joinPath("resources","locations","fightLoss1.png")
        fightLoss2 = joinPath("resources","locations","fightLoss2.png")
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
        competition = joinPath("resources","buttons","competitionCancel.png")
        firstScoreLoc = joinPath("resources","locations","firstScoreLoc.png")
        newRanking = joinPath("resources","locations","newRanking.png")
        JJC10Loc = joinPath("resources","locations","JJC10Loc.png")
        cancel15Loc = joinPath("resources","locations","cancel15Loc.png")
        sureEnter = joinPath("resources","buttons","sureEnter.png")
        illusions = joinPath("resources","locations","illusions.png")
        activities = joinPath("resources","locations","activities.png")
        notEnoughAsk = joinPath("resources","locations","notEnoughAsk.png")
        tabBar = joinPath("resources","locations","tabBar.png")
        getItem= joinPath("resources","buttons","getItem.png")
        home = joinPath("resources","buttons","base.png")
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
        menuPos = None
        basePos = None
        tradingPos = None
        buildingOccupancyPos = None
    
    def __init__(self, adb_path: str, logger:logging.Logger, config:JsonConfig) -> None:
        self.adb_path = adb_path
        self.device = None
        self.log = logger
        self.config = config
        self.ocr:PaddleOCR = None # type: ignore
        self.startupinfo = subprocess.STARTUPINFO()
        self.startupinfo.dwFlags = subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
        self.startupinfo.wShowWindow = subprocess.SW_HIDE
        self.DNConsole = None
        self.submitOrders = []
        self.size = None
    
    def dowloadADBTools(self) -> str:
        self.log.info("未指定adb路径，已添加下载任务")
        FileManage(file_path = UrlManage.dowload(ADB_TOOLS_URL)).unzip(retain = False)
        adb_path = join("platform-tools", "adb.exe")
        self.log.info("解压完成")
        return adb_path
    
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
    def inlocationCompetition(self): return self.inLocation(self.ScreenLocs.competition, self.ScreenCut.cut2x2(1, 0))
    @property
    def inlocationSimulatedMilitaryExercises(self): return self.inLocation(self.Buttons.competition_button, self.ScreenCut.cut2x1(0, 0))
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
    def inLocationFightLoss(self): return self.inLocation(self.ScreenLocs.fightLoss1, self.ScreenCut.cut2x2(0, 0))
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
    
    def inLocation(self, screen_loc, cutPoints:tuple[tuple[int, int]] = None, per = 0.9, grayScreenshot = None) -> bool:
        answer = bool(self.findImageCenterLocations(screen_loc, cutPoints, per, grayScreenshot))
        self.log.debug(f"检测界面 {screen_loc} {answer}")
        return answer
    
    def getScreenSize(self) -> tuple[int, int]:
        if self.size:
            return self.size
        else:
            msg = subprocess.check_output([self.adb_path, "-s", self.device, "shell", "wm", "size"], startupinfo = self.startupinfo).decode().split(" ")[-1].replace("\r\n","")
            w, h = map(int, msg.split("x"))
            self.size = (max(w, h), min(w, h))
        return self.size
    
    @check
    def screenshot(self) -> bytes:
        startTime = time()
        data = subprocess.check_output([self.adb_path, "-s", self.device, "exec-out", "screencap", "-p"], startupinfo = self.startupinfo)
        # self.log.debug(f"data size {len(data)}, {img.shape}")
        runningTime = (time() - startTime)
        self.log.debug("截图耗时 {:.2f} s".format(runningTime))
        return data
    
    def grayScreenshot(self, cutPoints = None):
        screenshot = cv2.imdecode(np.frombuffer(self.screenshot(), np.uint8), cv2.IMREAD_GRAYSCALE)
        # self.log.debug(f"截图 size {screenshot.shape}")
        # self.log.debug(f"截取范围 {cutPoints}")
        return self.cutScreenshot(screenshot, cutPoints)

    def cutScreenshot(self, screenshot, cutPoints = None):
        if cutPoints:
            (x0, y0), (x1, y1) = cutPoints
            return screenshot[y0:y1, x0:x1]
        else:
            return screenshot
    
    def click(self, x:int, y:int, wait:int = 0):
        cmd = [self.adb_path, "-s", self.device, "shell", "input", "tap", str(x), str(y)]
        subprocess.run(cmd, startupinfo = self.startupinfo)
        self.log.debug(f"执行点击 {' '.join(cmd)}")
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
                    
    def clickButton(self, button_path:str, index:int = 0, wait:int = 0, log:bool = True, cutPoints = None, per = 0.9, grayScreenshot = None) -> tuple[int, int] | None:
        if locations := self.findImageCenterLocations(button_path, cutPoints, per, grayScreenshot):
            self.click(*locations[index], wait)
            self.log.debug(f"点击按钮{button_path} {locations[index]}")
            return locations[index]
        else:
            if log:
                self.log.warning(f"未找到按钮{button_path}")
            return None

    def clickFightButton(self):
        return self._clickAndMsg(self.Buttons.fight_button, "前往【关卡界面】", "前往【关卡界面】失败", wait = 1, cutPoints = self.ScreenCut.cut4x3(3, 2), per = 0.8)

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

    def waitClickStartFight(self):
        if loc := self._waitClickAndMsg(self.Buttons.startFight_button, infoMsg = "准备战斗", wait = 1, cutPoints = self.ScreenCut.cut3x4(2, 3)):
            if self.needSureEnterFight: self.makeSureEnter(2)
        return loc
    
    def clickHelpFight(self, index:int = None):
        return self._clickAndMsg(self.Buttons.helpFight_button, index = index, wait = 0.5, cutPoints = self.ScreenCut.cut2x1(1, 0))
    
    def clickCloseUseThisTeam(self, index: Literal[0, 1] = None):
        return self._clickAndMsg(self.Buttons.useTeam_button, index = index, wait = 0.1, cutPoints = self.ScreenCut.cut4x1(3, 0))
    
    def choiceFightTeam(self, index: Literal[0, 1] = None, teamNum: Literal[1, 2, 3, 4, 5, 6, 7, 8] = 3):
        def _(Num):
            match Num:
                case 1:
                    self._clickAndMsg(self.Numbers.team1, wait = 0.3)
                case 2:
                    self._clickAndMsg(self.Numbers.team2, wait = 0.3)
                case 3:
                    self._clickAndMsg(self.Numbers.team3, wait = 0.3)
                case 4:
                    self._clickAndMsg(self.Numbers.team4, wait = 0.3)
                case 5:
                    self._clickAndMsg(self.Numbers.team5, wait = 0.3)
                case 6:
                    self._clickAndMsg(self.Numbers.team6, wait = 0.3)
                case 7:
                    self._clickAndMsg(self.Numbers.team7, wait = 0.3)
                case 8:
                    self._clickAndMsg(self.Numbers.team8, wait = 0.3)
                    
        loc = self._clickAndMsg(self.Buttons.choiceTeam_button, index = index, wait = 0.3, cutPoints = self.ScreenCut.cut4x1(1, 0))
        if teamNum > 5:
            self.swipe(loc[0], loc[1]+100, *loc, wait = 0.3)
        _(teamNum)
    
    def clickStartToAct(self, wait = 0, log = True):
        if log:
            return self._waitClickAndMsg(self.Buttons.startToAct_button, self.inLocationWhateverIllusionLevelsFget, "开始战斗", "开始战斗异常", wait = wait, cutPoints = self.ScreenCut.cut3x4(2, 3))
        else:
            return self._waitClickAndMsg(self.Buttons.startToAct_button, self.inLocationWhateverIllusionLevelsFget, wait = wait, cutPoints = self.ScreenCut.cut3x4(2, 3))
    
    def clickSkipAnimation(self, log = False):
        return self._clickAndMsg(self.Buttons.skipAnimation_button, deepLog = log, cutPoints = self.ScreenCut.cut4x3(3, 0), per = 0.8)
    
    def clickReadyTeamPlane(self, wait = 0.7):
        return self._clickAndMsg(self.Buttons.plane_button, wait = wait, deepLog = False, cutPoints = self.ScreenCut.cut3x7(1, 6))
    
    def clickGetItems(self, wait = 0.3, log = False):
        return self._clickAndMsg(self.ScreenLocs.getItem, wait = wait, deepLog = log, cutPoints = self.ScreenCut.cut3x2(1, 0), per = 0.8)
    
    def getQuarryTime(self) -> int:
        """获取矿场结算时间"""
        self.takeOre()
        if self.config.quarry_time != -1:
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
    
    def getCompetitionAndCancelTimes(self, grayScreenshot:MatLike = None) -> tuple[int, int]:
        if grayScreenshot is None:
            grayScreenshot = self.grayScreenshot()
        return (self.getCompetitionTimes(grayScreenshot), self.getCompetitionCancelTimes(grayScreenshot))
        
    def getCompetitionTimes(self, grayScreenshot:MatLike = None) -> int:
        cutPoints = self.ScreenCut.cut2x3(1, 0)
        if grayScreenshot is None:
            grayScreenshot = self.grayScreenshot()
        if self.findImageCenterLocation(self.Numbers.JJC10, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 10
        if self.findImageCenterLocation(self.Numbers.JJC9, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 9
        if self.findImageCenterLocation(self.Numbers.JJC8, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 8
        if self.findImageCenterLocation(self.Numbers.JJC7, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 7
        if self.findImageCenterLocation(self.Numbers.JJC6, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 6
        if self.findImageCenterLocation(self.Numbers.JJC5, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 5
        if self.findImageCenterLocation(self.Numbers.JJC4, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 4
        if self.findImageCenterLocation(self.Numbers.JJC3, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 3
        if self.findImageCenterLocation(self.Numbers.JJC2, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 2
        if self.findImageCenterLocation(self.Numbers.JJC1, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 1
        if self.findImageCenterLocation(self.Numbers.JJC0, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 0
    
    def getCompetitionCancelTimes(self, grayScreenshot:MatLike = None) -> int:
        cutPoints = self.ScreenCut.cut2x3(1, 0)
        if grayScreenshot is None:
            grayScreenshot = self.grayScreenshot()
        if self.findImageCenterLocation(self.Numbers.cancel15, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 15
        if self.findImageCenterLocation(self.Numbers.cancel14, cutPoints = cutPoints, per = 0.9, grayScreenshot = grayScreenshot): return 14
        if self.findImageCenterLocation(self.Numbers.cancel13, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 13
        if self.findImageCenterLocation(self.Numbers.cancel12, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 12
        if self.findImageCenterLocation(self.Numbers.cancel11, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 11
        if self.findImageCenterLocation(self.Numbers.cancel10, cutPoints = cutPoints, per = 0.85, grayScreenshot = grayScreenshot): return 10
        if self.findImageCenterLocation(self.Numbers.cancel9, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 9
        if self.findImageCenterLocation(self.Numbers.cancel8, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 8
        if self.findImageCenterLocation(self.Numbers.cancel7, cutPoints = cutPoints, per = 0.9, grayScreenshot = grayScreenshot): return 7
        if self.findImageCenterLocation(self.Numbers.cancel6, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 6
        if self.findImageCenterLocation(self.Numbers.cancel5, cutPoints = cutPoints, per = 0.9, grayScreenshot = grayScreenshot): return 5
        if self.findImageCenterLocation(self.Numbers.cancel4, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 4
        if self.findImageCenterLocation(self.Numbers.cancel3, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 3
        if self.findImageCenterLocation(self.Numbers.cancel2, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 2
        if self.findImageCenterLocation(self.Numbers.cancel1, cutPoints = cutPoints, per = 0.97, grayScreenshot = grayScreenshot): return 1
        if self.findImageCenterLocation(self.Numbers.cancel0, cutPoints = cutPoints, per = 0.95, grayScreenshot = grayScreenshot): return 0
    
    def challengeCompetition(self):
        thresholdValue = self.config.JJCThresholdValue
        clickCancelTimes, clicked = 0, True
        maxClickCancelTImes = 4
        allTimes, allCancels = self.getCompetitionAndCancelTimes()
        competitionHistory = {"+28": 0, "+26": 0, "loss": 0}
        for _ in range(allCancels*allTimes):
            # 简单的逻辑：
            # 刷新次数//挑战次数 = 最小当前可刷新次数(最大值为4)
            # 最小当前可刷新次数用于寻找符合阈值的+28挑战
            # 若刷新次数用完也没有找到符合阈值的挑战对象则 =》 挑战当前符合阈值的对象（无论+26 or +28）
            # 结束条件： 模拟次数或者挑战次数用完
            info = self.findImageDetailLocations(self.ScreenLocs.firstScoreLoc, cutPoints = self.ScreenCut.cut3x1(0, 0))
            times, cancels = self.getCompetitionAndCancelTimes(info.baseGrayScreenshot)
            self.log.info(f"挑战次数{times},刷新次数{cancels}")
            if clicked: #如果已经挑战后更新点击次数
                clickCancelTimes = cancels//times if times != 0 else 0
                clickCancelTimes = maxClickCancelTImes if clickCancelTimes > maxClickCancelTImes else clickCancelTimes
                clicked = False
            loc = info.transRange(info.transMatchTempletePointFromSize(info.transMoveFromTemleteSize(rightMoveTimes = 1), rightHeightTimes = 1))
            number = int(self.ocr.readtext(self.cutScreenshot(info.baseGrayScreenshot, loc))[0])
            if number <= thresholdValue and self.inLocation(self.Numbers.score28, cutPoints = self.ScreenCut.cut2x2(0, 0), per = 0.95, grayScreenshot = info.baseGrayScreenshot) and times != 0:
                # 条件1： 符合阈值的+28挑战
                self.log.info("已找到+28挑战")
                self.click(*info.transCenterPoint(loc))
                clicked = True
                self.clickChallengeCompetition()
                if self.autoPlayLevels():
                    competitionHistory["+28"] += 1
                else:
                    competitionHistory["loss"] += 1
                # self._clickAndMsg(self.ScreenLocs.newRanking, wait = 0.3, deepLog = False, cutPoints = self.ScreenCut.cut3x2(1, 0), per = 0.8)
                # self.clickGetItems()
                self.click(self.width//2, self.height//5, wait = 0.6)
                self.click(self.width//2, self.height//5, wait = 0.6)
                self.click(self.width//2, self.height//5, wait = 0.6)
            elif number <= thresholdValue and clickCancelTimes <= 0 and times != 0:
                # 条件2： 符合阈值，但已超出最小当前可刷新次数
                self.log.info("已找到+26挑战")
                self.click(*info.transCenterPoint(loc))
                clicked = True
                self.clickChallengeCompetition()
                if self.autoPlayLevels():
                    competitionHistory["+26"] += 1
                else:
                    competitionHistory["loss"] += 1
                # self._clickAndMsg(self.ScreenLocs.newRanking, wait = 0.3, deepLog = False, cutPoints = self.ScreenCut.cut3x2(1, 0), per = 0.8)
                # self.clickGetItems()
                self.click(self.width//2, self.height//5, wait = 0.6)
                self.click(self.width//2, self.height//5, wait = 0.6)
                self.click(self.width//2, self.height//5, wait = 0.6)
            else:
                if cancels == 0 or times == 0: #刷新次数为0 或战斗次数为0 时结束
                    break
                self._clickAndMsg(self.Buttons.competitionCancel_button, "点击刷新", wait = 1, cutPoints = self.ScreenCut.cut2x3(1, 0), grayScreenshot = info.baseGrayScreenshot)
                clickCancelTimes -= 1
        self.log.info(f"+28 X {competitionHistory['+28']}")
        self.log.info(f"+26 X {competitionHistory['+26']}")
        self.log.info(f"挑战失败 X {competitionHistory['loss']}")
        if competitionHistory["loss"]: self.log.info("＞﹏＜ 红豆泥私密马赛 :(")
    
    def loginJCZX(self):
        if self.startJCZX():
            self.log.info("启动交错战线")
            self._waitClickAndMsg(self.Buttons.userLogin_button, self.Buttons.login_button, wait = 0.6)
            self._waitClickAndMsg(self.Buttons.login_button, self.Buttons.base_button, wait = 2, maxWaitSecond = 20)
            self._waitClickAndMsg(self.Buttons.noReminders_button, wait = 0.5, maxWaitSecond = 3, func = lambda: self._clickAndMsg(self.Buttons.closeNotice_button, wait = 1))
            self._waitClickAndMsg(self.Buttons.signIn_button, wait = 1, maxWaitSecond = 2, func = lambda: (self.clickGetItems(wait = 1), self.back()))
            self._waitClickAndMsg(self.Buttons.noRemindersBase_button, wait = 0.3, maxWaitSecond = 2, per = 0.7, func = lambda: self._clickAndMsg(self.Buttons.closeNotice_button, wait = 1, per = 0.8))
            self._waitClickAndMsg(self.Buttons.noRemindersBase_button, wait = 0.3, maxWaitSecond = 2, per = 0.5, func = lambda: self.click(self.width//2, self.height//5, 1))
    
    def lauchDevice(self, emulator):
        if self.DNConsole.CAN_RUN:
            if emulator in self.config.dnconsoleDevices.Devices.keys():
                if self.DNConsole.isrunning(self.config.dnconsoleDevices.Devices[emulator]):
                    return
                self.DNConsole.launchDevice(self.config.dnconsoleDevices.Devices[emulator])
                sleep(30)
    
    def gotoHome(self):
        if self.inLocation(self.ScreenLocs.home, cutPoints = self.ScreenCut.cut3x4(1, 3)):
            return
        if self.Pos.homePos:
            self.click(*self.Pos.homePos)
            self.log.info("前往【主界面】")
        else:
            if loc := self._clickAndMsg(self.Buttons.home_button, "前往【主界面】", "前往【主界面】失败", cutPoints = self.ScreenCut.cut3x7(0,0)):
                self.Pos.homePos = loc
            else:
                self.click(self.width//2, self.height//5, 1)
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
    
    def gotoCompetition(self):
        if self.inlocationCompetition:
            return
        else:
            self.gotoSimulatedMilitaryExercises()
            self._clickAndMsg(self.Buttons.competition_button, "前往【竞技场】", "前往【竞技场】失败", wait = 1, cutPoints = self.ScreenCut.cut2x1(0, 0))
            self.gotoCompetition()
    
    def gotoSimulatedMilitaryExercises(self):
        if self.inlocationSimulatedMilitaryExercises:
            return
        else:
            self.gotoLevels()
            self._clickAndMsg(self.Buttons.simulatedMilitaryExercises_button, "前往【模拟军演】", "前往【模拟军演】失败", wait = 1, cutPoints = self.ScreenCut.cut3x3(0, 1))
            self.gotoSimulatedMilitaryExercises()
    
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
            if not self._clickAndMsg(self.ScreenLocs.ZhouSi_a_3, wait = 3, deepLog = False, cutPoints = self.ScreenCut.cut1x2(0, 0)):
                self.autoPlayLevels()
                self._clickAndMsg(self.ScreenLocs.ZhouSi_a_3, wait = 3, deepLog = False, cutPoints = self.ScreenCut.cut1x2(0, 0))
            self._clickAndMsg(self.ScreenLocs.ZhouSiBoss_a,  wait = 3, cutPoints = self.ScreenCut.cut1x2(0, 0), per = 0.8)
            self.autoPlayLevels()
        else:
            self._clickAndMsg(self.ScreenLocs.ZhouSi_b_1, wait = 3, deepLog = False, cutPoints = self.ScreenCut.cut2x1(0, 0))
            self._clickAndMsg(self.ScreenLocs.ZhouSi_b_2, wait = 7, deepLog = False, cutPoints = self.ScreenCut.cut3x3(1, 1))
            if not self._clickAndMsg(self.ScreenLocs.ZhouSi_b_3, wait = 3, deepLog = False, cutPoints = self.ScreenCut.cut1x2(0, 0)):
                self.autoPlayLevels()
                self._clickAndMsg(self.ScreenLocs.ZhouSi_b_3, wait = 3, deepLog = False, cutPoints = self.ScreenCut.cut1x2(0, 0))
            self._clickAndMsg(self.ScreenLocs.ZhouSiBoss_b, wait = 3, cutPoints = self.ScreenCut.cut1x2(0, 0), per = 0.8)
            self.autoPlayLevels()
    
    def playIllusionARuiSi(self):
        self._clickAndMsg(self.ScreenLocs.ARuiSi_1, wait = 3, deepLog = False)
        self._clickAndMsg(self.ScreenLocs.ARuiSi_2, wait = 3, deepLog = False)
        self._clickAndMsg(self.ScreenLocs.ARuiSi_3, wait = 3, deepLog = False)
        self.autoPlayLevels()
        self._clickAndMsg(self.ScreenLocs.ARuiSi_4, wait = 3, deepLog = False)
        self.autoPlayLevels()
        self.click(self.width//2, self.height//4, 3)
        self.autoPlayLevels()
    
    def autoPlayLevels(self, wait = 0) -> bool:
        while not self.inLocationONfight:
            self.clickSkipAnimation()
            sleep(0.3)
        self._clickAndMsg(self.Buttons.fightAuto_button, deepLog = False, cutPoints = self.ScreenCut.cut4x3(3, 0), per = 0.8)
        win = None
        while True:
            info = self.findImageDetailLocations(self.ScreenLocs.fightWin, cutPoints = self.ScreenCut.cut2x2(0, 0))
            if info.matchTempleteCenterPoint:
                win = True
                break
            if self.findImageCenterLocation(self.ScreenLocs.fightLoss1, cutPoints = self.ScreenCut.cut2x2(0, 0), grayScreenshot = info.baseGrayScreenshot):
                win = False
                break
            if loc := self.findImageCenterLocation(self.ScreenLocs.fightLoss2, cutPoints = self.ScreenCut.cut1x2(0, 0), grayScreenshot = info.baseGrayScreenshot):
                # self.clickButton(self.Buttons.fightLossBack_button, cutPoints = self.ScreenCut.cut2x4(0, 3), grayScreenshot = info.baseGrayScreenshot)
                sleep(1)
                self.click(*loc)
                win = False
                break
            if self.inLocationGetItems:
                self.click(self.width//2, self.height//2, 1)
            sleep(0.3)
        self.click(self.width//2, self.height//2, 1)
        self.click(self.width//2, self.height//2, 7)
        sleep(wait)
        return win
        
    def gotoIllusions(self):
        if self.inLocationIllusions:
            return
        else:
            self.gotoActivities()
        if not self.clickIllusionsButton():
            self.gotoIllusions()
    
    def gotoMenu(self):
        if self.inLocation(self.ScreenLocs.menu, self.ScreenCut.cut2x1(1, 0)):
            return
        else:
            self.gotoHome()
        if self.Pos.menuPos:
            self.click(*self.Pos.menuPos)
            self.log.info("点击【菜单】")
        else:
            if loc := self._clickAndMsg(self.Buttons.menu_button, "点击【菜单】", "点击【菜单】失败", cutPoints = self.ScreenCut.cut9x9(8, 0)):
                self.Pos.menuPos = loc
            else:
                self.gotoMenu()
        sleep(1)
    
    def gotoFriend(self):
        if self.inLocation(self.ScreenLocs.friend, self.ScreenCut.cut9x9(0, 8)):
            return
        else:
            self.gotoMenu()
        if self.Pos.friendPos:
            self.click(*self.Pos.friendPos)
            self.log.info("前往【好友界面】")
        else:
            if loc := self._clickAndMsg(self.Buttons.friends_button, "前往【好友界面】", "前往【好友界面】失败", cutPoints = self.ScreenCut.cut2x1(1, 0)):
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
            if loc := self._clickAndMsg(self.Buttons.base_button, "前往【基地】", "前往【基地】失败"):
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
    
    def clickChoiceFriendTradingPost(self):
        if loc := self.Pos.choiceFriendTPPos:
            self.click(*loc)
        else:
            loc = self._clickAndMsg(self.Buttons.choiceFriendTP_button, wait = 0.3, cutPoints = self.ScreenCut.cut7x2(0, 1))
        return loc
    
    def clickRightSwitchFriendTradingPost(self):
        return self._clickAndMsg(self.Buttons.rightSwitchTradingPost_buttion, wait = 0.5, deepLog = False, cutPoints = self.ScreenCut.cut4x2(0, 1))
    
    def clickLeftSwitchFriendTradingPost(self):
        return self._clickAndMsg(self.Buttons.leftSwitchTradingPost_buttion, wait = 0.5, deepLog = False, cutPoints = self.ScreenCut.cut7x2(0, 1))
    
    def clickChallengeCompetition(self):
        return self._waitClickAndMsg(self.Buttons.challenge_button, wait = 1, cutPoints = self.ScreenCut.cut1x4(0, 3), per = 0.8)
    
    def addAndCraft(self, num:int):
        loc = self.findImageCenterLocation(self.Buttons.add_button, cutPoints = self.ScreenCut.cut3x3(2, 1))
        for _ in range(num - 1):
            self.click(*loc, wait = 0.1)
        self.craftSure()
    
    def checkAndSpendOrders(self):
        """检查并交付订单"""
        grayScreenshot = self.grayScreenshot()
        self.__checkOrders(grayScreenshot = grayScreenshot)
        if self.inLocation(self.ScreenLocs.tabBar, self.ScreenCut.cut7x1(6, 0), per = 0.8, grayScreenshot = grayScreenshot):
            self.swipeUPScreenCenter()
            self.__checkOrders(self.ScreenCut.cut1x2(0, 1))
    
    def __checkOrders(self, cutPoints = None, grayScreenshot = None):
        self.log.info("正在检索【订单】")
        if grayScreenshot is None:
            grayScreenshot = self.grayScreenshot()
        for img,des,craft in self.getUserOrderPaths():
            # if self._clickAndMsg(img, wait = 0.3, log = False, per = 0.95):
            if locality := self.findImageCenterLocation(img, cutPoints, per = 0.94, grayScreenshot = grayScreenshot):
                self.log.info(f"发现订单【{des}】")
                # if self.findImageCenterLocation(self.ScreenLocs.notEnough, self.ScreenCut.cut3x3(1, 1)):
                templete = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
                h, w = templete.shape
                x, y = locality
                x0, y0 = x-w//2, y+h//2
                x1, y1 = x+w//2, y+h//2+h
                if self.findImageCenterLocation(self.ScreenLocs.notEnough, ((x0, y0), (x1, y1)), 0.8, grayScreenshot):
                    if not craft:
                        self.log.info("当前订单材料不足")
                        # self._clickAndMsg(self.Buttons.cancel_button, wait = 0.3, cutPoints = self.ScreenCut.cut4x2(1, 1))
                        continue
                    self.click(*locality, 0.3)
                    if img in self.Orders.BuildOrders:
                        ticketRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.ticketRaw_button)
                        self.makeSure(2)
                        #合成黑盒
                        self._clickAndMsg(self.Buttons.craftTicketRaw_button, "点击【稀有黑匣】", "点击【稀有黑匣】失败", wait = 0.3, per = 0.8)
                        self.addAndCraft(ticketRawNum)
                        self.log.info(f"合成【稀有黑匣】x{ticketRawNum}")
                    elif img in self.Orders.CoinOrders:
                        coinRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.coinRaw_button)
                        self.makeSure(2)
                        #合成星币原料
                        self._clickAndMsg(self.Buttons.craftCoinRaw_button, "点击【星币碎片】", "点击【星币碎片】失败", wait = 0.3, per = 0.8)
                        self.addAndCraft(coinRawNum)
                        self.log.info(f"合成【星币碎片】x{coinRawNum}")
                    elif img in self.Orders.ExpOrders:
                        expRawNum = self.Orders.amount(img) - self.findRawNumbers(self.Buttons.expRaw_button)
                        self.makeSure(2)
                        #合成数据硬盘
                        self._clickAndMsg(self.Buttons.craftExpRaw_button, "点击【数据硬盘】", "点击【数据硬盘】失败", wait = 0.3, per = 0.8)
                        self.addAndCraft(expRawNum)
                        self.log.info(f"合成【数据硬盘】x{expRawNum}")
                    self.back(1)
                    self.back(1)
                    # self._clickAndMsg(img, wait = 1)
                    self.click(*locality, 1)
                    self.makeSure2(2)
                    self.submitOrders.append(des)
                else:
                    self.click(*locality, 0.3)
                    if self.makeSure2():
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
    
    def makeSure(self, wait = 0.3, log = False):
        if self.Pos.surePos:
            self.click(*self.Pos.surePos, wait)
        else:
            loc = self._clickAndMsg(self.Buttons.sure_button, wait = wait, deepLog = log, cutPoints = self.ScreenCut.cut4x2(2, 1))
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
        return self.clickGetItems()
    
    def craftSure(self):
        if self.Pos.craftPos:
            self.click(*self.Pos.craftPos, wait = 1)
        else:
            loc = self._clickAndMsg(self.Buttons.craftSure_button, wait = 1, cutPoints = self.ScreenCut.cut3x3(2, 2))
            self.Pos.craftPos = loc
        self.clickGetItems(1)
        self.click(self.width//2, self.height//4, wait = 1)
    
    def tellMeSubmitOrders(self):
        """告知我已交付订单"""
        if self.submitOrders:
            self.log.info("已提交订单"+" ".join(self.submitOrders))
            self.submitOrders.clear()
        else:
            self.log.info("无满足条件订单提交")
    
    def gotoFriendOrdersAndSpend(self):
        # self.useFriendListCheckOrderAndSpend()
        # self.useChoiceFriendCheckOrderAndSpend()
        self.useSwitchButtonFriendCheckOrderAndSpend()
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
                    # self.gotoChoiceFriendTradingPost()
                    self.clickChoiceFriendTradingPost()
                self.swipeLeftScreenCenter()
        self.click(self.width//2, self.height//1.2, 0.3)
    
    def useSwitchButtonFriendCheckOrderAndSpend(self):
        """使用订单库切换好友进入订单库进行检测交付"""
        self.gotoChoiceFriendTradingPost()
        grayScreenshot = self.grayScreenshot()
        visits = self.findImageCenterLocations(self.Buttons.visit_button, cutPoints = self.ScreenCut.cut1x2(0, 1), grayScreenshot = grayScreenshot)
        visiting = self.findImageCenterLocation(self.ScreenLocs.visiting, cutPoints = self.ScreenCut.cut1x2(0, 1), grayScreenshot = grayScreenshot)
        if not visits:
            return
        if visiting:
            visits = [(x, y) for x, y in visits if x > visiting[0]]
        if not visits:
            return
        else:
            loc = visits[0]
            self.click(*loc, wait = 1.5)
        for index in range(40):
            self.log.info(f"进入【好友交易所】{index + 1}")
            self.checkAndSpendOrders()
            if not self.clickRightSwitchFriendTradingPost():
                return
    
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
    
    def back(self, wait:int = 1, log = False):
        if self.Pos.backPos:
            self.click(*self.Pos.backPos, wait)
            self.log.info("返回上一界面")
        else:
            loc = self._clickAndMsg(self.Buttons.back_button, "返回上一界面", "返回上一界面失败", wait = wait, deepLog = log, cutPoints = self.ScreenCut.cut3x7(0, 0))
            self.Pos.backPos = loc
    
    def takeOre(self):
        if self.inLocation(self.ScreenLocs.base, self.ScreenCut.cut4x3(0, 2)):
            if self._clickAndMsg(self.Buttons.ore_button, "收集矿物", deepLog = False, cutPoints = self.ScreenCut.cut3x2(1, 1)):
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
    
    def _clickAndMsg(self, button_path, infoMsg:str = None, warnMsg:str = None, index:int = 0, wait:int = 0, deepLog:bool = True, cutPoints = None, per = 0.9, grayScreenshot = None) -> tuple[int, int] | None:
        if loc := self.clickButton(button_path, index, wait, deepLog, cutPoints, per, grayScreenshot):
            if infoMsg: self.log.info(infoMsg)
            return loc
        else:
            if warnMsg: self.log.warning(warnMsg)
            return None
    
    def _waitClickAndMsg(self, button_path, newLocation: Callable | str = None, infoMsg:str = None, warnMsg:str = None, index:int = 0, wait:int = 0, maxWaitSecond:int = 0, log:bool = False, cutPoints = None, per = 0.9, waitFunc:Callable = lambda: ..., func: Callable = lambda: ...) -> None:
        """等待并点击按钮
        - button_path   按钮样板路径
        - newLocation   点击按钮后前往的界面
        - infoMsg       info等级日志信息
        - warnMsg       warn等级日志信息
        - index         若按钮匹配多个，则可指定索引
        - wait          点击后等待延迟
        - maxWaitSecond 最大等待时间
        - log           深度Debug日志信息是否显示
        - cutPoints     图片截取部分
        - per           模板匹配程度0~1
        - waitFunc      等待过程中执行函数
        - func          点击按钮后等待延迟并执行函数
        """
        startTime = datetime.now()
        while True:
            loc = self._clickAndMsg(button_path, infoMsg, warnMsg, index, 0, log, cutPoints, per)
            waitFunc()
            if newLocation:
                if isinstance(newLocation, str):
                    if self.inLocation(newLocation):
                        break
                else:
                    if newLocation():
                        break
            elif loc:
                break
            sleep(0.3)
            runningTime = (datetime.now() - startTime).seconds
            if maxWaitSecond:
                if runningTime >= maxWaitSecond:
                    sleep(wait)
                    return
        sleep(wait)
        func()
    
    def _waitLocations(self, button_path, newLocation: Callable | str = None, wait:int = 0, maxWaitSecond:int = 0, cutPoints = None, per = 0.9, waitFunc:Callable = lambda: ..., func: Callable = lambda: ...):
        startTime = datetime.now()
        while True:
            locs = self.findImageCenterLocations(button_path, cutPoints, per)
            waitFunc()
            if newLocation:
                if isinstance(newLocation, str):
                    if self.inLocation(newLocation):
                        break
                else:
                    if newLocation():
                        break
            elif locs:
                break
            sleep(0.3)
            runningTime = (datetime.now() - startTime).seconds
            if maxWaitSecond:
                if runningTime >= maxWaitSecond:
                    sleep(wait)
                    return
        sleep(wait)
        func()
        return locs
        
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
    
    def findImageDetailLocations(self, button_path:str,  cutPoints = None, per:float = 0.9, grayScreenshot = None) -> MatchTempleteDetailInfo | None:
        """返回详细的匹配图像信息"""
        if cutPoints:
            x0, y0 = cutPoints[0]
        else:
            x0, y0 = 0, 0
        if grayScreenshot is None:
            baseGrayScreenshot = self.grayScreenshot()
            screenshot_gray = self.cutScreenshot(baseGrayScreenshot, cutPoints)
        else:
            baseGrayScreenshot = grayScreenshot
            screenshot_gray = self.cutScreenshot(grayScreenshot, cutPoints)
        assert exists(button_path), f"未找到 {button_path}"
        template_gray = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        matcher = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        locations = np.where(matcher > per)
        templeteHeight, temleteWidth = template_gray.shape[0:2]
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
            matchTempletePoints = [((x+x0, y+y0), (x+x0+temleteWidth, y+y0), (x+x0, y+y0+templeteHeight), (x+x0+temleteWidth, y+y0+templeteHeight)) for x,y in zip(tmp_x,tmp_y)]
            matchTempleteCenterPoints = [((x+temleteWidth//2)+x0,(y+templeteHeight//2)+y0) for x,y in zip(tmp_x,tmp_y)]
            return self.MatchTempleteDetailInfo(
                baseGrayScreenshot = baseGrayScreenshot,
                grayScreenshot = screenshot_gray,
                templeteSize = template_gray.shape[1::-1],
                matchTempletePoints = matchTempletePoints,
                matchTempleteCenterPoints = matchTempleteCenterPoints
            )
        else:
            return self.MatchTempleteDetailInfo(
                baseGrayScreenshot = baseGrayScreenshot,
                grayScreenshot = screenshot_gray,
                templeteSize = template_gray.shape[1::-1],
                matchTempletePoints = None,
                matchTempleteCenterPoints = None
            )
    
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
        if tmp := self._waitLocations(self.ScreenLocs.helpFriend, maxWaitSecond = 4, cutPoints = self.ScreenCut.cut2x1(1, 0)):
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
            screenshot_gray = self.cutScreenshot(grayScreenshot, cutPoints)
        assert exists(button_path), f"未找到 {button_path}"
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
            if loc := self._clickAndMsg(self.Buttons.accept_button, "点击【同意】x∞", wait = 0.7, deepLog = False, cutPoints = self.ScreenCut.cut3x2(2, 0)):
                self.Pos.acceptPos = loc
    
    def swipe(self, x1:int, y1:int, x2:int, y2:int, duration:int = 200, wait:int = 0):
        cmd = [self.adb_path, "-s", self.device, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)]
        subprocess.run(cmd, startupinfo = self.startupinfo)
        self.log.debug(f"执行滑动 {' '.join(cmd)}")
        sleep(wait)
    
    def dragAndDrop(self, x1:int, y1:int, x2:int, y2:int, duration:int = 200, wait:int = 0):
        cmd = [self.adb_path, "-s", self.device, "shell", "input", "draganddrop", str(x1), str(y1), str(x2), str(y2), str(duration)]
        subprocess.run(cmd, startupinfo = self.startupinfo)
        self.log.debug(f"执行拖动 {' '.join(cmd)}")
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
    
    def setDevice(self, device: str):
        self.device = device
        self.initDeviceInfor()
    
    def setADBPath(self, path):
        self.adb_path = path
    
    def startAPP(self, activity:str):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "am", "start", activity], startupinfo = self.startupinfo)
    
    def startJCZX(self):
        try:
            subprocess.check_output([self.adb_path, "-s", self.device, "shell", "pidof", "com.megagame.crosscore"], startupinfo = self.startupinfo)
            return False
        except:
            self.startAPP("com.megagame.crosscore/com.mjsdk.app.MJUnityActivity")
            return True
    
    def stopJCZX(self):
        subprocess.run([self.adb_path, "-s", self.device, "shell", "am", "force-stop", "com.megagame.crosscore"], startupinfo = self.startupinfo)
    
    @check
    def devices(self) -> list[str]:
        try:
            info = subprocess.check_output([self.adb_path, "devices"], startupinfo = self.startupinfo)
            devices = list(map(lambda x:x[:x.find("\t")], info.decode().split("\r\n")))[1:-2]
            return devices
        except:
            self.log.error("adb端口占用，或者模拟器未打开，请重启\打开模拟器，亦或者电脑")
            return []
    
    @check
    def setDNconsoleDevices(self):
        dnconsolePath = join(FileManage(file_path = self.adb_path).save_path, 'dnconsole.exe')
        if not self.DNConsole:
            self.DNConsole = self.DNConsoleExe(dnconsolePath)
        if self.DNConsole.CAN_RUN:
            for index in self.DNConsole.getEmulatorIndexs():
                emulator = self.DNConsole.getEmulatorName(index)
                if emulator:
                    self.config.dnconsoleDevices.setDevice(emulator, index)
    
class WorkThread(QThread, WorkTags):
    referADBSignal = pyqtSignal(str)
    
    def __init__(self, adb:JCZXGame = None, log:logging.Logger = None, config:JsonConfig = None) -> None:
        super().__init__()
        self.adb = adb
        self.log = log
        self.mode = None
        self.config = config
        self.workQueue = []
    
    def stop(self):
        if not self.isRunning(): return
        match self.mode:
            case self.ORDER:
                self.adb.tellMeSubmitOrders()
            case self.TASKS_LIST:
                self.adb.setDevice(self.config.adb_device)
        if self.mode not in (self.INIT_OCR, self.SET_ADBTOOLS):
            self.terminate()
            return True
        else:
            return False
    
    def setMode(self, mode:str, addQueue:bool = False):
        if addQueue:
            self.workQueue.append(mode)
        else:
            self.mode = mode
    
    def run(self) -> None:
        def _():
            self.loginJCZX()
            match self.mode:
                case None:
                    ...
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
                case self.SET_ADBTOOLS:
                    self.referADB()
                case self.ILLUSION_TO_FAVOR:
                    self.favor()
                case self.TASKS_LIST:
                    self.tasks()
                case self.JJC_TASK:
                    self.JJCTask()
                case self.INIT_OCR:
                    self.initOCR()
                case self.QUIT_JCZX:
                    (self.adb.stopJCZX(), self.log.info("退出游戏"))
                case self.QUIT_DEVICE:
                    self.adb.DNConsole.quitDevice(self.config.dnconsoleDevices.Devices[self.adb.device])
                    self.log.info(f"关闭模拟器【{self.adb.device}】")
                case _:
                    self.log.error(f"未知模式 {self.mode}")
        
        def work():
            _()
            while True:
                if self.workQueue:
                    self.setMode(self.workQueue.pop(0))
                    _()
                else:
                    break
        
        if LOG_LEVEL == logging.INFO:
            try:
                work()
            except Exception as e:
                self.log.error(f"捕获到错误抛出 {e}")
        else:
            work()

    def loginJCZX(self):
        if self.adb.device and self.mode not in (self.TASKS_LIST, self.INIT_OCR, self.SET_ADBTOOLS, self.QUIT_DEVICE, self.QUIT_JCZX) and self.mode:
            self.adb.loginJCZX()
            return True
        return False
                
    def __debug(self):
        adb = self.adb
        adb.gotoCompetition()
        info = adb.findImageDetailLocations(adb.ScreenLocs.firstScoreLoc, cutPoints = adb.ScreenCut.cut3x1(0, 0))
        # cv2.namedWindow('test', cv2.WINDOW_NORMAL)
        # cv2.imshow("test", cv2.rectangle(info.baseGrayScreenshot, *info.transRange(info.transMatchTempletePointFromSize(info.transMoveFromTemleteSize(rightMoveTimes = 1), rightHeightTimes = 1)), (255, 0, 0), 5))
        # cv2.waitKey()
        
    def setADB(self, adb):
        self.adb = adb
    
    def setLog(self, log):
        self.log = log
    
    @staticmethod
    def check(func):
        def _(self, *args, **kwargs):
            if not exists(self.config.adb_path):
                self.log.warning(f"{self.config.adb_path}不可用")
                self.setMode(self.SET_ADBTOOLS)
                self.run()
                return
            if self.config.adb_path:
                if self.config.adb_device:
                    func(self, *args, **kwargs)
                else:
                    self.log.error("当前未设置【设备】")
            else:
                self.log.error("当前未选择【ADB调试路径】")
        return _
    
    def referADB(self):
        self.referADBSignal.emit(self.adb.dowloadADBTools())
    
    def initOCR(self):
        self.log.info("开始载入OCR模块")
        # from easyocr import Reader
        # self.adb.ocr = Reader(["ch_sim", "en"], model_storage_directory = joinPath("EasyOCR", "model"), download_enabled = False)
        from paddleocr import PaddleOCR
        class OCR(PaddleOCR):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

            def readtext(self, img:MatLike):
                data = self.ocr(img, cls = False)
                result = []
                for line in data[0]:
                    text = line[1][0]
                    result.append(text)
                return result
            
        self.adb.ocr = OCR(
            use_angle_cls = False,
            lang = 'ch',
            use_gpu = False,
            enable_mkldnn = True,
            show_log = False,
            det_model_dir = joinPath('OCR', 'ch_PP-OCRv4_det_infer'),
            rec_model_dir = joinPath('OCR', 'ch_PP-OCRv4_rec_infer')
            # cls_model_dir = joinPath('OCR', 'ch_ppocr_mobile_v2.0_cls_infer')
        )
        self.log.info("OCR载入完成")
    
    @check
    def spendOrder(self):
        self.log.info("开始【交付订单】任务")
        self.adb.gotoTradingPost()
        #check orders
        self.adb.checkAndSpendOrders()
        self.adb.gotoFriendOrdersAndSpend()
        self.adb.gotoHome()
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
            # self.adb.clickStartFight()
            self.adb.waitClickStartFight()
            # self.adb.clickCloseUseThisTeam(1)
            self.adb.clickHelpFight(0)
            self.adb.clickReadyTeamPlane(1.2)
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
        self.adb.gotoHome()
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
                adb.gotoHome()
                self.log.info("微晶已满【虚影微晶】任务结束")
    
    @check
    def favor(self):
        teamNum = self.config.favor.teamNum
        self.log.info(f"开始【虚影】任务")
        self.log.info(f"使用第{teamNum}小队，战斗{self.config.favor.time}次")
        adb = self.adb
        for i in range(self.config.favor.time):
            adb.gotoGeLiKeIllusion()
            adb.clickStartFight()
            match teamNum:
                case 1:
                    adb.clickCloseUseThisTeam(1)
                case 2:
                    adb.clickCloseUseThisTeam(0)
                case _ as x:
                    adb.clickCloseUseThisTeam(1)
                    adb.choiceFightTeam(0, x)
            adb.clickStartToAct(0, False)
            self.log.info(f"战斗 x {i+1}")
            adb.playIllusionARuiSi()
        adb.gotoHome()
        self.log.info("【虚影任务】结束")
    
    @check
    def tasks(self):
        tasks = self.config.tasks
        choice = tasks.choice
        task = tasks[choice]
        self.log.info(f"开始运行任务【{choice}】")
        for emulator, operate in task:
            self.adb.lauchDevice(emulator)
            if self.adb.device != emulator:
                self.adb.setDevice(emulator)
                self.log.info(f"设置设备【{emulator}】")
                self.loginJCZX()
            self.setMode(operate)
            self.run()
        if self.config.adb_device in self.adb.devices():
            self.adb.setDevice(self.config.adb_device)
        self.log.info(f"任务【{choice}】结束")
    
    @check
    def JJCTask(self):
        adb = self.adb
        self.log.info(f"开始【竞技场】任务")
        adb.gotoCompetition()
        adb.challengeCompetition()
        adb.gotoHome()
        self.log.info(f"任务【竞技场】结束")
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = MainManager(app)
    manager.setupUi()