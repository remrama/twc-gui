#### dont delete with out taking out the nice links in here!
#### dont delete with out taking out the nice links in here!
#### dont delete with out taking out the nice links in here!
#### dont delete with out taking out the nice links in here!


from PyQt5 import QtCore, QtWidgets, QtMultimedia

import os
# os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'


import sys


class Window(QtWidgets.QWidget):

    def __init__(self, parent=None):

        QtWidgets.QWidget.__init__(self, parent)

        # app = QtWidgets.QApplication(sys.argv)
        
        self.playButton = QtWidgets.QPushButton(self.tr("&Play"))
        self.playButton.clicked.connect(self.play)
        buttonLayout = QtWidgets.QVBoxLayout()
        buttonLayout.addWidget(self.playButton)
        buttonLayout.addStretch()

        self.recordButton = QtWidgets.QPushButton(self.tr("&Record"))
        self.recordButton.clicked.connect(self.record)
        buttonLayout.addWidget(self.recordButton)

        # volume slider stuff
        self.volumeSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.volumeSlider.setMinimum(0) ## sliders can only have integer values
        self.volumeSlider.setMaximum(100) 
        self.volumeSlider.setTickInterval(10)
        self.volumeSlider.setSingleStep(1)
        self.volumeSlider.valueChanged.connect(self.changeVolume)
        self.volume = 0

        formLayout = QtWidgets.QFormLayout()
        formLayout.addRow(self.tr("&Volume:"), self.volumeSlider)
        horizontalLayout = QtWidgets.QHBoxLayout(self)
        horizontalLayout.addLayout(formLayout)
        horizontalLayout.addLayout(buttonLayout)

        filename = "./wav/dog1.wav"
        # filename = 'https://www.pachd.com/sfx/camera_click.wav'
        # fullpath = QtCore.QDir.current().absoluteFilePath(filename) 
        content = QtCore.QUrl.fromLocalFile(filename)
        # content = QtCore.QUrl(filename)

        ## with QMediaPlayer
        # player = QtMultimedia.QMediaPlayer()
        # player.setMedia(content)
        # player.setVolume(50)

        # # ## with QSound
        # self.player = QtMultimedia.QSound()
        # self.player.setSource(content)

        # best site summarizing pyqt audio ins/outs
        # https://doc.qt.io/qt-5/audiooverview.html

        ## playing audio
        # better latency perhaps
        # https://crackedbassoon.com/writing/playing-pure-tones-with-pyqt5
        # https://wiki.python.org/moin/PyQt/Playing%20a%20sound%20with%20QtMultimedia

        ## with QSoundEffect
        self.player = QtMultimedia.QSoundEffect()
        self.player.setSource(content)
        self.player.setVolume(self.volume) # 0 to 1
        # self.player.setLoopCount(1) # QtMultimedia.QSoundEffect.Infinite

        # audio recorder stuff
        # https://stackoverflow.com/a/64300056
        # https://doc.qt.io/qt-5/qtmultimedia-multimedia-audiorecorder-example.html
        # https://flothesof.github.io/pyqt-microphone-fft-application.html
        # https://gist.github.com/sloria/5693955
        self.recorder = QtMultimedia.QAudioRecorder()
        devices = self.recorder.audioInputs()
        # self.device_selector = QtMultimedia.QAudioInputSelectorControl(self)
        # recorder.setAudioInput(selected_audio_input)
        settings = QtMultimedia.QAudioEncoderSettings()
        # bit_rate = 32000 # values: 0, 32000, 64000,96000, 128000
        # n_channels = 1 # values: -1, 1, 2, 4
        # settings.setChannelCount(n_channels)
        # settings.setBitRate(bit_rate)
        # settings.setSampleRate() # Hz (-1, means find optimal)
        # # settings.setSampleType()QAudioFormat::UnSignedInt);
        # The quality settings parameter is only used in the constant quality encoding mode
        # (it basically ignores everything else???)
        # settings.setEncodingMode(QtMultimedia.QMultimedia.ConstantBitRateEncoding)
        settings.setEncodingMode(QtMultimedia.QMultimedia.ConstantQualityEncoding)
        settings.setQuality(QtMultimedia.QMultimedia.NormalQuality)
        self.recorder.setEncodingSettings(settings)

        export_fname = "test.wav"
        self.recorder.setOutputLocation(QtCore.QUrl.fromLocalFile(export_fname))

        self.recorder.stateChanged.connect(self.recording_state_change)

        # recording monitor 
        self.input_monitor = QtMultimedia.QAudioProbe()
        # connect to recorder
        # https://stackoverflow.com/a/66416099
        self.input_monitor.setSource(self.recorder)
        self.input_monitor.audioBufferProbed.connect(self.process_audio_data)

    def process_audio_data(self, buff):
        # https://doc.qt.io/qt-5/audiooverview.html
        # https://stackoverflow.com/a/67483225
        print(buff.startTime())

    def play(self):
        self.player.play()

    def record(self):
        state = self.recorder.state() # recording / paused / stopped
        status = self.recorder.status() # this has more options, like unavailable vs inactive
        # if status == QtMultimedia.QMediaRecorder.RecordingStatus:
        if state == QtMultimedia.QMediaRecorder.StoppedState:
            self.recorder.record()
        elif state == QtMultimedia.QMediaRecorder.RecordingState:
            self.recorder.stop()

    def recording_state_change(self, state):
        if state == QtMultimedia.QMediaRecorder.StoppedState:
            print("recording stopped, change border")
        elif state == QtMultimedia.QMediaRecorder.RecordingState:
            print("recording started, change border")

    def changeVolume(self, value):
        # pyqt sliders only take integers but range is 0-1
        self.volume = value / 100
        self.player.setVolume(self.volume)
        # self.createData()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec_())


# sound = QtCore.QUrl("https://www.pachd.com/sfx/camera_click.wav")
# player = QtMultimedia.QMediaPlayer(sound)
# player.setVolume(1)
# player.play()


# # PyQt5.QtCore.PYQT_VERSION_STR  # '5.9'

# test_fname = "./wav/dog1.wav"

# audioFormat = QtMultimedia.QAudioFormat()
# audioFormat.setChannelCount(1)
# audioFormat.setSampleRate(16000)
# audioFormat.setSampleSize(16)
# audioFormat.setCodec("audio/pcm")
# audioFormat.setByteOrder(QtMultimedia.QAudioFormat.LittleEndian)
# audioFormat.setSampleType(QtMultimedia.QAudioFormat.SignedInt)

# info = QtMultimedia.QAudioDeviceInfo.defaultInputDevice()

# devices = QtMultimedia.QAudioDeviceInfo.availableDevices(QtMultimedia.QAudio.AudioInput)
# print(devices)

# info.deviceName()  # 'Default Input Device'
# audio = QtMultimedia.QAudioInput(info, audioFormat)
# audio.volume()  # 0.0

# info.isFormatSupported(audioFormat)  # True