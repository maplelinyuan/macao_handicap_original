from PyQt5 import QtCore, QtGui, QtWidgets, QtSql
import time
import datetime
import json
import pdb
import os
from apscheduler.schedulers.background import BackgroundScheduler

def is_chinese(uchar):
    """判断一个unicode是否是汉字"""
    if uchar >= u'\u4e00' and uchar <= u'\u9fa5':
        return True
    else:
        return False

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        self.league_name = ''

        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(680, 600)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label1 = QtWidgets.QLabel(MainWindow)  # 绑定label到窗口
        self.label1.setText("最后更新时间：")  # 设置label标签的文字内容
        self.label1.setGeometry(10, 20, 100, 20)  # 设置控件相对父窗口位置宽高 参数(x,y,w,h)
        self.label2 = QtWidgets.QLabel(MainWindow)  # 绑定label到窗口
        self.label2.setText("")  # 设置label标签的文字内容
        self.label2.setGeometry(120, 20, 200, 20)  # 设置控件相对父窗口位置宽高 参数(x,y,w,h)
        self.pushButton = QtWidgets.QPushButton(self.centralwidget)
        self.pushButton.setGeometry(QtCore.QRect(580, 20, 75, 23))
        self.pushButton.setObjectName("pushButton")
        self.tableWidget = QtWidgets.QTableWidget(self.centralwidget)
        self.tableWidget.setGeometry(QtCore.QRect(10, 60, 650, 500))
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setColumnCount(6)
        self.tableWidget.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(5, item)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 23))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

        self.pushButton.clicked.connect(self.analysingData)   ##用来将切换中/英按钮关联的函数

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Macao_Handicap_Analysis"))
        item = self.tableWidget.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "开赛时间"))
        item = self.tableWidget.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "主队名"))
        item = self.tableWidget.horizontalHeaderItem(2)
        item.setText(_translate("MainWindow", "盘口"))
        item = self.tableWidget.horizontalHeaderItem(3)
        item.setText(_translate("MainWindow", "客队名"))
        item = self.tableWidget.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "联赛名称"))
        item = self.tableWidget.horizontalHeaderItem(5)
        item.setText(_translate("MainWindow", "支持方向"))
        self.pushButton.setText(_translate("MainWindow", "分析"))

    # 执行爬虫
    def exe_crawl(self):
        crawl_commend = 'scrapy crawl aoke'
        return os.system(crawl_commend)

    # 打印表格信息
    def print_form_info(self, match_info_list):
        nowatime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')  # 当前时间
        print('开始打印分析结果：')
        # 先清空所有表项
        self.tableWidget.clearContents()
        # 设置行数
        self.tableWidget.setRowCount(len(match_info_list))
        row_count = 0
        for i in range(len(match_info_list)):
            # 循环填入数据
            col_count = 0
            for j in range(self.tableWidget.columnCount()):
                if col_count == 0:
                    cnt = '%s' % (
                        match_info_list[i]['start_time']
                    )
                elif col_count == 1:
                    cnt = '%s' % (
                        match_info_list[i]['host']
                    )
                elif col_count == 2:
                    cnt = '%s' % (
                        match_info_list[i]['handicap']
                    )
                elif col_count == 3:
                    cnt = '%s' % (
                        match_info_list[i]['guest']
                    )
                elif col_count == 4:
                    cnt = '%s' % (
                        match_info_list[i]['league_name']
                    )
                elif col_count == 5:
                    cnt = '%d' % (
                        match_info_list[i]['support']
                    )
                newItem = QtWidgets.QTableWidgetItem(cnt)
                self.tableWidget.setItem(row_count, col_count, newItem)
                col_count += 1
            row_count += 1
        self.tableWidget.resizeColumnsToContents()
        self.tableWidget.setSortingEnabled(True)
        self.label2.setText(nowatime)  # 设置最后更新时间

    # 更新数据
    # def updateData(self):
    #     nowatime = datetime.datetime.now().strftime('%Y_%m_%d_%H%M')  # 当前时间
    #     self.exe_crawl()
    #     # 先连接至分析数据库获取上次所用分析表的时间
    #     db = QtSql.QSqlDatabase().addDatabase("QMYSQL")
    #     db.setDatabaseName("macao_handicap_analysis")
    #     db.setHostName("127.0.0.1")  # set address
    #     db.setUserName("root")  # set user name
    #     db.setPassword("1994")  # set user pwd
    #     if not db.open():
    #         # 打开失败
    #         return db.lastError()
    #     print("连接至 macao_handicap_analysis success!")
    #     # 创建QsqlQuery对象，用于执行sql语句
    #     query = QtSql.QSqlQuery()
    #     # 查询出刚才更新的表
    #     table_name = 'macao_handicap_analysis' + nowatime
    #     query.exec('SELECT * FROM ' + table_name)
    #     query.next()
    #     if query.size() > 0:
    #         print('查询不到数据')
    #     match_info_list = []
    #     for i in range(query.size()):
    #         match_info = {}
    #         match_info['start_time'] = query.value(4)
    #         match_info['host'] = query.value(1)
    #         match_info['handicap'] = query.value(8)
    #         match_info['guest'] = query.value(2)
    #         match_info['league_name'] = query.value(3)
    #         match_info['support'] = query.value(9)
    #         match_info_list.append(match_info)
    #         query.next()
    #     if len(match_info_list) > 0:
    #         self.print_form_info(match_info_list)
    #     db.close()
    #     print('断开数据库')

    # 开始拉取今天数据并分析
    def analysingData(self):
        nowatime = datetime.datetime.now().strftime('%Y_%m_%d_%H%M')    # 当前时间
        self.exe_crawl()

        # 先连接至分析数据库获取上次所用分析表的时间
        db = QtSql.QSqlDatabase().addDatabase("QMYSQL")
        db.setDatabaseName("macao_handicap_analysis")
        db.setHostName("127.0.0.1")  # set address
        db.setUserName("root")  # set user name
        db.setPassword("1994")  # set user pwd
        if not db.open():
            # 打开失败
            print('打开数据库失败！')
            return db.lastError()
        print("连接至 macao_handicap_analysis success!")
        # 创建QsqlQuery对象，用于执行sql语句
        query = QtSql.QSqlQuery()
        query.exec('show tables')
        query.first()
        # 查询出刚才更新的表
        table_name = query.value(0)
        query.exec('SELECT * FROM '+table_name)
        query.next()
        match_info_list = []
        for i in range(query.size()):
            start_time = time.strptime(query.value(4), "%Y-%m-%d %H:%M")
            mk_start_time = time.mktime(start_time)
            match_id = query.value(0)
            # 定时任务
            # if (time.time() - mk_start_time) < 0:
            #     f = open('timer_id.txt', 'r')
            #     timer_text = f.read()
            #     timer_list = timer_text.split(',')
            #     f.close()
            #     if not match_id in timer_list:
            #         scheduler = BackgroundScheduler()
            #         scheduler.add_job(self.updateData, 'date', run_date=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(mk_start_time))) # 在指定的时间，只执行一次
            #         print('设定定时任务,match_id:',match_id,'开始时间',start_time)
            #         # 将定时执行的比赛id写入,防止重复
            #         f = open('timer_id.txt', 'a')
            #         f.write(match_id+',')
            #         f.close()
            #         scheduler.start()  # 这里的调度任务是独立的一个线程
            match_info = {}
            match_info['start_time'] = query.value(4)
            match_info['host'] = query.value(1)
            match_info['handicap'] = query.value(8)
            match_info['guest'] = query.value(2)
            match_info['league_name'] = query.value(3)
            match_info['support'] = query.value(9)
            match_info_list.append(match_info)
            query.next()
        if len(match_info_list) > 0:
            self.print_form_info(match_info_list)
        db.close()
        print('断开数据库')

if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
