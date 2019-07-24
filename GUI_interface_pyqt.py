"""
Created on Fri Nov 9 2018
@author: Ali Hanks
"""

import sys
import numpy as np
import math
import time
import datetime as dt
import csv
import sys
import os
import pika
import json
import atexit
import traceback
import argparse
import fnmatch
import pandas as pd
import pylab

from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QPushButton, QListWidget, QMessageBox
from PyQt5.QtWidgets import QAction, QLineEdit, QMessageBox, QLabel, QRadioButton
from PyQt5.QtWidgets import QMenu, QGridLayout, QFormLayout, QSpacerItem, QSizePolicy
from PyQt5.Qt import QHBoxLayout, QVBoxLayout #new imports
from PyQt5.QtWidgets import QCheckBox
from pyqtgraph import QtGui
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtGui import QPalette, QFont, QTabWidget, QTabBar, QComboBox, QBrush, QImage
from PyQt5.QtGui import QStyleFactory
import matplotlib.pyplot as plt

import pyqtgraph as pg

import random

# Various function calls to set general look
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

# Set text for sensor types
RAD = "Radiation"
AIR = "Air Quality"
CO2 = "CO2"
PTH = "P/T/H"

good_background = "background-color:#33FF99;"
okay_background = "background-color:#FFFF00;"
med_background = "background-color:#FF8000;"
bad_background = "background-color:#FF0000;"
verybad_background = "background-color:#FF66B2;"

vLine = pg.InfiniteLine(angle=90, movable=False)
hLine = pg.InfiniteLine(angle=0, movable=False)
global ex
global proxy

def mouseMoved(evt):
    global ex
    pos = evt[0]  ## using signal proxy turns arguments into a tuple
    if ex.splot.sceneBoundingRect().contains(pos):
        mousePoint = ex.splot.vb.mapSceneToView(pos)
        index = int(mousePoint.x()/2.55)
        if index > 0 and index < len(ex.data[RAD]):
            ex.cursor_label.setText("<span style='font-size: 12pt'>Energy [keV] = %0.1f,   <span style='color: red'>Counts = %0.1f</span>" % (mousePoint.x(), ex.data[RAD][index]))
        vLine.setPos(mousePoint.x())
        hLine.setPos(mousePoint.y())

#class sscButton(object):
    #def __init__(self, label, row, column, color):
        #button = QPushButton(label)
        #self.layout.addWidget(checkbox, row, column)
        #button_style = "background-color: " + color
        #button.setStyleSheet(button_style)

class App(QWidget, object):

    def __init__(self, nbins=4096, test=False, windows=False, **kwargs):
        super().__init__()
        self.title = 'DoseNet Sensor GUI'
        self.left = 0
        self.test_mode = test
        self.windows = windows

        bg = QImage("dosenet.png")
        palette = QPalette()
        palette.setBrush(10, QBrush(bg))
        self.setPalette(palette)
        
        if not self.test_mode:
            import pika

        if windows:
            self.top = 80
            self.width = 1280
            self.height = 720

        else:
            self.top = 20
            self.width = 800
            self.height = 440

        self.nbins = nbins
        self.start_time = None
        self.plot_list = {}
        self.err_list = {}
        self.sensor_list = {}
        self.sensor_tab = {}
        self.data_display = {}
        self.data = {}
        self.time_data = {}
        self.saveData = False
        self.channels = np.arange(self.nbins, dtype=float) * 2.55

        self.setFixedSize(800, 440)
        self.initUI()

    def initUI(self):
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QPalette.Base)
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.initLayout()
        self.setLayout(self.layout)

    def initLayout(self):
        # Create Grid layout
        self.layout = QGridLayout()
        #self.layout.setSpacing(0.01)
        self.layout.setContentsMargins(0.,0.,0.,0.)

        # Create main plotting area
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet("QTabWidget::tab-bar { alignment: left; } "+\
                "QTabWidget::pane { border: 2px solid #404040; } "+\
                "QTabBar {font-size: 18pt;}");
        tab_bar = QTabBar()
        tab_bar.setStyleSheet("QTabBar::tab { height: 25px; width: 150px;}")
        
        self.tabs.setTabBar(tab_bar)
        ptop, pleft, pheight, pwidth = 0, 0, 12, 12
        self.layout.addWidget(self.tabs,1,1,1,3) #ptop,pleft,pheight,pwidth)
        self.setCompTab()
        self.setSelectionTab()
        self.tabs.setCurrentIndex(1)

        # Create text label
        #label = QLabel('Select Sensors', self)

        #if self.windows:
        #    textfont = QFont("Helvetica Neue", 18, QFont.Bold)
        #else:
        #    textfont = QFont("Helvetica Neue", 20, QFont.Bold)

        #label.setFont(textfont)
        #self.layout.addWidget(label,ptop,pleft+pwidth+1,1,1)
        #label.setAlignment(Qt.AlignCenter)

        # Create checkboxes for each sensor
        self.addCheckBox(RAD, 1, 4) #1, 2)
        self.addCheckBox(AIR, 2, 4) #2, 2)
        self.addCheckBox(CO2, 3, 4) #3, 2)
        self.addCheckBox(PTH, 4, 4) #4, 2)
 
        # Create textbox
        #self.textbox = QLineEdit(self)
        #self.layout.addWidget(self.textbox,ptop+1,pleft+pwidth+1,1,1)
        #self.textbox.setAlignment(Qt.AlignCenter)

        #Create start, stop, clear button
        start_button = QPushButton("Start")
        self.layout.addWidget(start_button, 2, 1)
        start_button_style = "background-color: #39c43e"
        start_button.setStyleSheet(start_button_style)
        start_button.clicked.connect(lambda: self.run(start_button))

        stop_button = QPushButton("Stop")
        self.layout.addWidget(stop_button, 2, 2)
        stop_button_style = "background-color: #de4545"
        stop_button.setStyleSheet(stop_button_style)
        stop_button.clicked.connect(lambda: self.stop(stop_button, clear_button))

        clear_button = QPushButton("Clear")
        self.layout.addWidget(clear_button, 2, 3)
        clear_button_style = "background-color: #a3d1ff"
        clear_button.setStyleSheet(clear_button_style)
        clear_button.clicked.connect(lambda: self.clear())        

    #def addButton(self,label,method,top,left,height,width,color):
        #'''
        #Add a button to the main layout
        #Inputs: label,
                #method: button action function,
                #location: top,left
                #size: height,width
                #color: background color for the button
        #'''
        #button = QPushButton(label, self)
        #style_sheet_text = "background-color: "+color+";"+\
                           #"border-style: outset;"+\
                           #"border-width: 2px;"+\
                           #"border-radius: 2px;"+\
                           #"border-color: beige;"+\
                           #"font: bold 20px;"+\
                           #"min-width: 6em;"+\
	                   #"color: color"
                           #"padding: 2px;"

        #button.setStyleSheet(style_sheet_text)
        #button.clicked.connect(method)
        #self.layout.addWidget(button,top,left,height,width,Qt.AlignHCenter)

    def addCheckBox(self, label, top, left):
        '''
        Add a checkbox to the main layout in the specified location (top,left)
        '''
        checkbox = QCheckBox(label)
        textfont = QFont("Helvetica Neue", 18)

        checkbox.setFont(textfont)
        checkbox.setChecked(False)
        checkbox.stateChanged.connect(lambda:self.sensorButtonState(checkbox))
        self.config_layout.addWidget(checkbox, top, left) #top, left

    def rmvSensorTab(self, sensor):
        '''
        Remove Sensor Tab from GUI
        '''
        self.tabs.removeTab(self.sensor_tab[sensor][0])
        if not self.test_mode:
            self.kill_sensor(sensor)

    def startSensor(self, sensor):
        fname = "/home/pi/data/" + self.file_name + '_' + \
                str(dt.datetime.today()).split()[0]
        if sensor==AIR:
            py = 'python'
            script = 'air_quality_DAQ.py'
            log = 'AQ_gui.log'
            if self.saveData:
                fname = fname + "_AQ.csv"
        if sensor==RAD:
            py = 'sudo python'
            script = 'D3S_rabbitmq_DAQ.py'
            log = 'rad_gui.log'
            if self.saveData:
                fname = fname + "_D3S.csv"
        if sensor==CO2:
            py = 'python'
            script = 'adc_DAQ.py'
            log = 'CO2_gui.log'
            if self.saveData:
                fname = fname + "_CO2.csv"

        cmd_head = '{} /home/pi/dosenet-raspberrypi/{}'.format(py, script)
        cmd_options = ' -i {}'.format(self.integration_time)
        if self.saveData:
            cmd_options = cmd_options + ' -d {}'.format(fname)
        cmd_log = ' > /tmp/{} 2>&1 &'.format(log)
        cmd = cmd_head + cmd_options + cmd_log

        print(cmd)
        os.system(cmd)

    def sensorButtonState(self,b):
        if b.isChecked() == True:
            print("{} is selected".format(b.text()))
            self.addSensor(b.text())
        else:
            print("{} is deselected".format(b.text()))
            self.rmvSensorTab(b.text())

    def setDisplayText(self, sensor):
        full_text = ' '.join(str(r) for r in self.sensor_list[sensor])
        self.data_display[sensor].setText(full_text)

    def searchData(self, found, location, data_type, loc, month, year):
        found.clear()
        for file in os.listdir(location):
            if fnmatch.fnmatch(file, loc + "*" + year + "*" + month + "-*" + data_type + ".csv"):
                found.addItem(file)
        if found.count() == 0:
            found.addItem("no files found")

    def addFile(self, file, comp):
        if comp.count() > 0:
            for i in range(comp.count()):
                if comp.item(i).text() == file:
                    b = True
                else:
                    b = False
        else:
            b = False

        if b == False:
            comp.addItem(file)

    def displayPM(self, comp):
        if comp.count() > 0 and self.getDataType(comp.item(0)) == "AQ":
            self.pm1.show()
            self.pm25.show()
            self.pm10.show()
            self.select_pm.show()
        else:
            self.pm1.hide()
            self.pm25.hide()
            self.pm10.hide()
            self.select_pm.hide()
    
    def getDataType(self, file):
        dt = file.text()[len(file.text()) - 6:len(file.text()) - 4]

        if dt == "O2":
            dt = "CO2"
        elif dt == "3S":
            dt = "D3S"
        else:
            dt = "AQ"

        return dt
                  
    def compData(self, comp, dt):
        s = True
        f = True

        if comp.count() > 0:
            for i in range(comp.count()):
                if self.getDataType(comp.item(i)) != dt:
                    s = False
        else:
            f = False

        if s == False:
            self.cant_comp = QMessageBox.about(self, "Can't compare data",
                                               "Please select files of the same data type")
        elif f == False:
            self.no_files = QMessageBox.about(self, "Can't compare data",
                                              "No files selected")
        else:
            if dt == "CO2":
                self.plotCO2(comp)
            elif dt == "AQ":
                self.plotAQ(comp)
            #else:
                #self.plotRAD(comp)
        
    def plotCO2(self, datasets):

        plt.title("Carbon Dioxide")
        plt.xlabel("date and time")
        plt.ylabel("carbon dioxide (parts per million)")

        for i in range(datasets.count()):
            with open(r'/Users/vaughnluthringer/Desktop/dosenet/newdata/' +
                      datasets.item(i).text()) as csv_file:
                ds = pd.read_csv(csv_file, delimiter = ",")
                
                datetime = ds.loc[:, "Date and Time"]
                co2 = ds.loc[:, "CO2 (ppm)"]

                plt.plot(datetime, co2)

        return plt.show()

    def plotAQ(self, datasets):

        plt.title("Air Quality")
        plt.xlabel("time")
        plt.ylabel("µg/m^3")

        for i in range(datasets.count()):
            with open(r'/Users/vaughnluthringer/Desktop/dosenet/newdata/' +
                      datasets.item(i).text()) as csv_file:
                ds = pd.read_csv(csv_file, delimiter = ",")

                time = ds.loc[:, "Time"]
                pm1 = ds.loc[:, 'PM 1.0']
                pm25 = ds.loc[:, 'PM 2.5']
                pm10 = ds.loc[:, 'PM 10']

                plt.plot(time, pm1)
                plt.plot(time, pm25)
                plt.plot(time, pm10)

        return plt.show()
        
    def setCompTab(self):
        self.comp_tab = QWidget()
        self.tabs.addTab(self.comp_tab, "Compare")
        self.comp_layout = QGridLayout()
        self.comp_layout.setContentsMargins(30.,50.,30.,20.)

        data_text1 = QLabel("I want to find ")
        textfont = QFont("Helvetica Neue", 12) 
        data_text1.setFont(textfont)
        data_text1.setAlignment(Qt.AlignLeft)
        self.comp_layout.addWidget(data_text1, 0, 0)
        data_text2 = QLabel(" data taken ")
        data_text2.setFont(textfont)
        data_text2.setAlignment(Qt.AlignLeft)
        self.comp_layout.addWidget(data_text2, 0, 2)
        data_text3 = QLabel(" in ")
        data_text3.setFont(textfont)
        data_text3.setAlignment(Qt.AlignLeft)
        self.comp_layout.addWidget(data_text3, 0, 4)

        data_types = {"air quality": "AQ", "radiation": "D3S", "carbon dioxide": "CO2"}
        months = {"January": 1, "February": 2, "February": 3, "April": 4,
                  "May": 5, "June": 6, "July": 7, "August": 8,
                  "September": 9, "October": 10, "November": 11,
                  "December": 12}
        years = ["2011", "2012", "2013", "2014", "2015", "2016", "2017",
                 "2018", "2019"]
        locs = ["Inside", "Outside"]

        types_box = QComboBox()
        self.comp_layout.addWidget(types_box, 0, 1)
        types_box.addItems(data_types.keys())
        types_box.setCurrentIndex(0)

        loc_box = QComboBox()
        self.comp_layout.addWidget(loc_box, 0, 3)
        loc_box.addItems(locs)
        loc_box.setCurrentIndex(0)

        months_box = QComboBox()
        self.comp_layout.addWidget(months_box, 0, 5)
        months_box.addItems(months.keys())
        types_box.setCurrentIndex(0)

        years_box = QComboBox()
        self.comp_layout.addWidget(years_box, 0, 6)
        years_box.addItems(years)
        years_box.setCurrentIndex(0)

        self.pm_layout = QGridLayout()
        self.comp_layout.addLayout(self.pm_layout, 4, 7)

        self.pm1 = QRadioButton("PM 1.0")
        self.pm1.setChecked(True)
        self.pm_layout.addWidget(self.pm1, 1, 0)
        self.pm1.hide()

        self.pm25 = QRadioButton("PM 2.5")
        self.pm_layout.addWidget(self.pm25, 2, 0)
        self.pm25.hide()

        self.pm10 = QRadioButton("PM 10")
        self.pm_layout.addWidget(self.pm10, 3, 0)
        self.pm10.hide()

        self.select_pm = QLabel("Select a\nparticle size:")
        self.pm_layout.addWidget(self.select_pm, 0, 0)
        self.select_pm.hide()

        #textfont = QFont("Helvetica Neue", 18)
        found_text = QLabel("Found files:")
        comp_text = QLabel("Compare:")
        howto_text = QLabel("Double-click items move/remove them")

        #found_text.setFont(textfont)
        #found_text.setFont(textfont)
        #howto_text.setFont(textfont)

        comp_files = QListWidget()
        found_files = QListWidget()

        self.comp_layout.addWidget(found_text, 2, 0)
        self.comp_layout.addWidget(found_files, 3, 0, 2, 2)

        self.comp_layout.addWidget(comp_text, 2, 3)
        self.comp_layout.addWidget(comp_files, 3, 3, 2, 3)

        self.comp_layout.addWidget(howto_text, 5, 0)

        go_button = QPushButton("Go")
        self.comp_layout.addWidget(go_button, 0, 7)
        go_button_style = "background-color: #39c43e"
        go_button.setStyleSheet(go_button_style)
        #pathway only applicable on Vaughn's laptop!!!
        go_button.clicked.connect(lambda:self.searchData(found_files,
                                                '/Users/vaughnluthringer/Desktop/dosenet/newdata/',
                                                 data_types[types_box.currentText()], loc_box.currentText(),
                                                 str(months[months_box.currentText()]).zfill(2),
                                                     str(years_box.currentText())))

        comp_button = QPushButton("Compare")
        self.comp_layout.addWidget(comp_button, 2, 7)
        comp_button_style = "background-color: #D3D3D3"
        comp_button.setStyleSheet(comp_button_style)
        comp_button.clicked.connect(lambda:self.compData(comp_files,
                                                         data_types[types_box.currentText()]))


        found_files.itemDoubleClicked.connect(
            lambda:self.addFile(found_files.currentItem().text(), comp_files))
        found_files.itemDoubleClicked.connect(lambda: self.displayPM(comp_files))

        comp_files.itemDoubleClicked.connect(
            lambda:comp_files.takeItem(comp_files.currentRow()))
        comp_files.itemDoubleClicked.connect(lambda: self.displayPM(comp_files))

        self.comp_tab.setLayout(self.comp_layout)

    def setSelectionTab(self):
        '''
        Fill out the tab providing all of the user input
            - user inputs include parameters for data acquisition
            - option to save data with user info for setting a unique file-name
        '''
        self.selection_tab = QWidget()
        self.tabs.addTab(self.selection_tab, "Configure")
        self.config_layout = QGridLayout() #QVBoxLayout() #QFormLayout()

        self.spaceItem = QSpacerItem(150,10,QSizePolicy.Expanding)
        self.config_layout.addItem(self.spaceItem, 1,2) #QSpacerItem(1,1)

        self.config_layout.setContentsMargins(30.,50.,30.,20.)
        integration_text = QLabel("Integration time (seconds):")
        textfont = QFont("Helvetica Neue", 18)
        integration_text.setFont(textfont)
        integration_text.setAlignment(Qt.AlignLeft)
        self.config_layout.addWidget(integration_text, 0,0) #1 
        integration_box = QComboBox()
        self.config_layout.addWidget(integration_box, 0,1) #2
        item_list = ["1","2","3","4","5","10","15","20","30","60","120","300"]
        self.integration_time = 2
        integration_box.addItems(item_list)
        integration_box.setCurrentIndex(1)
        integration_box.currentIndexChanged.connect(
            lambda:self.setIntegrationTime(str(integration_box.currentText())))
        #self.config_layout.addRow(integration_text,integration_box)

        ndata_text = QLabel("Data points to display:")
        ndata_text.setFont(textfont)
        ndata_text.setAlignment(Qt.AlignLeft)
        self.config_layout.addWidget(ndata_text, 1,0) #3
        ndata_box = QComboBox()
        self.config_layout.addWidget(ndata_box, 1,1) #4
        item_list = ["5","10","15","20","25","30","40","50","60"]
        self.ndata = 25
        ndata_box.addItems(item_list)
        ndata_box.setCurrentIndex(4)
        ndata_box.currentIndexChanged.connect(
                lambda:self.setNData(str(ndata_box.currentText())))
        #self.config_layout.addRow(ndata_text,ndata_box)

        checkbox = QCheckBox("Save data?")
        checkbox.setFont(QFont("Helvetica Neue", 18))
        checkbox.setChecked(False)
        checkbox.stateChanged.connect(lambda:self.setSaveData(checkbox))
        self.config_layout.addWidget(checkbox, 2, 0) #5 

        #self.group_text = QLabel("Group number:")
        #self.group_text.setFont(textfont)
        #self.group_text.setAlignment(Qt.AlignCenter)
        #self.group_box = QComboBox()
        #item_list = ["1","2","3","4","5","6","7","8","9","10"]
        #self.group_id = "1"
        #self.group_box.addItems(item_list)
        #self.group_box.currentIndexChanged.connect(
                #lambda:self.setGroupID(str(self.group_box.currentText())))
        #self.config_layout.addRow(self.group_text,self.group_box)
        #self.config_layout.addWidget(self.group_text, 3,0) #6
        #self.config_layout.addWidget(self.group_box, 3,1) #7  
        #self.group_text.setAlignment(Qt.AlignLeft)

        #self.ptext = QLabel("Period:")
        #self.ptext.setFont(textfont)
        #self.ptext.setAlignment(Qt.AlignCenter)
        #self.pbox = QComboBox()
        #item_list = ["1","2","3","4","5","6","7","8"]
        #self.period_id = "1"
        #self.pbox.addItems(item_list)
        #self.pbox.currentIndexChanged.connect(
                #lambda:self.setPeriodID(str(self.pbox.currentText())))
        #self.config_layout.addRow(self.ptext,self.pbox)
        #self.config_layout.addWidget(self.ptext, 4,0) #8 
        #self.config_layout.addWidget(self.pbox, 4,1) #9
        #self.ptext.setAlignment(Qt.AlignLeft) #extra
        #self.config6.addWidget(self.ptext)

        self.location_text = QLabel("Taking data inside or outside?")
        self.location_text.setFont(textfont)
        self.location_text.setAlignment(Qt.AlignCenter)
        self.location_box = QComboBox()
        item_list = ["Inside","Outside"]
        self.location = "Inside"
        self.location_box.addItems(item_list)
        #self.config_layout.addRow(self.location_text,self.location_box)
        self.config_layout.addWidget(self.location_text, 4,0) #10
        self.config_layout.addWidget(self.location_box, 4,1) #11
        self.location_text.setAlignment(Qt.AlignLeft)
        self.location_box.currentIndexChanged.connect(
            lambda:self.setFilename(str(self.location_box.currentText()),
                                        str(self.namebox.text())))

        self.sensorLabel = QLabel("Select sensors:")
        headerfont = QFont("Helvetica Neue", 18, QFont.Bold)
        self.sensorLabel.setFont(headerfont)
        self.config_layout.addWidget(self.sensorLabel, 0, 4) 


        self.nametext = QLabel("File name: ")
        self.nametext.setFont(textfont)
        self.config_layout.addWidget(self.nametext, 5, 0)

        self.notename = QLabel("(no need to include inside/outside, data type," +
                               " or date in file name)")
        self.config_layout.addWidget(self.notename, 6, 0)
        
        self.namebox = QLineEdit()
        self.config_layout.addWidget(self.namebox, 5,1)
        self.namebox.textChanged.connect(
            lambda:self.setFilename(str(self.location_box.currentText()),
                                        str(self.namebox.text())))

        self.selection_tab.setLayout(self.config_layout)
        #self.group_text.close()
        #self.group_box.close()
        #self.ptext.close()
        #self.pbox.close()
        self.namebox.close()
        self.nametext.close()
        self.notename.close()
        self.location_text.close()
        self.location_box.close()

    def setSaveData(self,b):
        if b.isChecked() == True:
            print("Saving sensor data")
            self.saveData = True
            #self.group_text.show()
            #self.group_box.show()
            #self.ptext.show()
            #self.pbox.show()
            self.location_text.show()
            self.location_box.show()
            self.namebox.show()
            self.nametext.show()
            self.notename.show()
        else:
            self.saveData = False
            #self.group_text.close()
            #self.group_box.close()
            #self.ptext.close()
            #self.pbox.close()
            self.location_text.close()
            self.location_box.close()
            self.namebox.close()
            self.nametext.close()
            self.notename.close()


    def setIntegrationTime(self,text):
        self.integration_time = int(text)


    def setNData(self,text):
        self.ndata = int(text)


    #def setGroupID(self,text):
        #self.group_id = text
        #self.setFilename()


    #def setPeriodID(self,text):
        #self.period_id = text
        #self.setFilename()


    #def setLocation(self,text):
        #self.location = text
        #self.setFilename()


    def setFilename(self, loc, name):
        self.file_name = loc + "_" + name


    #def setFilename(self):
        #self.file_prefix = '{}_p{}_g{}'.format(self.location,
                                               #self.period_id,
                                               #self.group_id)
        #self.textbox.setText(self.file_prefix)


    def addSensor(self, sensor):
        self.initSensorData(sensor)
        self.setSensorTab(sensor)
        self.setSensorText(sensor)
        if not self.test_mode:
            self.startSensor(sensor)

    def setSensorTab(self, sensor):
        '''
        Setup the tab and layout for the selected sensor, initialize plots, etc.
        '''
        # Create canvas for plots
        if sensor in self.sensor_tab:
            self.tabs.insertTab(self.sensor_tab[sensor][0],
                                self.sensor_tab[sensor][1],sensor)
            return
        itab = QWidget()
        index = self.tabs.addTab(itab, sensor)
        self.sensor_tab[sensor] = [index,itab]
        tablayout = QGridLayout()
        tablayout.setSpacing(0.)
        tablayout.setContentsMargins(0.,0.,0.,0.)

        # Create value display
        self.data_display[sensor] = QLabel("")
        textfont = QFont("Helvetica Neue", 18, QFont.Bold)
        self.data_display[sensor].setFont(textfont)
        self.data_display[sensor].setStyleSheet(good_background)
        self.data_display[sensor].setAlignment(Qt.AlignCenter)
        tablayout.addWidget(self.data_display[sensor],0,2,1,4)
        tablayout.setRowStretch(0,2)

        self.setPlots(sensor,tablayout)
        itab.setLayout(tablayout)


    def setPlots(self,sensor,layout):
        '''
        Set the initial plot layout, initialize plot curves, error bars, etc.
        '''
        if sensor==RAD:
            global proxy
            splotwin = pg.GraphicsWindow()
            splotwin.setContentsMargins(0,0,0,0)
            self.cursor_label = pg.LabelItem(justify='right')
            splotwin.addItem(self.cursor_label)
            self.splot = splotwin.addPlot(
                            #title="<h2> {} Data </h2>".format(sensor),
                            row=1, col=0)
            self.splot.showGrid(x=True, y=True)
            self.splot.setLabel('left', '<h3>Counts/Energy [1/keV]</h3>')
            self.splot.setLabel('bottom', '<h3>Energy [keV]</h3>')
            curve1 = self.splot.plot(self.channels, self.data[sensor],
                                pen=(255, 0, 0))
            self.splot.setLogMode(False,True)
            #cross hair
            self.splot.addItem(vLine, ignoreBounds=True)
            self.splot.addItem(hLine, ignoreBounds=True)
            proxy = pg.SignalProxy(self.splot.scene().sigMouseMoved,
                                   rateLimit=60,
                                   slot=mouseMoved)
            tplotwin = pg.GraphicsWindow()
            tplotwin.setContentsMargins(0,0,0,0)
            tplot = tplotwin.addPlot()
            tplot.showGrid(x=True, y=True)
            tplot.setLabel('left', '<h3>CPS</h3>')
            tplot.setLabel('bottom', '<h3>Time</h3>')
            err = pg.ErrorBarItem(x=self.time_data[sensor],
								  y=self.ave_data[0],
                                  height=np.asarray(self.ave_data[1]))
            tplot.addItem(err)
            curve2 = tplot.plot(symbolBrush=(255,0,0), symbolPen='k',
                                pen=(255, 0, 0))
            self.plot_list[sensor] = [curve1,curve2]
            self.err_list[sensor] = err
            layout.addWidget(splotwin,1,0,1,8)
            layout.setRowStretch(1,15)
            layout.addWidget(tplotwin,2,0,1,8)
            layout.setRowStretch(2,5)

        if sensor==AIR:
            plotwin = pg.GraphicsWindow()
            plotwin.setContentsMargins(0,0,0,0)
            iplot = plotwin.addPlot()
            iplot.showGrid(x=True, y=True)
            legend = pg.LegendItem(size=(110,90), offset=(100,10))
            legend.setParentItem(iplot)
            iplot.setLabel('left', '<h2>Particulate Concentration</h2>')
            iplot.setLabel('bottom', '<h2>Time</h2>')
            colors = [(255,0,0),(0,255,0),(0,0,255)]
            names = ['<h4>PM 1.0</h4>',
                     '<h4>PM 2.5</h4>',
                     '<h4>PM 10</h4>']

            self.plot_list[sensor] = []
            self.err_list[sensor] = []
            for idx in range(len(self.data[sensor])):
                err = pg.ErrorBarItem(x=self.time_data[sensor],
									  y=self.data[sensor][idx][0],
									  height=np.asarray(
                                                self.data[sensor][idx][1]))
                iplot.addItem(err)
                curve = iplot.plot(self.time_data[sensor],
                                   self.data[sensor][idx][0],
                                   symbolBrush=colors[idx], symbolPen='k',
                                   pen=colors[idx], name=names[idx])
                self.err_list[sensor].append(err)
                self.plot_list[sensor].append(curve)
                legend.addItem(curve,names[idx])
            layout.addWidget(plotwin,1,0,1,8)
            layout.setRowStretch(1,15)

        if sensor==CO2:
            plotwin = pg.GraphicsWindow()
            plotwin.setContentsMargins(0,0,0,0)
            iplot = plotwin.addPlot()
            iplot.showGrid(x=True, y=True)
            iplot.setLabel('left','<h2>CO<sub>2</sub> Concentration (ppm)</h2>')
            iplot.setLabel('bottom','<h2>Time</h2>')
            err = pg.ErrorBarItem(x=self.time_data[sensor],
                                  y=self.data[sensor][0],
                                  height=np.asarray(self.data[sensor][1]))
            iplot.addItem(err)
            curve = iplot.plot(symbolBrush=(255,0,0), symbolPen='k',
                               pen=(255,0,0))
            self.plot_list[sensor] = curve
            self.err_list[sensor] = err
            layout.addWidget(plotwin,1,0,1,8)
            layout.setRowStretch(1,15)


    def setSensorText(self, sensor):
        '''
        Set initial text/display above data graphs for the sensor
        '''
        if sensor==RAD:
            cps = "{:.1f}".format(np.mean(self.data[sensor]))
            usv = "{:.3f}".format(np.mean(self.data[sensor]))
            sensor_text = ["CPS =",cps,"                  uSv/hr =",usv]
            self.sensor_list[sensor] = sensor_text

        if sensor==AIR:
            if len(self.data[sensor][0]) == 0:
                pm1, pm25, pm10 = 0., 0., 0.
            else:
                pm1 = "{:.1f}".format(np.mean(self.data[sensor][0]))
                pm25 = "{:.1f}".format(np.mean(self.data[sensor][1]))
                pm10 = "{:.1f}".format(np.mean(self.data[sensor][2]))
            sensor_text = ["PM 1.0 =",pm1,
                           "ug/L     PM 2.5 =",pm25,
                           "ug/L     PM 10 =",pm10,"ug/L"]
            self.sensor_list[sensor] = sensor_text

        if sensor==CO2:
            ppm = "{:.1f}".format(np.mean(self.data[sensor]))
            sensor_text = ["PPM =",ppm]
            self.sensor_list[sensor] = sensor_text

        self.setDisplayText(sensor)


    def initSensorData(self,sensor):
        '''
        Initialize the relevant sensor data lists
        '''
        self.time_data[sensor] = []
        if sensor==RAD:
            self.data[sensor] = np.ones(self.nbins, dtype=float)
            self.spectra = []
            self.ave_data = [[],[]]

        if sensor==AIR:
            self.data[sensor] = [[[],[]],[[],[]],[[],[]]]

        if sensor==CO2:
            self.data[sensor] = [[],[]]


    def makeTestData(self,sensor):
        '''
        Make dummy data for testing
        '''
        if sensor==RAD:
            data = np.random.random(self.nbins)
        if sensor==AIR:
            base_data = np.random.random(1)[0]
            base_err = 0.05*np.random.random(3)
            data = [[base_data,base_err[0]],
                    [base_data*1.5,base_err[1]],
                    [base_data*5.0,base_err[2]]]
        if sensor==CO2:
            data = [np.random.random(1)[0],0.05*np.random.random(1)[0]]
        return data


    def addData(self, sensor, data):
        '''
        Add newest data from the sensor to data lists
        '''
        # For robustness: make sure start_time is defined
        #  - if it's not restart the time count here
        if self.start_time is None:
            self.start_time = float(format(float(time.time()), '.2f'))
        itime = float(format(float(time.time()), '.2f')) - self.start_time
        self.time_data[sensor].append(itime)
        if len(self.time_data[sensor]) > self.ndata:
            self.time_data[sensor].pop(0)

        if sensor==RAD:
            data = np.asarray(data).reshape(self.nbins,int(len(data)/self.nbins)).sum(axis=1)
            self.spectra.append(data)
            self.data[sensor] += data
            cps = np.sum(data)/float(self.integration_time)
            err = np.sqrt(np.sum(data))/float(self.integration_time)
            self.ave_data[0].append(cps)
            self.ave_data[1].append(err)
            if len(self.ave_data[0]) > self.ndata:
                self.spectra.pop(0)
                self.ave_data[0].pop(0)
                self.ave_data[1].pop(0)

        if sensor==AIR:
            self.data[AIR][0][0].append(data[0][0])
            self.data[AIR][0][1].append(data[0][1])
            self.data[AIR][1][0].append(data[1][0])
            self.data[AIR][1][1].append(data[1][1])
            self.data[AIR][2][0].append(data[2][0])
            self.data[AIR][2][1].append(data[2][1])

            if len(self.data[sensor][0][0]) > self.ndata:
                self.data[sensor][0][0].pop(0)
                self.data[sensor][0][1].pop(0)
                self.data[sensor][1][0].pop(0)
                self.data[sensor][1][1].pop(0)
                self.data[sensor][2][0].pop(0)
                self.data[sensor][2][1].pop(0)

        if sensor==CO2:
            self.data[CO2][0].append(data[0])
            self.data[CO2][1].append(data[1])

            if len(self.data[sensor][0]) > self.ndata:
                self.data[sensor][0].pop(0)
                self.data[sensor][1].pop(0)

    def updatePlot(self, sensor):
        '''
        Update plots with newest data from the sensor
        '''
        if sensor==RAD:
            self.plot_list[sensor][0].setData(self.channels,
                                              np.asarray(self.data[sensor]))

            self.err_list[sensor].setData(x=np.asarray(self.time_data[sensor]),
                                          y=np.asarray(self.ave_data[0]),
                                          height=np.asarray(self.ave_data[1]),
                                          beam=0.15)
            self.plot_list[sensor][1].setData(self.time_data[sensor],
                                              self.ave_data[0])

        if sensor==AIR:
            self.err_list[sensor][0].setData(x=np.asarray(self.time_data[sensor]),
                                             y=np.asarray(self.data[sensor][0][0]),
                                             height=np.asarray(self.data[sensor][0][1]),
                                             beam=0.15)
            self.plot_list[sensor][0].setData(self.time_data[sensor],
                                              self.data[sensor][0][0])
            self.err_list[sensor][1].setData(x=np.asarray(self.time_data[sensor]),
                                             y=np.asarray(self.data[sensor][1][0]),
                                             height=np.asarray(self.data[sensor][1][1]),
                                             beam=0.15)
            self.plot_list[sensor][1].setData(self.time_data[sensor],
                                              self.data[sensor][1][0])
            self.err_list[sensor][2].setData(x=np.asarray(self.time_data[sensor]),
                                             y=np.asarray(self.data[sensor][2][0]),
                                             height=np.asarray(self.data[sensor][2][1]),
                                             beam=0.15)
            self.plot_list[sensor][2].setData(self.time_data[sensor],
                                              self.data[sensor][2][0])

        if sensor==CO2:
            self.err_list[sensor].setData(x=np.asarray(self.time_data[sensor]),
                                          y=np.asarray(self.data[sensor][0]),
                                          height=np.asarray(self.data[sensor][1]),
                                          beam=0.15)
            self.plot_list[sensor].setData(self.time_data[sensor],
                                           self.data[sensor][0])

        self.updateText(sensor)


    def updateText(self, sensor):
        '''
        Determine new values for text above the graph and update the display
        '''
        if sensor==RAD:
            if len(self.ave_data[0]) > 0:
                cps = self.ave_data[0][-1]
            else:
                cps = np.mean(self.data[sensor])
            usv = cps * 0.0000427*60
            cps_str = "{:.1f}".format(cps)
            usv_str = "{:.3f}".format(usv)
            self.sensor_list[sensor][1] = cps_str
            self.sensor_list[sensor][3] = usv_str
            self.setDisplayBackground(sensor,usv)

        if sensor==AIR:
            if len(self.data[sensor][0][0]) > 0:
                pm1 = "{:.1f}".format(self.data[sensor][0][0][-1])
                pm25 = "{:.1f}".format(self.data[sensor][1][0][-1])
                pm10 = "{:.1f}".format(self.data[sensor][2][0][-1])
            else:
                pm1 = "0.0"
                pm25 = "0.0"
                pm10 = "0.0"
            self.sensor_list[sensor][1] = pm1
            self.sensor_list[sensor][3] = pm25
            self.sensor_list[sensor][5] = pm10
            self.setDisplayBackground(sensor,np.mean(self.data[sensor][1][0]))

        if sensor==CO2:
            if len(self.data[sensor][0]) > 0:
                ppm = "{:.1f}".format(self.data[sensor][0][-1])
            else:
                ppm = "0.0"
            self.sensor_list[sensor][1] = ppm
            self.setDisplayBackground(sensor,np.mean(self.data[sensor][0]))

        self.setDisplayText(sensor)

    def setDisplayBackground(self, sensor, val):
        '''
        Sets background color according to newest reading(val) from the sensor
        '''
        if sensor==RAD:
            if val < 1.0:
                self.data_display[sensor].setStyleSheet(good_background)
            elif val < 2.0:
                self.data_display[sensor].setStyleSheet(okay_background)
            elif val < 25.0:
                self.data_display[sensor].setStyleSheet(med_background)
            elif val < 200.0:
                self.data_display[sensor].setStyleSheet(bad_background)
            else:
                self.data_display[sensor].setStyleSheet(verybad_background)
        if sensor==AIR:
            if val < 12.1:
                self.data_display[sensor].setStyleSheet(good_background)
            elif val < 35.5:
                self.data_display[sensor].setStyleSheet(okay_background)
            elif val < 55.5:
                self.data_display[sensor].setStyleSheet(med_background)
            elif val < 150.5:
                self.data_display[sensor].setStyleSheet(bad_background)
            else:
                self.data_display[sensor].setStyleSheet(verybad_background)
        if sensor==CO2:
            if val < 1000:
                self.data_display[sensor].setStyleSheet(good_background)
            elif val < 2000:
                self.data_display[sensor].setStyleSheet(okay_background)
            elif val < 5000:
                self.data_display[sensor].setStyleSheet(med_background)
            elif val < 40000:
                self.data_display[sensor].setStyleSheet(bad_background)
            else:
                self.data_display[sensor].setStyleSheet(verybad_background)


    @pyqtSlot()
    def updatePlots(self):
        if self.test_mode:
            for sensor in self.sensor_list:
                data = self.makeTestData(sensor)
                self.addData(sensor,data)
                self.updatePlot(sensor)
        else:
            message = receive_queue_data()
            while message is not None:
                self.addData(message['id'],message['data'])
                self.updatePlot(message['id'])
                message = receive_queue_data()

    @pyqtSlot()
    def run(self, button):
        button.setEnabled(False)
        self.selection_tab.setEnabled(False)
        time_sample = 50
        if self.test_mode:
            time_sample = 1000*self.integration_time
        print("Starting data collection")
        # Only set start time the first time user clicks start
        if self.start_time is None:
            self.start_time = float(format(float(time.time()), '.2f'))
        if not self.test_mode:
            send_queue_cmd('START',self.sensor_list)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updatePlots)
        self.timer.start(time_sample)

    @pyqtSlot()
    def stop(self, stop, clear):
        '''
        Send STOP command to all sensors
            - functionally a pause in displaying/recording data
        '''
        stop.setEnabled(False)
        clear.setEnabled(False)
        if not self.test_mode:
            send_queue_cmd('STOP',self.sensor_list)
        self.timer.stop()
        stopmsg = QMessageBox()
        stopmsg.setIcon(QMessageBox.Information)
        stopmsg.setText('Data collection stopped')
        if self.saveData:
            stopmsg.setInformativeText('Data saved')
        stopmsg.setWindowTitle('Stop')
        stopmsg.setStandardButtons(QMessageBox.Ok)
        retval = stopmsg.exec_()
 
    @pyqtSlot()
    def clear(self):
        '''
        Send STOP command to all sensors and clear current data
        '''
        # TODO: Automaticaly save data to file here and/or add 'Save' button?
        #    - maybe produce a pop-up prompting user to chose to save or not
        try:
            if not self.test_mode:
                send_queue_cmd('STOP',self.sensor_list)
            self.start_time = None
            for sensor in self.sensor_list:
                self.time_data[sensor][:] = []
                if sensor==RAD:
                    self.spectra[:] = []
                    self.data[sensor] = np.ones(self.nbins, dtype=float)
                    self.ave_data = [[],[]]
                if sensor==AIR:
                    self.data[sensor] = [[[],[]],[[],[]],[[],[]]]
                if sensor==CO2:
                    self.data[sensor] = [[],[]]
                self.updatePlot(sensor)
        except:
            if not arg_dict['test']:
                send_queue_cmd('EXIT',[RAD,AIR,CO2,PTH])
            # Still want to see traceback for debugging
            print('ERROR: GUI quit unexpectedly!')
            traceback.print_exc()

    def kill_sensor(self, sensor):
        send_queue_cmd('EXIT',sensor)

    def exit(self):
        '''
        Send EXIT command to all sensors
        '''
        print("Exiting GUI")
        if not self.test_mode:
            print("Sending EXIT command to all active sensors")
            send_queue_cmd('EXIT',self.sensor_list)
            time.sleep(2)



#-------------------------------------------------------------------------------
# Methods for communication with the shared queue
#   - allows commmunication between GUI and sensor DAQs
#   - send commands and receive sensor data
#-------------------------------------------------------------------------------
def send_queue_cmd(cmd, daq_list):
    '''
    Send commands for sensor DAQs
        - valid commands: START, STOP, EXIT
    '''
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='fromGUI')
    for sensor in daq_list:
        print("Sending cmd: {} for {}".format(cmd,sensor))
        message = {'id': sensor, 'cmd': cmd}
        channel.basic_publish(exchange='',
                              routing_key='fromGUI',
                              body=json.dumps(message))
    connection.close()

def receive_queue_data():
    '''
    Receive data from sensor DAQs
    '''
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='toGUI')
    method_frame, header_frame, body = channel.basic_get(queue='toGUI')
    if body is not None:
        if type(body) is bytes:
            body = body.decode("utf-8")
        message = json.loads(body)
        channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        connection.close()
        return message
    else:
        connection.close()
        return None

def clear_queue():
    print("Initializing queues... clearing out old data")
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='toGUI')
    channel.queue_delete(queue='toGUI')
    connection.close()

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='fromGUI')
    channel.queue_delete(queue='fromGUI')
    connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test", "-t",
        action='store_true',
        default=False,
    )
    parser.add_argument(
        "--windows", "-w",
        action = 'store_true',
        default = False,
    )


    args = parser.parse_args()
    arg_dict = vars(args)

    global ex
    # Wrap everything in try/except so that sensor DAQs can be shutdown cleanly
    try:
        if not arg_dict['test']:
            clear_queue()
        app = QApplication(sys.argv)
        QApplication.setStyle(QStyleFactory.create("Cleanlooks"))
        nbins = 1024
        ex = App(nbins=nbins, **arg_dict)
        ex.show()

        atexit.register(ex.exit)
    except:
        if not arg_dict['test']:
            send_queue_cmd('EXIT',[RAD,AIR,CO2,PTH])
        # Still want to see traceback for debugging
        print('ERROR: GUI quit unexpectedly!')
        traceback.print_exc()
        pass

    ret = app.exec_()
    print(ret)
    sys.exit(ret)
