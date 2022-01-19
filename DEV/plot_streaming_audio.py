

import numpy as np
import sys, os
import pyaudio
import wave
import pyqtgraph as pg
from qtpy import QtCore, QtGui, QtWidgets
import matplotlib.pyplot as plt

class MicThread(QtCore.QThread):
    sig = QtCore.Signal(bytes)
    
    def __init__(self, sc):
        super(MicThread, self).__init__()
        self.sc = sc
        self.sig.connect(self.sc.append)
        self.running = True

    def run(self):
        try:
            while self.running:
                data = self.sc.stream.read(self.sc.CHUNK)
                self.sig.emit(data)
        except:
            (type, value, traceback) = sys.exc_info()
            sys.stdout.write(str(type))
            sys.stdout.write(str(value))
            sys.stdout.write(str(traceback.format_exc()))
            
    def stop(self):
        sys.stdout.write('THREAD STOPPED')
        self.running = False

class StreamController(QtWidgets.QWidget):
    def __init__(self):
        super(StreamController, self).__init__()
        self.data = np.zeros((100000), dtype=np.int32)
        self.CHUNK = 1024
        self.CHANNELS = 1
        self.RATE = 44100
        self.FORMAT = pyaudio.paInt16
        
    def setup_stream(self):
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=self.FORMAT,  channels=self.CHANNELS, rate=self.RATE, 
                            input=True, frames_per_buffer=self.CHUNK)
        self.micthread = MicThread(self)
        self.micthread.start()
        

    def append(self, vals):
        vals = np.frombuffer(vals, 'int16')
        c = self.CHUNK
        self.data[:-c] = self.data[c:]
        self.data[-c:] = vals
        
    def breakdown_stream(self):
        self.micthread.terminate()
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(400, loop.quit)
        loop.exec_()
        
    
class StreamViz(QtWidgets.QWidget):
    def __init__(self):
        super(StreamViz, self).__init__()
        self.show()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_streamplot)
        self.timer.start(10)
        
        self.l = QtGui.QVBoxLayout()
        self.setLayout(self.l)
        self.p = pg.PlotWidget()
        self.l.addWidget(self.p)
        self.sc = StreamController()
        self.l.addWidget(self.sc)
        self.pdataitem = self.p.plot(self.sc.data)
        self.sc.setup_stream()
        
        self.startstop_button = QtWidgets.QPushButton('Stop')
        self.startstop_button.pressed.connect(self.startstop)
        self.startstop_button.status = 1
        self.l.addWidget(self.startstop_button)
        
    def startstop(self):
        b = self.startstop_button
        b.setEnabled(False)
        if b.status:
            self.sc.breakdown_stream()
            b.setText('Start')
            b.status = 0
        else:
            self.sc.setup_stream()
            b.setText('Stop')
            b.status = 1
        b.setEnabled(True)
        
    def closeEvent(self, event):
        if self.startstop_button.status:
            self.sc.breakdown_stream()
        event.accept()        

    def update_streamplot(self):
        self.pdataitem.setData(self.sc.data)

    
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    s = StreamViz()
    sys.exit(app.exec_())

