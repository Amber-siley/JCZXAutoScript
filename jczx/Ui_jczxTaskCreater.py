# Form implementation generated from reading ui file 'e:\IDE\pyththon_project\jczx_auto_script\jczx\jczx\jczxTaskCreater.ui'
#
# Created by: PyQt6 UI code generator 6.4.2
#
# WARNING: Any manual changes made to this file will be lost when pyuic6 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_jczxTaskCreater(object):
    def setupUi(self, jczxTaskCreater):
        jczxTaskCreater.setObjectName("jczxTaskCreater")
        jczxTaskCreater.resize(400, 200)
        jczxTaskCreater.setMinimumSize(QtCore.QSize(400, 200))
        jczxTaskCreater.setMaximumSize(QtCore.QSize(400, 200))
        jczxTaskCreater.setStyleSheet("QWidget {\n"
"    color: black;\n"
"    border: 1px;\n"
"    background-color: white;\n"
"}\n"
"QLineEdit {\n"
"    border: 1px solid #dcdfe6;\n"
"    border-radius: 2px;\n"
"    padding-left: 3px;\n"
"}\n"
"QListWidget {\n"
"    border: 1px solid #dcdfe6;\n"
"}\n"
"QScrollBar::vertical {\n"
"background:transparent;\n"
"width:2px;\n"
"border:0px;\n"
"}\n"
"\n"
"QScrollBar::handle:vertical {\n"
"background:rgb(190, 190, 190);\n"
"width:2px;\n"
"}\n"
"\n"
"QScrollBar::add-line:vertical {\n"
"background:none;\n"
"border:none;\n"
"}\n"
"\n"
"QScrollBar::sub-line:vertical {\n"
"background:none;\n"
"border:none;\n"
"}\n"
"\n"
"QScrollBar::add-page:vertical {\n"
"background:transparent;\n"
"border:none;\n"
"}\n"
"\n"
"QScrollBar::sub-page:vertical {\n"
"background:transparent;\n"
"border:none;\n"
"}\n"
"\n"
"QComboBox {\n"
"    border: 1px solid #dcdfe6;\n"
"    padding: 0px;\n"
"    padding-left: 3px;\n"
"}\n"
"QComboBox::drop-down {\n"
"    border: 0px;\n"
"    width: 0px;\n"
"}\n"
"QComboBox::down-arrow {\n"
"    background-color: transparent;\n"
"}\n"
"QPushButton {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #dcdfe6;\n"
"    border-radius: 1px;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"    background-color: #ecf5ff;\n"
"    color: #409eff;\n"
"}\n"
"\n"
"QPushButton:pressed, QPushButton:checked {\n"
"    border: 1px solid #3a8ee6;\n"
"    color: #409eff;\n"
"}\n"
"")
        self.widget = QtWidgets.QWidget(parent=jczxTaskCreater)
        self.widget.setGeometry(QtCore.QRect(0, 0, 401, 201))
        self.widget.setStyleSheet("")
        self.widget.setObjectName("widget")
        self.Options_widget = QtWidgets.QWidget(parent=self.widget)
        self.Options_widget.setGeometry(QtCore.QRect(0, 0, 171, 201))
        self.Options_widget.setObjectName("Options_widget")
        self.TaskList_label = QtWidgets.QLabel(parent=self.Options_widget)
        self.TaskList_label.setGeometry(QtCore.QRect(0, 0, 71, 24))
        self.TaskList_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.TaskList_label.setIndent(-1)
        self.TaskList_label.setObjectName("TaskList_label")
        self.TaskList_comboBox = QtWidgets.QComboBox(parent=self.Options_widget)
        self.TaskList_comboBox.setGeometry(QtCore.QRect(70, 0, 101, 24))
        self.TaskList_comboBox.setObjectName("TaskList_comboBox")
        self.renameTask_lineEdit = QtWidgets.QLineEdit(parent=self.Options_widget)
        self.renameTask_lineEdit.setGeometry(QtCore.QRect(70, 24, 71, 24))
        self.renameTask_lineEdit.setObjectName("renameTask_lineEdit")
        self.renameTask_label = QtWidgets.QLabel(parent=self.Options_widget)
        self.renameTask_label.setGeometry(QtCore.QRect(0, 24, 71, 24))
        self.renameTask_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.renameTask_label.setIndent(-1)
        self.renameTask_label.setObjectName("renameTask_label")
        self.renameTask_Button = QtWidgets.QPushButton(parent=self.Options_widget)
        self.renameTask_Button.setGeometry(QtCore.QRect(140, 24, 30, 24))
        self.renameTask_Button.setObjectName("renameTask_Button")
        self.delTask_Button = QtWidgets.QPushButton(parent=self.Options_widget)
        self.delTask_Button.setGeometry(QtCore.QRect(0, 48, 171, 30))
        self.delTask_Button.setStyleSheet("QPushButton:hover {\n"
"    background-color: rgb(255, 239, 239);\n"
"    color: rgb(255, 32, 36);\n"
"}\n"
"\n"
"QPushButton:pressed, QPushButton:checked {\n"
"    border: 1px solid #3a8ee6;\n"
"    color: #409eff;\n"
"}")
        self.delTask_Button.setObjectName("delTask_Button")
        self.decollator_label = QtWidgets.QLabel(parent=self.Options_widget)
        self.decollator_label.setGeometry(QtCore.QRect(0, 80, 171, 16))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.decollator_label.sizePolicy().hasHeightForWidth())
        self.decollator_label.setSizePolicy(sizePolicy)
        self.decollator_label.setStyleSheet("QLabel {\n"
"    border-bottom: 1px solid rgb(220, 223, 230)\n"
"}")
        self.decollator_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.decollator_label.setIndent(-1)
        self.decollator_label.setObjectName("decollator_label")
        self.newNameTask_label = QtWidgets.QLabel(parent=self.Options_widget)
        self.newNameTask_label.setGeometry(QtCore.QRect(0, 95, 71, 24))
        self.newNameTask_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.newNameTask_label.setIndent(-1)
        self.newNameTask_label.setObjectName("newNameTask_label")
        self.newNameTask_lineEdit = QtWidgets.QLineEdit(parent=self.Options_widget)
        self.newNameTask_lineEdit.setGeometry(QtCore.QRect(70, 95, 71, 24))
        self.newNameTask_lineEdit.setObjectName("newNameTask_lineEdit")
        self.newNameTask_Button = QtWidgets.QPushButton(parent=self.Options_widget)
        self.newNameTask_Button.setGeometry(QtCore.QRect(140, 95, 30, 24))
        self.newNameTask_Button.setObjectName("newNameTask_Button")
        self.saveTaskList_Button = QtWidgets.QPushButton(parent=self.Options_widget)
        self.saveTaskList_Button.setGeometry(QtCore.QRect(0, 116, 171, 42))
        self.saveTaskList_Button.setStyleSheet("QPushButton:hover {\n"
"    background-color: rgb(226, 255, 233);\n"
"    color: #409eff;\n"
"}\n"
"\n"
"QPushButton:pressed, QPushButton:checked {\n"
"    border: 1px solid #3a8ee6;\n"
"    color: #409eff;\n"
"}")
        self.saveTaskList_Button.setObjectName("saveTaskList_Button")
        self.saveAndQuit_Button = QtWidgets.QPushButton(parent=self.Options_widget)
        self.saveAndQuit_Button.setGeometry(QtCore.QRect(0, 158, 171, 42))
        self.saveAndQuit_Button.setStyleSheet("QPushButton:hover {\n"
"    background-color: rgb(255, 239, 239);\n"
"    color: rgb(255, 32, 36);\n"
"}\n"
"\n"
"QPushButton:pressed, QPushButton:checked {\n"
"    border: 1px solid #3a8ee6;\n"
"    color: #409eff;\n"
"}")
        self.saveAndQuit_Button.setObjectName("saveAndQuit_Button")
        self.TaskList_label.raise_()
        self.renameTask_label.raise_()
        self.renameTask_Button.raise_()
        self.renameTask_lineEdit.raise_()
        self.delTask_Button.raise_()
        self.newNameTask_label.raise_()
        self.newNameTask_lineEdit.raise_()
        self.newNameTask_Button.raise_()
        self.TaskList_comboBox.raise_()
        self.saveTaskList_Button.raise_()
        self.saveAndQuit_Button.raise_()
        self.decollator_label.raise_()
        self.listWidget = QtWidgets.QListWidget(parent=self.widget)
        self.listWidget.setGeometry(QtCore.QRect(169, 72, 231, 129))
        self.listWidget.setObjectName("listWidget")
        self.widget_2 = QtWidgets.QWidget(parent=self.widget)
        self.widget_2.setGeometry(QtCore.QRect(170, 0, 231, 48))
        self.widget_2.setObjectName("widget_2")
        self.newTaskItem_Button = QtWidgets.QPushButton(parent=self.widget_2)
        self.newTaskItem_Button.setGeometry(QtCore.QRect(180, 0, 51, 48))
        self.newTaskItem_Button.setObjectName("newTaskItem_Button")
        self.newTaskItem_label = QtWidgets.QLabel(parent=self.widget_2)
        self.newTaskItem_label.setGeometry(QtCore.QRect(1, 24, 71, 24))
        self.newTaskItem_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.newTaskItem_label.setIndent(-1)
        self.newTaskItem_label.setObjectName("newTaskItem_label")
        self.newTaskItem_comboBox = QtWidgets.QComboBox(parent=self.widget_2)
        self.newTaskItem_comboBox.setGeometry(QtCore.QRect(70, 24, 111, 24))
        self.newTaskItem_comboBox.setObjectName("newTaskItem_comboBox")
        self.emulator_label = QtWidgets.QLabel(parent=self.widget_2)
        self.emulator_label.setGeometry(QtCore.QRect(0, 0, 71, 24))
        self.emulator_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.emulator_label.setIndent(-1)
        self.emulator_label.setObjectName("emulator_label")
        self.emulator_comboBox = QtWidgets.QComboBox(parent=self.widget_2)
        self.emulator_comboBox.setGeometry(QtCore.QRect(70, 0, 111, 24))
        self.emulator_comboBox.setObjectName("emulator_comboBox")
        self.nowViewTaskList_lineEdit = QtWidgets.QLineEdit(parent=self.widget)
        self.nowViewTaskList_lineEdit.setGeometry(QtCore.QRect(240, 48, 161, 24))
        self.nowViewTaskList_lineEdit.setReadOnly(True)
        self.nowViewTaskList_lineEdit.setObjectName("nowViewTaskList_lineEdit")
        self.nowViemTaskList_label = QtWidgets.QLabel(parent=self.widget)
        self.nowViemTaskList_label.setGeometry(QtCore.QRect(170, 48, 71, 24))
        self.nowViemTaskList_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.nowViemTaskList_label.setIndent(-1)
        self.nowViemTaskList_label.setObjectName("nowViemTaskList_label")
        self.widget_2.raise_()
        self.Options_widget.raise_()
        self.listWidget.raise_()
        self.nowViemTaskList_label.raise_()
        self.nowViewTaskList_lineEdit.raise_()

        self.retranslateUi(jczxTaskCreater)
        QtCore.QMetaObject.connectSlotsByName(jczxTaskCreater)

    def retranslateUi(self, jczxTaskCreater):
        _translate = QtCore.QCoreApplication.translate
        jczxTaskCreater.setWindowTitle(_translate("jczxTaskCreater", "TaskCreater"))
        self.TaskList_label.setText(_translate("jczxTaskCreater", "任务列表："))
        self.renameTask_label.setText(_translate("jczxTaskCreater", "重命名："))
        self.renameTask_Button.setText(_translate("jczxTaskCreater", "命名"))
        self.delTask_Button.setText(_translate("jczxTaskCreater", "删除任务"))
        self.decollator_label.setText(_translate("jczxTaskCreater", "==================="))
        self.newNameTask_label.setText(_translate("jczxTaskCreater", "新建任务："))
        self.newNameTask_Button.setText(_translate("jczxTaskCreater", "新建"))
        self.saveTaskList_Button.setText(_translate("jczxTaskCreater", "保存"))
        self.saveAndQuit_Button.setText(_translate("jczxTaskCreater", "保存并退出"))
        self.newTaskItem_Button.setText(_translate("jczxTaskCreater", "添加"))
        self.newTaskItem_label.setText(_translate("jczxTaskCreater", "添加项："))
        self.emulator_label.setText(_translate("jczxTaskCreater", "模拟器："))
        self.nowViemTaskList_label.setText(_translate("jczxTaskCreater", "当前预览："))
