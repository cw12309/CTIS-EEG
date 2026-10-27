
import sys
import time
import serial
import string
import binascii
import pyqtgraph as pg
import array
import threading
import numpy as np
from queue import Queue 
i = 0
#建立列表
Delta_P     = Queue(maxsize=0)
Theta_P     = Queue(maxsize=0)
LowAlpha_P  = Queue(maxsize=0)
HighAlpha_P = Queue(maxsize=0)
LowBeta_P   = Queue(maxsize=0)
HighBeta_P  = Queue(maxsize=0)
LowGamma_P  = Queue(maxsize=0)
MiddleGamma_P = Queue(maxsize=0)
Attention_P = Queue(maxsize=0)
Meditation_P = Queue(maxsize=0)

#串口读取
def Serial():
    global i 
    global Delta_P,Theta_P,LowAlpha_P,HighAlpha_P,LowBeta_P,HighBeta_P,LowGamma_P,MiddleGamma_P,Attention_P,Meditation_P
    while(True):
        if mSerial.inWaiting() > 0:
            b = mSerial.read(1)
            if b.hex() == 'aa':
                b = mSerial.read(1)
                if b.hex() == 'aa':
                    data = mSerial.read(34)
                    Delta       = data[6]*256+data[7]
                    Theta       = data[9]*256+data[10]
                    LowAlpha    = data[12]*256+data[13]
                    HighAlpha   = data[15]*256+data[16]
                    LowBeta     = data[18]*256+data[19]
                    HighBeta    = data[21]*256+data[22]
                    LowGamma    = data[24]*256+data[25]
                    MiddleGamma = data[27]*256+data[28]
                    Attention   = data[30]
                    Meditation  = data[32] 
                    Delta_P.put(Delta)
                    Theta_P.put(Theta)
                    LowAlpha_P.put(LowAlpha)
                    HighAlpha_P.put(HighAlpha)
                    LowBeta_P.put(LowBeta)
                    HighBeta_P.put(HighBeta)
                    LowGamma_P.put(LowGamma)
                    MiddleGamma_P.put(MiddleGamma)
                    Attention_P.put(Attention)
                    Meditation_P.put(Meditation)

                    
                    #绘图
def plotData():
    global i 
    global Delta_P,Theta_P,LowAlpha_P,HighAlpha_P,LowBeta_P,HighBeta_P,LowGamma_P,MiddleGamma_P,Attention_P,Meditation_P
    if i < historyLength:
        Delta_data[i] = Delta_P.get()
        Theta_data[i] = Theta_P.get()
        LowAlpha_data[i] = LowAlpha_P.get()
        HighAlpha_data[i] = HighAlpha_P.get()
        LowBeta_data[i] = LowBeta_P.get()
        HighBeta_data[i] = HighBeta_P.get()
        LowGamma_data[i] = LowGamma_P.get()
        MiddleGamma_data[i] = MiddleGamma_P.get()
        Attention_data[i] = Attention_P.get()
        Meditation_data[i] = Meditation_P.get()
        i = i+1
    else:
        Delta_data[:-1] = Delta_data[1:]
        Delta_data[i-1] = Delta_P.get()
        Theta_data[:-1] = Theta_data[1:]
        Theta_data[i-1] = Theta_P.get()
        LowAlpha_data[:-1] = LowAlpha_data[1:]
        LowAlpha_data[i-1] = LowAlpha_P.get()
        HighAlpha_data[:-1] = HighAlpha_data[1:]
        HighAlpha_data[i-1] = HighAlpha_P.get()
        LowBeta_data[:-1] = LowBeta_data[1:]
        LowBeta_data[i-1] = LowBeta_P.get()
        HighBeta_data[:-1] = HighBeta_data[1:]
        HighBeta_data[i-1] = HighBeta_P.get()
        LowGamma_data[:-1] = LowGamma_data[1:]
        LowGamma_data[i-1] = LowGamma_P.get()
        MiddleGamma_data[:-1] = MiddleGamma_data[1:]
        MiddleGamma_data[i-1] = MiddleGamma_P.get()
        Attention_data[:-1] = Attention_data[1:]
        Attention_data[i-1] = Attention_P.get()
        Meditation_data[:-1] = Meditation_data[1:]
        Meditation_data[i-1] = Meditation_P.get()

    curve1.setData(Delta_data,pen = 'r')
    curve2.setData(Theta_data,pen = 'g')
    curve3.setData(LowAlpha_data,pen = 'b')
    curve4.setData(HighAlpha_data,pen = 'c')
    curve5.setData(LowBeta_data,pen = 'm')
    curve6.setData(HighBeta_data,pen = 'y')
    curve7.setData(LowGamma_data,pen = 'w')
    curve8.setData(MiddleGamma_data,pen = 'w')
    curve9.setData(Attention_data,pen = 'r')
    curve10.setData(Meditation_data,pen = 'g')


if __name__ == "__main__":
    app = pg.mkQApp()
    win = pg.GraphicsWindow()#建立一个窗口
    win.setWindowTitle(u"Sichiray金牛座脑波模块")
    win.resize(1200,800)            #窗口分辨率
    EEG1_data = array.array('i')
    historyLength = 100             #窗口数据长度
    a = 0
    Delta_data = np.zeros(historyLength).__array__('d')
    Theta_data = np.zeros(historyLength).__array__('d')
    LowAlpha_data = np.zeros(historyLength).__array__('d')
    HighAlpha_data = np.zeros(historyLength).__array__('d')
    LowBeta_data = np.zeros(historyLength).__array__('d')
    HighBeta_data = np.zeros(historyLength).__array__('d')
    LowGamma_data = np.zeros(historyLength).__array__('d')
    MiddleGamma_data = np.zeros(historyLength).__array__('d')
    Attention_data = np.zeros(historyLength).__array__('d')
    Meditation_data = np.zeros(historyLength).__array__('d')


    EEG1 = win.addPlot(left = 'y',buttom = 'x',title = "Delta")
    EEG1.setRange(xRange = [0,historyLength],padding = 0)
    curve1 = EEG1.plot()
    curve1.setData(Delta_data)
    EEG2 = win.addPlot(left = 'y',buttom = 'x',title = "Theta")
    EEG2.setRange(xRange = [0,historyLength],padding = 0)
    curve2 = EEG2.plot()
    curve2.setData(Theta_data)
    EEG3 = win.addPlot(left = 'y',buttom = 'x',title = "LowAlpha")
    EEG3.setRange(xRange = [0,historyLength],padding = 0)
    curve3 = EEG3.plot()
    curve3.setData(LowAlpha_data)
    win.nextRow()
    
    EEG4 = win.addPlot(left = 'y',buttom = 'x',title = "HighAlpha")
    EEG4.setRange(xRange = [0,historyLength],padding = 0)
    curve4 = EEG4.plot()
    curve4.setData(HighAlpha_data)
    EEG5 = win.addPlot(left = 'y',buttom = 'x',title = "LowBeta")
    EEG5.setRange(xRange = [0,historyLength],padding = 0)
    curve5 = EEG5.plot()
    curve5.setData(LowBeta_data)
    EEG6 = win.addPlot(left = 'y',buttom = 'x',title = "HighBeta")
    EEG6.setRange(xRange = [0,historyLength],padding = 0)
    curve6 = EEG6.plot()
    curve6.setData(HighBeta_data)
    win.nextRow()
    
    EEG7 = win.addPlot(left = 'y',buttom = 'x',title = "LowGamma")
    EEG7.setRange(xRange = [0,historyLength],padding = 0)
    curve7 = EEG7.plot()
    curve7.setData(LowGamma_data)
    EEG8 = win.addPlot(left = 'y',buttom = 'x',title = "MiddleGamma")
    EEG8.setRange(xRange = [0,historyLength],padding = 0)
    curve8 = EEG8.plot()
    curve8.setData(MiddleGamma_data) 
    EEG9 = win.addPlot(left = 'y',buttom = 'x',title = "Attention")
    EEG9.setRange(xRange = [0,historyLength],padding = 0)
    curve9 = EEG9.plot()
    curve9.setData(Attention_data)
    win.nextRow()
    
    EEG10 = win.addPlot(left = 'y',buttom = 'x',title = "Meditation")
    EEG10.setRange(xRange = [0,historyLength],padding = 0)
    curve10 = EEG10.plot()
    curve10.setData(Meditation_data)

    portx = 'COM3'
    bps = 57600
    mSerial = serial.Serial(portx, int(bps))    #打开串口
    if(mSerial.isOpen()):
        print('serial is OK')
    else:
        print("serial is ERROR")
        mSerial.close()  # 关闭端口
    th1 = threading.Thread(target=Serial)
    th1.start()
    timer = pg.QtCore.QTimer()
    timer.timeout.connect(plotData)
    timer.start(800)
    sys.exit(app.exec())
#    app.exec()