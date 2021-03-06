"""
Initialize a new session
and open the main interface.
"""
import os
import sys
import time
import json
import random
import logging
import warnings

from psychopy import parallel
# import sounddevice as sd

# import pyttsx3 # text2speech

from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia


with open("./config.json", "r", encoding="utf-8") as fp:
    C = json.load(fp)

stimuli_directory = C["stimuli_directory"]
if not os.path.isdir(stimuli_directory):
    raise ValueError("Stimuli directory not found!\nCheck config.json file.\nFiles available at https://osf.io/6p2mc/files/")

if not os.path.isdir(C["data_directory"]):
    raise ValueError("Data directory not found!\nCheck config.json file.\nFiles available at https://osf.io/6p2mc/files/")

cues_directory = os.path.join(stimuli_directory, "cues")
noise_directory = os.path.join(stimuli_directory, "noise")
biocals_directory = os.path.join(stimuli_directory, "biocals")

# def load_button_legend():
#     with open("./button_legend.json", "r") as f:
#         data = json.load(f)
#     return data

class BorderWidget(QtWidgets.QFrame):
    """thing to make a border
    https://stackoverflow.com/a/7351943
    """
    def __init__(self, *args):
        super(BorderWidget, self).__init__(*args)
        self.setStyleSheet("background-color: rgb(0,0,0,0); margin:0px; border:4px solid rgb(0, 0, 0); border-radius: 25px; ")

class InputDialog(QtWidgets.QDialog):
    """A separate initialization window
    that is never attached to the main interface.
    It just pops up once at the start and returns
    the subject and session IDs.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Session information")

        # this removes the default question mark ("What's this?") from the titlebar
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)

        self.subject_id = QtWidgets.QLineEdit(self)
        self.session_id = QtWidgets.QLineEdit(self)
        self.subject_id.setText(str(C["dev_subject_id"]))
        self.session_id.setText(str(C["dev_session_id"]))
        self.subject_id.setValidator(QtGui.QIntValidator(0, 999)) # must be a 3-digit number
        self.session_id.setValidator(QtGui.QIntValidator(0, 999))

        buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)

        layout = QtWidgets.QFormLayout(self)
        layout.addRow("Subject ID", self.subject_id)
        layout.addRow("Session ID", self.session_id)
        layout.addWidget(buttonBox)

        # self.setWhatsThis("What's this?")

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)


    def getInputs(self):
        return ( int(self.subject_id.text()), int(self.session_id.text()) )



def showAboutPopup():
    win = QtWidgets.QMessageBox()
    win.setWindowTitle("About")
    win.setIcon(QtWidgets.QMessageBox.Information)
    win.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Close)
    win.setDefaultButton(QtWidgets.QMessageBox.Close)
    informative_text = C["about_string"] + "\nVersion: " + C["version"]
    win.setInformativeText(informative_text)
    # win.setDetailedText("detailshere")
    # win.setStyleSheet("QLabel{min-width:500 px; font-size: 24px;} QPushButton{ width:250px; font-size: 18px; }");
    # win.setGeometry(200, 150, 100, 40)
    win.exec_()



class myWindow(QtWidgets.QMainWindow):
    """Main interface
    """
    def __init__(self, subject_id, session_id):
        super().__init__()

        # self.legend = load_button_legend()
        
        self.n_report_counter = 0 # cumulative counter for determining filenames

        # store the subject and session IDs
        # self.subject_id = subject_id
        # self.session_id = session_id
        # build a stringy-thing that will be used for lots of filenames
        sub_id_str = f"sub-{subject_id:03d}"
        ses_id_str = f"ses-{session_id:03d}"
        self.subj_sess_ids = f"{sub_id_str}_{ses_id_str}"

        # select directory for save location
        data_dir = QtWidgets.QFileDialog.getExistingDirectory(self,
            "Select data directory to place new subject directory",
            C["data_directory"],
            QtWidgets.QFileDialog.ShowDirsOnly)
        if not data_dir:
            sys.exit() # if the directory view is cancelled/exited
        else:
            # make sure the export dir doesn't exist and make it if it doesn't
            self.session_dir = os.path.join(data_dir, sub_id_str, ses_id_str)
            exist_ok = (subject_id==C["dev_subject_id"] and session_id==C["dev_session_id"])
            os.makedirs(self.session_dir, exist_ok=exist_ok)

        self.init_logger()

        self.biocals_order = ["Welcome", "OpenEyes", "CloseEyes", "LookLeft",
            "LookRight", "LookUp", "LookDown", "BlinkEyes", "ClenchTeeth",
            "InhaleExhale", "HoldBreath", "ExtendHands", "FlexFeet",
            "LucidSignalOpen", "LucidSignalClosed",
            "LucidSignalOpen", "LucidSignalClosed",
            "Thanks"]

        self.pport_address = C["pport_address"]            
        self.portcodes = {
            "TriggerInitialization": 200,
            "Note": 201,
            "LightsOff": 202,
            "LightsOn": 203,
            "DreamReportStarted": 204,
            "DreamReportStopped": 205,
            "NoiseStarted": 206,
            "NoiseStopped": 207,
            "CueStopped": 208,
        }

        for i, s in enumerate(self.biocals_order):
            pc = max(list(self.portcodes.values())) + 1
            assert pc < 245
            self.portcodes[f"biocals-{s}"] = pc

        self.cues_directory = cues_directory
        self.noise_directory = noise_directory
        self.biocals_directory = biocals_directory

        self.extract_cue_names()
        self.preload_cues()
        self.preload_biocals()

        self.init_recorder()

        self.initUI()

        init_msg = "Opened TWC interface v" + C["version"]
        self.log_info_msg(init_msg)
        # # Save port code legend to the log file
        # portcode_legend_str = "Portcode legend: " + json.dumps(self.portcodes)
        # self.log_info_msg(portcode_legend_str)

        self.init_pport()

    def showErrorPopup(self, short_msg, long_msg=None):
        self.log_info_msg("ERROR")
        win = QtWidgets.QMessageBox()
        # win.setIcon(QtWidgets.QMessageBox.Critical)
        win.setIconPixmap(QtGui.QPixmap("./img/fish.ico"))
        win.setText(short_msg)
        if long_msg is not None:
            win.setInformativeText(long_msg)
        win.setWindowTitle("Error")
        win.exec_()
    # def showErrorPopup(self, short_msg):
    #     em = QtWidgets.QErrorMessage()
    #     em.showMessage(short_msg)
    #     em.exec_()

    def log_info_msg(self, msg):
        """wrapper just to make sure msg goes to viewer too
        (should probably split up)
        """
        # log the message
        self.logger.info(msg)
        
        # print message to the GUI viewer box thing
        item = self.logViewer.addItem(time.strftime("%H:%M:%S") + " - " + msg)
        self.logViewer.repaint()
        self.logViewer.scrollToBottom()
        # item = pg.QtGui.QListWidgetItem(msg)
        # if warning: # change txt color
        #     item.setForeground(pg.QtCore.Qt.red)
        # self.eventList.addItem(item)
        # self.eventList.update()

    def init_pport(self):
        try:
            self.pport = parallel.ParallelPort(address=self.pport_address)
            self.pport.setData(0) # clear all pins out to prep for sending
            msg = "Parallel port connection succeeded."
        except:
            self.pport = None
            msg = "Parallel port connection failed."
        portcode = self.portcodes["TriggerInitialization"]
        self.send_to_pport(portcode, msg)


    def send_to_pport(self, portcode, port_msg):
        """Wrapper to avoid rewriting if not None a bunch
        to make sure the msg also gets logged to output file and gui
        """
        if self.pport is not None:
            self.pport.setData(0)
            self.pport.setData(portcode)
            success = "Sent"
        else:
            success = "Failed"
            ### Consider re-trying to connect here
        log_msg = f"{port_msg} - {success} portcode {portcode}"
        self.log_info_msg(log_msg)

    def init_logger(self):
        """initialize logger that writes to a log file
        as well as the terminal, with independent levels if info
        """
        log_name = f"{self.subj_sess_ids}"
        log_fname = os.path.join(self.session_dir, f"{log_name}_tmr.log")
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(logging.DEBUG)
        # open file handler to save external file
        fh = logging.FileHandler(log_fname, mode="w", encoding="utf-8")
        fh.setLevel(logging.DEBUG) # this determines what gets written to file
        # create console handler to choose separately from file
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG) # this determines what gets printed to console
        # create formatter and add it to the handlers
        formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d, %(levelname)s, %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)



    def initUI(self):

        self.statusBar().showMessage("Ready")

        ##### create actions that can be applied to *either* menu or toolbar #####
        
        # create a quit/exit option
        exitAct = QtWidgets.QAction(QtGui.QIcon("./img/exit.png"), "&Exit", self)
        exitAct.setShortcut("Ctrl+Q")
        exitAct.setStatusTip("Close the TWC interface (don't worry about saving)")
        exitAct.triggered.connect(self.close) #close goes to closeEvent
        
        # create an about window
        aboutAct = QtWidgets.QAction(QtGui.QIcon("./img/about.png"), "&About", self)
        # aboutAct.setShortcut("Ctrl+A")
        aboutAct.setStatusTip("What is this?")
        aboutAct.triggered.connect(showAboutPopup)

        #####  setup menu bar  #####
        menuBar = self.menuBar()
        menuBar.setNativeMenuBar(False) # needed for pyqt5 on Mac

        fileMenu = menuBar.addMenu("&File")
        fileMenu.addAction(aboutAct)
        fileMenu.addAction(exitAct)

        #### audio device list menu
        audioMenu = menuBar.addMenu("&Audio")
        inputMenu = audioMenu.addMenu(QtGui.QIcon("./img/input.png"), "&Input device")
        # outputMenu = audioMenu.addMenu(QtGui.QIcon("./img/output.png"), "&Output device")

        input_devices = self.recorder.audioInputs()
        # don't know y each device shows up twice
        input_devices = list(set(input_devices))
        # print(self.recorder.defaultAudioInput())
        # print(QtMultimedia.QtMultimediaControl.QAudioInputSelectorControl.defaultInput())
        # print(input_devices)
        # print(self.recorder.audioInput())
        # print(self.recorder.audioInputDescription("Default Input Device"))
        # print(QtMultimedia.QAudioRecorder())
        # devices = QtMultimedia.QAudioDeviceInfo.availableDevices(QtMultimedia.QAudio.AudioInput)
        # for d in devices:
        #     print(d.deviceName())
        # print(QtMultimedia.QAudioDeviceInfo.availableDevices(QtMultimedia.QAudio.AudioInput))
        # print(QtMultimedia.QAudioDeviceInfo.availableDevices(QtMultimedia.QAudio.AudioOutput))
        # save the action items to change the checkmarks later
        self.input_menu_items = []
        for device in input_devices:
            action = QtWidgets.QAction(device, self)
            action.setStatusTip(f"Set {device} as input device")
            action.setCheckable(True)
            # if device == self.recorder.defaultAudioInput():
            if device == self.recorder.audioInput(): # doesn't work :/
                action.setChecked(True)
            action.triggered.connect(self.update_input_device)
            inputMenu.addAction(action)
            self.input_menu_items.append(action)

        # # devices = sd.query_devices()
        # # input_devices  = { d["name"]: i for i, d in enumerate(devices) if d["max_input_channels"]>0 }
        # # output_devices = { d["name"]: i for i, d in enumerate(devices) if d["max_output_channels"]>0 }
        # # for k, v in input_devices.values():
        # for i, dev in enumerate(devices):
        #     if dev["max_input_channels"] > 0:
        #         action = QtWidgets.QAction(QtGui.QIcon("./img/1F399_color.png"), dev["name"], self)
        #         action.setStatusTip("Set "+dev["name"]+" as input device")
        #         action.triggered.connect(self.set_audio_device)
        #         inputMenu.addAction(action)
        #     if dev["max_output_channels"] > 0:
        #         action = QtWidgets.QAction(QtGui.QIcon("./img/1F4FB_color.png"), dev["name"], self)
        #         action.setStatusTip("Set "+dev["name"]+" as output device")
        #         action.triggered.connect(self.set_audio_device)
        #         outputMenu.addAction(action)


        # # create an about window
        # # aboutAct.setShortcut("Ctrl+A")
        # fileMenu = menuBar.addMenu("&File")
        # aboutAct.setStatusTip("What is this?")
        # aboutAct.triggered.connect(showAboutPopup)
        # outputAct = QtWidgets.QAction(QtGui.QIcon("./img/1F937_color.png"), "&Input", self)
        # audioMenu.addAction(inputAct)
        # audioMenu.addAction(exitAct)

        #####  setup tool bar  #####
        toolbar = self.addToolBar("&Add")
        # toolbar.addAction(initArousalAct)
        # toolbar.addAction(delRecallAct)

        # create central widget for holding grid layout
        self.init_CentralWidget()

        # # main window stuff
        # xywh = (50, 100, self.winWidth, self.winHeight) # xloc, yloc, width, height
        # self.setGeometry(*xywh)
        # self.setMinimumSize(300, 200)    
        self.setWindowTitle("TWC Interface")
        self.setWindowIcon(QtGui.QIcon("./img/fish.ico"))
        # self.setGeometry(100, 100, 600, 400)
        self.resize(1200, 500)
        self.show()


    def update_input_device(self):
        # if the current input is re-selected it still "changes" here
        # update the menu checkmarks
        # the only checkmark that gets AUTOMATICALLY updated is the one
        # that was clicked, so change all the others, and change BACK
        # the one that was undone if it was already the audio input (has to be something)
        checked = self.sender().isChecked()
        if checked:
            new_device_name = self.sender().text()
            for menu_item in self.input_menu_items:
                device_name = menu_item.text()
                if device_name == new_device_name:
                    self.recorder.setAudioInput(new_device_name)
                    # menu_item.setChecked(True) # happens by default
                else: # need to uncheck the one that WAS checked, so just hit all of them
                    menu_item.setChecked(False)
            # if new_device_name == self.recorder.audioInput():
            #     action.setChecked(True)
            # self.log_info_msg(f"INPUT DEVICE UPDATE {new_device_name}")
            # self.showErrorPopup("Not implemented yet")
        elif not checked:
            # this is when someone tries to "unselect" an input.
            # can't be allowed, but pyqt will uncheck it, so recheck it
            self.sender().setChecked(True) # recheck it
            # for menu_item in self.input_menu_items:
            #     if menu_item.iconText() == self.sender().text():
            #         menu_item.setChecked(True)


    def init_recorder(self):
        """initialize the recorder
        Do this early so that a list of devices can be generated
        to build the menubar options for changing the input device.
        Not allowing options to change settings for now.

        The output location is updated whenever a new recording is started.
        The default device is selected here but can be updated from menubar.
        """
        # audio recorder stuff
        # https://stackoverflow.com/a/64300056
        # https://doc.qt.io/qt-5/qtmultimedia-multimedia-audiorecorder-example.html
        # https://flothesof.github.io/pyqt-microphone-fft-application.html
        self.recorder = QtMultimedia.QAudioRecorder()
        settings = QtMultimedia.QAudioEncoderSettings()
        settings.setEncodingMode(QtMultimedia.QMultimedia.ConstantQualityEncoding)
        settings.setQuality(QtMultimedia.QMultimedia.NormalQuality)
        self.recorder.setEncodingSettings(settings)
        self.recorder.stateChanged.connect(self.recorder_state_change)

    def record(self):
        state = self.recorder.state() # recording / paused / stopped
        status = self.recorder.status() # this has more options, like unavailable vs inactive
        # if status == QtMultimedia.QMediaRecorder.RecordingStatus:
        if state == QtMultimedia.QMediaRecorder.StoppedState:
            ### start a new recording
            # generate filename
            self.n_report_counter += 1
            basename = f"{self.subj_sess_ids}_report-{self.n_report_counter:02d}.wav"
            export_fname = os.path.join(self.session_dir, basename)
            self.recorder.setOutputLocation(QtCore.QUrl.fromLocalFile(export_fname))
            self.recorder.record()
            # # filename = 'https://www.pachd.com/sfx/camera_click.wav'
            # # fullpath = QtCore.QDir.current().absoluteFilePath(filename) 
        elif state == QtMultimedia.QMediaRecorder.RecordingState:
            self.recorder.stop()

    @QtCore.pyqtSlot()
    def on_cuePlayingChange(self):
        """To uncheck the cue button if something stops on its own.
        and send port message of start/stop"""
        current_volume = self.sender().volume()
        filepath = self.sender().source().toString()
        cue_name = os.path.basename(filepath).split(".")[0]
        if self.sender().isPlaying():
            portcode = self.portcodes[cue_name]
            action = "Started"
        else:
            self.cueButton.setChecked(False) # so it unchecks if player stops naturally
            portcode = self.portcodes["CueStopped"]
            action = "Stopped"
        port_msg = f"Cue{action}-{cue_name} - Volume {current_volume}" 
        self.send_to_pport(portcode, port_msg)


    def recorder_state_change(self, state):
        if state == QtMultimedia.QMediaRecorder.StoppedState:
            self.logViewer.setStyleSheet("border: 0px solid red;")
        elif state == QtMultimedia.QMediaRecorder.RecordingState:
            self.logViewer.setStyleSheet("border: 3px solid red;")

    def handleDreamReportButton(self):
        self.record() # i think this function handles the start/stop decision
        if self.sender().isChecked():
            port_msg = "DreamReportStarted"
            # self.logViewer.setStyleSheet("border: 3px solid red;")
            # self.sender().setStyleSheet("background-color : lightgrey")
        else:
            port_msg = "DreamReportStopped"
            # self.logViewer.setStyleSheet("border: 0px solid red;")
            # self.sender().setStyleSheet("background-color : lightblue")
        # button_label = self.sender().text()
        portcode = self.portcodes[port_msg]
        self.send_to_pport(portcode, port_msg)

    def handleLightSwitch(self):
        # button_label = self.sender().text()
        if self.sender().isChecked():
            port_msg = "LightsOff"
        else:
            port_msg = "LightsOn"
        portcode = self.portcodes[port_msg]
        self.send_to_pport(portcode, port_msg)


    def preload_biocals(self):
        self.biocals_player = QtMultimedia.QMediaPlayer()
        self.playlist = QtMultimedia.QMediaPlaylist(self.biocals_player)
        self.playlist.setPlaybackMode(QtMultimedia.QMediaPlaylist.Sequential) #Sequential/CurrentItemOnce
        for biocal_str in self.biocals_order:
            biocal_path = os.path.join(self.biocals_directory, f"{biocal_str}.mp3")
            url = QtCore.QUrl.fromLocalFile(biocal_path)
            content = QtMultimedia.QMediaContent(url)
            self.playlist.addMedia(content)
        self.biocals_player.setPlaylist(self.playlist)
        self.playlist.currentIndexChanged.connect(self.on_biocalsPlaylistIndexChange)

    def play_biocals(self):
        self.biocals_player.setVolume(50) # 0-100 # 0 to 1
        self.biocals_player.play()

    @QtCore.pyqtSlot()
    def on_biocalsPlaylistIndexChange(self):
        current_index = self.sender().currentIndex()
        if 0 < current_index < len(self.biocals_order)-1:
            biocal_str = self.biocals_order[current_index]
            portcode = self.portcodes[f"biocals-{biocal_str}"]
            msg = f"BiocalStarted-{biocal_str}"
            self.send_to_pport(portcode, msg)
        else:
            self.biocalsButton.setChecked(False)

    def extract_cue_names(self):
        self.cue_name_list = []
        for cue_basename in os.listdir(self.cues_directory):
            if cue_basename.endswith(".wav"):
                assert cue_basename.count(".") == 1
                cue_name = cue_basename.split(".")[0]
                assert cue_name not in self.portcodes, "No duplicate cue names"
                existing_portcodes = list(self.portcodes.values())
                portcode = max(existing_portcodes) + 1
                assert portcode < 245
                self.portcodes[cue_name] = int(portcode)
                self.cue_name_list.append(cue_name)

    def preload_cues(self):
        self.playables = {}
        for cue_name in self.cue_name_list:
            cue_basename = f"{cue_name}.wav"
            cue_fullpath = os.path.join(self.cues_directory, cue_basename)
            content = QtCore.QUrl.fromLocalFile(cue_fullpath)
            player = QtMultimedia.QSoundEffect()
            player.setSource(content)
            player.setVolume(C["default_volume"]) # 0 to 1
            ### these might be easier to handle in a Qmediaplaylist and then indexing like track numbers
            # player.setLoopCount(1) # QtMultimedia.QSoundEffect.Infinite
            # Connect to a function that gets called when it starts or stops playing.
            # Only need it for the "stop" so it unchecks the cue button when not manually stopped.
            player.playingChanged.connect(self.on_cuePlayingChange)
            self.playables[cue_name] = player

        # noise player
        noise_basename = "pink.wav"
        noise_fullpath = os.path.join(self.noise_directory, noise_basename)
        noise_content = QtCore.QUrl.fromLocalFile(noise_fullpath)
        ## this should prob be a mediaplayer/playlist which uses less resources
        self.noisePlayer = QtMultimedia.QSoundEffect()
        self.noisePlayer.setSource(noise_content)
        self.noisePlayer.setVolume(C["default_volume"]) # 0 to 1
        self.noisePlayer.setLoopCount(QtMultimedia.QSoundEffect.Infinite)
        # Connect to a function that gets called when it starts or stops playing.
        # Only need it for the "stop" so it unchecks the cue button when not manually stopped.
        # self.noisePlayer.playingChanged.connect(self.on_cuePlayingChange)

    @QtCore.pyqtSlot()
    def handleNoiseButton(self):
        if self.noiseButton.isChecked():
            # self.noisePlayer.setLoopCount(QtMultimedia.QSoundEffect.Infinite)
            self.noisePlayer.play()
            msg = "NoiseStarted"
        else: # not checked
            self.noisePlayer.stop()
            msg = "NoiseStopped"
        self.send_to_pport(self.portcodes[msg], msg)

    @QtCore.pyqtSlot()
    def handleBiocalsButton(self):
        ## couldnt these use "sender"?
        if self.biocalsButton.isChecked():
            self.play_biocals()
        else: # not checked
            self.biocals_player.stop()
            self.playlist.setCurrentIndex(0)

    @QtCore.pyqtSlot()
    def handleCueButton(self):
        if self.cueButton.isChecked():
            # #### play selected item
            # selected_item = self.rightList.currentItem()
            # if selected_item is not None:
            #     cue_basename = selected_item.text()
            #     portcode = self.portcodes[cue_basename]
            #     port_msg = "CUE+" + cue_basename
            #     self.send_to_pport(portcode, port_msg)
            #     self.playables[cue_basename].play()
            #### play random
            n_list_items = self.rightList.count()
            if n_list_items > 0:
                selected_item = random.choice(range(n_list_items))
                cue_name = self.rightList.item(selected_item).text()
                self.playables[cue_name].play()
        else: # stop
            for k, v in self.playables.items():
                if v.isPlaying():
                    v.stop()

    def handleNoteButton(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Text Input Dialog", "Custom note (no commas):")
        # self.subject_id.setValidator(QtGui.QIntValidator(0, 999)) # must be a 3-digit number
        if ok: # True of OK button was hit, False otherwise (cancel button)
            portcode = self.portcodes["Note"]
            port_msg = f"Note [{text}]"
            self.send_to_pport(portcode, port_msg)

    @QtCore.pyqtSlot()
    def handleLeft2RightButton(self):
        self.rightList.addItem(self.leftList.takeItem(self.leftList.currentRow()))
        self.rightList.sortItems()

    @QtCore.pyqtSlot()
    def handleRight2LeftButton(self):
        self.leftList.addItem(self.rightList.takeItem(self.rightList.currentRow()))
        self.leftList.sortItems()

    # def generate_cue_button(self, button_label):
    #     """run this separate outside of overall button
    #     creation because otherwise there is some persistent
    #     with the variables??
    #     """
    #     b = QtWidgets.QPushButton(button_label, self)
    #     help_string = self.legend[button_label]["help"]
    #     b.setStatusTip(help_string)
    #     # b.setShortcut("Ctrl+R")
    #     b.clicked.connect(lambda: self.handleCueButton(button_label))
    #     return b

    def init_CentralWidget(self):
        """The central widget holds the *non-toolbar*
        contents of the main window."""

        # basic layout/customization stuff

        #### to change color
        # self.setAutoFillBackground(True)
        # palette = self.palette()
        # palette.setColor(QtGui.QPalette.Window, QtGui.QColor("blue"))
        # self.setPalette(palette)

        # manage the location/size of widgets
        # grid = QtWidgets.QGridLayout()
        # i = 0
        # for label, lineedit in zip(self.setupLabels,self.setupLEdits):
        #     grid.addWidget(label,i,0)
        #     grid.addWidget(lineedit,i,1)
        #     i += 1
        # grid.addWidget(initSessButton,i,0,1,2)

        # # intialize the central widget
        # centralWidget = QtWidgets.QWidget()
        # # centralWidget.setLayout(grid)
        # self.setCentralWidget(centralWidget)

        # self.winWidth = centralWidget.sizeHint().width()
        # self.winHeight = centralWidget.sizeHint().height()

        ############ create buttons ################

        leftListHeader = QtWidgets.QLabel("Cue Bank", self)
        leftListHeader.setAlignment(QtCore.Qt.AlignCenter)
        # leftListHeader.setStyleSheet("border: 1px solid red;") #changed

        self.leftList = QtWidgets.QListWidget()
        self.rightList = QtWidgets.QListWidget()
        self.leftList.setAutoScroll(True) # scrollable
        self.leftList.setAutoScroll(True)
        self.leftList.setSortingEnabled(True) # allow alphabetical sorting
        self.rightList.setSortingEnabled(True)

        self.cueButton = QtWidgets.QPushButton("Cue", self)
        self.cueButton.setStatusTip("Play a random cue from the right side.")
        self.cueButton.setShortcut("Ctrl+R")
        self.cueButton.setCheckable(True)
        self.cueButton.clicked.connect(self.handleCueButton)

        self.noiseButton = QtWidgets.QPushButton("Noise", self)
        self.noiseButton.setStatusTip("Play pink noise.")
        self.noiseButton.setShortcut("Ctrl+P")
        self.noiseButton.setCheckable(True)
        self.noiseButton.clicked.connect(self.handleNoiseButton)

        self.biocalsButton = QtWidgets.QPushButton("Biocals", self)
        self.biocalsButton.setStatusTip("Start biocals.")
        self.biocalsButton.setShortcut("Ctrl+B")
        self.biocalsButton.setCheckable(True)
        self.biocalsButton.clicked.connect(self.handleBiocalsButton)

        self.left2rightButton = QtWidgets.QPushButton(">", self)
        self.right2leftButton = QtWidgets.QPushButton("<", self)
        self.left2rightButton.setStatusTip("Move selected item from left to right.")
        self.right2leftButton.setStatusTip("Move selected item from right to left.")
        self.left2rightButton.clicked.connect(self.handleLeft2RightButton)
        self.right2leftButton.clicked.connect(self.handleRight2LeftButton)
        cueSelectionLayout = QtWidgets.QGridLayout()
        # cueSelectionLayout.addWidget(logViewer_header, 0, 0, 1, 1)
        cueSelectionLayout.addWidget(leftListHeader, 0, 0, 1, 2)
        cueSelectionLayout.addWidget(self.cueButton, 0, 3, 1, 2)
        cueSelectionLayout.addWidget(self.leftList, 1, 0, 4, 2)
        cueSelectionLayout.addWidget(self.rightList, 1, 3, 4, 2)
        cueSelectionLayout.addWidget(self.left2rightButton, 2, 2, 1, 1)
        cueSelectionLayout.addWidget(self.right2leftButton, 3, 2, 1, 1)
        # cueSelectionLayout.addWidget(self.cueButton, 5, 3, 1, 2)
        for c in self.cue_name_list:
            self.leftList.addItem(c)

        # # all cue buttons are similar so can be created simultaneously
        # self.buttons = {}
        # for k in self.legend.keys():
        #     if k not in ["Dream report", "Note"]:
        #         self.buttons[k] = self.generate_cue_button(k)

        dreamReportButton = QtWidgets.QPushButton("Record dream report", self)
        dreamReportButton.setStatusTip("Ask for a dream report and start recording.")
        dreamReportButton.setCheckable(True)
        dreamReportButton.clicked.connect(self.handleDreamReportButton)

        noteButton = QtWidgets.QPushButton("Note", self)
        noteButton.setStatusTip("Open a text box and timestamp a note.")
        noteButton.clicked.connect(self.handleNoteButton)

        lightSwitch = QtWidgets.QPushButton("Lights Off", self)
        lightSwitch.setStatusTip("Switch lights off or back on.")
        lightSwitch.setCheckable(True)
        lightSwitch.clicked.connect(self.handleLightSwitch)

        buttonsLayout = QtWidgets.QVBoxLayout()
        # buttonsLayout.setMargin(20)
        buttonsLayout.setAlignment(QtCore.Qt.AlignCenter)
        # buttonsLayout.setFixedSize(12, 12)
        buttonsLayout.addWidget(self.noiseButton)
        buttonsLayout.addWidget(self.biocalsButton)
        buttonsLayout.addWidget(lightSwitch)
        buttonsLayout.addWidget(dreamReportButton)
        buttonsLayout.addWidget(noteButton)


        logViewer_header = QtWidgets.QLabel("Event log", self)
        logViewer_header.setAlignment(QtCore.Qt.AlignCenter)
        self.logViewer = QtWidgets.QListWidget()
        # logViewer.setGeometry(20,20,100,700)
        self.logViewer.setAutoScroll(True)

        # cue_header = QtWidgets.QLabel("Audio cue buttons", self)
        # cue_header.setAlignment(QtCore.Qt.AlignCenter)
        # # cue_header.setStyleSheet("border: 1px solid red;") #changed

        # # make a subset of buttons in a vertical layout
        # left_button_layout = QtWidgets.QVBoxLayout()
        # left_button_header = QtWidgets.QLabel("Waking", self)
        # # left_button_header.setText("Waking")
        # # left_button_header.setMargin(1)
        # left_button_header.setAlignment(QtCore.Qt.AlignCenter)
        # # left_button_header.setFixedSize(12, 12)
        # left_button_layout.addWidget(left_button_header)
        # left_button_layout.addWidget(self.buttons["Biocals"])
        # left_button_layout.addWidget(self.buttons["LRLR"])
        # left_button_layout.addWidget(self.buttons["TLR Training 1"])
        # left_button_layout.addWidget(self.buttons["TLR Training 2"])

        # right_button_layout = QtWidgets.QVBoxLayout()
        # right_button_header = QtWidgets.QLabel("Sleeping", self)
        # # left_button_header.setText("Waking")
        # # right_button_header.setMargin(20)
        # right_button_header.setAlignment(QtCore.Qt.AlignCenter)
        # # left_button_header.setFixedSize(12, 12)
        # right_button_layout.addWidget(right_button_header)
        # right_button_layout.addWidget(self.buttons["TLR cue"])
        # right_button_layout.addWidget(self.buttons["TMR cue"])


        border_widget = BorderWidget()

        # ## sublayout for audio cue section
        # audiocue_layout = QtWidgets.QGridLayout()
        # audiocue_layout.addWidget(cue_header, 0, 0, 1, 2) # widget, row, col, rowspan, colspan
        # audiocue_layout.addLayout(left_button_layout, 1, 0, 2, 1)
        # audiocue_layout.addLayout(right_button_layout, 1, 1, 2, 1)

        ## sublayout for log viewer
        viewer_layout = QtWidgets.QGridLayout()
        viewer_layout.addWidget(logViewer_header, 0, 0, 1, 1)
        viewer_layout.addWidget(self.logViewer, 2, 0, 2, 1)

        ## sublayout for extra buttons
        extra_layout = QtWidgets.QGridLayout()
        extra_layout.addLayout(buttonsLayout, 0, 0, 1, 1)

        # ## layout for the audio i/o monitoring
        # # io_layout = QtWidgets.QGridLayout()
        # io_layout = QtWidgets.QVBoxLayout()
        # io_header = QtWidgets.QLabel("Audio I/O", self)
        # io_header.setAlignment(QtCore.Qt.AlignCenter)
        # # io_layout.addWidget(io_header, 0, 0, 1, 2)
        # io_layout.addWidget(io_header)

        # # add row of headers
        # header_layout = QtWidgets.QHBoxLayout()
        # for label in ["Output Cue\nVolume", "Output Noise\nVolume", "Input\nGain", "Input\nVisualization"]:
        #     header_layout.addWidget(QtWidgets.QLabel(label, self))
        # io_layout.addLayout(header_layout)

        # create 2 sliders, 1 for output volume another for input gain
        # create volume slider and add to this i/o layout
        # volume slider stuff
        # cueVolumeSlider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        buttonsLayout = QtWidgets.QVBoxLayout()

        ## sliders can only have integer values
        ## so have to use 0-100 and then divide when setting it later
        default_vol_upscaled = int(100 * C["default_volume"])

        # Cue Volume Knob Layout
        cueVolumeKnob = QtWidgets.QDial()
        cueVolumeKnob.setMinimum(0)
        cueVolumeKnob.setMaximum(100)
        cueVolumeKnob.setSingleStep(1)
        cueVolumeKnob.setValue(default_vol_upscaled)
        cueVolumeKnob.setNotchesVisible(True)
        cueVolumeKnob.setWrapping(False)
        cueVolumeKnob.valueChanged.connect(self.changeOutputCueVolume)
        cueVolumeLabel = QtWidgets.QLabel("Cue Volume", self)
        cueVolumeLabel.setAlignment(QtCore.Qt.AlignCenter)
        cueVolumeLayout = QtWidgets.QVBoxLayout()
        cueVolumeLayout.addWidget(cueVolumeLabel)
        cueVolumeLayout.addWidget(cueVolumeKnob)

        # Noise Volume Knob Layout
        noiseVolumeKnob = QtWidgets.QDial()
        noiseVolumeKnob.setMinimum(0)
        noiseVolumeKnob.setMaximum(100)
        noiseVolumeKnob.setSingleStep(1)
        noiseVolumeKnob.setValue(default_vol_upscaled)
        noiseVolumeKnob.setNotchesVisible(True)
        noiseVolumeKnob.setWrapping(False)
        noiseVolumeKnob.valueChanged.connect(self.changeOutputNoiseVolume)
        noiseVolumeLabel = QtWidgets.QLabel("Noise Volume", self)
        noiseVolumeLabel.setAlignment(QtCore.Qt.AlignCenter)
        noiseVolumeLayout = QtWidgets.QVBoxLayout()
        noiseVolumeLayout.addWidget(noiseVolumeLabel)
        noiseVolumeLayout.addWidget(noiseVolumeKnob)

        # Biocals Volume Knob Layout
        biocalsVolumeKnob = QtWidgets.QDial()
        biocalsVolumeKnob.setMinimum(0)
        biocalsVolumeKnob.setMaximum(100)
        biocalsVolumeKnob.setSingleStep(1)
        biocalsVolumeKnob.setValue(default_vol_upscaled)
        biocalsVolumeKnob.setNotchesVisible(True)
        biocalsVolumeKnob.setWrapping(False)
        biocalsVolumeKnob.valueChanged.connect(self.changeOutputBiocalsVolume)
        biocalsVolumeLabel = QtWidgets.QLabel("Biocals Volume", self)
        biocalsVolumeLabel.setAlignment(QtCore.Qt.AlignCenter)
        biocalsVolumeLayout = QtWidgets.QVBoxLayout()
        biocalsVolumeLayout.addWidget(biocalsVolumeLabel)
        biocalsVolumeLayout.addWidget(biocalsVolumeKnob)

        volumeKnobsLayout = QtWidgets.QHBoxLayout()
        volumeKnobsLayout.addLayout(cueVolumeLayout)
        volumeKnobsLayout.addLayout(noiseVolumeLayout)
        volumeKnobsLayout.addLayout(biocalsVolumeLayout)
        # formLayout = QtWidgets.QFormLayout()
        # formLayout.addRow(self.tr("&Volume:"), volumeSlider)
        # io_layout.addLayout(formLayout, 1, 0, 1, 2)
        # horizontalLayout = QtWidgets.QHBoxLayout(self)
        # horizontalLayout.addLayout(formLayout)
        # horizontalLayout.addLayout(buttonLayout)

        # gainSlider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        # gainSlider.valueChanged.connect(self.changeInputGain)
        # volumeKnobsLayout.addWidget(gainSlider)

        # ## add a blank widget placeholder for the visualization for now
        # input_vis_widget = QtWidgets.QWidget()
        # volumeKnobsLayout.addWidget(input_vis_widget)


        # this main/larger layout holds all the subwidgets and in some cases other layouts
        main_layout = QtWidgets.QGridLayout()
        # main_layout.addLayout(audiocue_layout, 0, 0, 3, 2)
        main_layout.addLayout(cueSelectionLayout, 0, 0, 2, 2)
        main_layout.addLayout(extra_layout, 3, 0, 1, 2)
        main_layout.addLayout(viewer_layout, 0, 2, 2, 1)
        main_layout.addLayout(volumeKnobsLayout, 2, 2, 2, 1)
        # main_layout.setContentsMargins(20, 20, 20, 20)
        # main_layout.setSpacing(20)
        # main_layout.addWidget(border_widget, 0, 0, 3, 2)
        # main_layout.setColumnStretch(0, 2)
        # main_layout.setColumnStretch(1, 1)

        central_widget = QtWidgets.QWidget()
        # central_widget.setStyleSheet("background-color:salmon;")
        central_widget.setContentsMargins(5, 5, 5, 5)
        central_widget.move(100, 100)
        # central_widget.setFixedSize(300, 300) # using self.resize makes it resizable
        central_widget.setLayout(main_layout)

        self.setCentralWidget(central_widget)
        self.main_layout = main_layout
        # self.resize(300, 300)

    def _volume_rescaler(self, zero_to_hundred):
        # pyqt sliders only take integers but range is 0-1
        float_volume = round(zero_to_hundred / 100, 1)
        return float_volume

    def changeOutputCueVolume(self, value):
        # self.volume = value / 100
        float_volume = self._volume_rescaler(value)
        for player in self.playables.values():
            player.setVolume(float_volume)
        # self.createData()

    def changeOutputNoiseVolume(self, value):
        # pyqt sliders only take integers but range is 0-1
        # self.volume = value / 100
        float_volume = self._volume_rescaler(value)
        self.noisePlayer.setVolume(float_volume)
        if value % 10 == 0: # for now to avoid overlogging
            self.log_info_msg(f"Set noise volume: {value:d}")
        # self.createData()

    def changeOutputBiocalsVolume(self, value):
        # self.volume = value / 100
        # float_volume = self._volume_rescaler(value)
        self.biocals_player.setVolume(value)
        # self.createData()

    def changeInputGain(self, value):
        self.showErrorPopup("Not implemented yet", "This should eventually allow for increasing mic input volume.")

    def closeEvent(self, event):
        """customize exit.
        closeEvent is a default method used in pyqt to close, so this overrides it
        """
        if QtWidgets.QMessageBox.question(self, "Exit", "Are you sure?") == QtWidgets.QMessageBox.Yes:
            self.log_info_msg("Program closed")
            event.accept()
            # self.closed.emit()
            # sys.exit()
        else:
            event.ignore()

    def play_speech(self):
        button_txt = self.sender().text()
        speech_str = {
            "LRLR request" : "move your eyes left and right",
            "biocals" : "look up. look down. look left. look right.",
            "GET LUCID" : "GET LUCID!",
            "TMR" : "targeted memory reactivation cue",
        }[button_txt]
        pyttsx3.speak(speech_str)
        # engine = pyttsx3.init()
        # engine.say(speech_str)
        # engine.runAndWait()

    def training_onClick(self):
        # initialize the text-to-speech engine
        # engine = pyttsx3.init()
        # option to change some text-to-speech parameters
        # engine.setProperty("rate", 200) # default 200
        # engine.setProperty("volume", 1) # default 1 (range 0-1)
        # voices = engine.getProperty('voices')       #getting details of current voice
        # # engine.setProperty('voice', voices[0].id)  #changing index, changes voices. o for male

        # make a list of all phrases that will be said
        PHRASES = [
            "When you here the cue, imagine being lucid.",
            "Now you should feel comfortable falling asleep.",
        ]

        # configurate the sequence of phrases to play and their timings
        SEQUENCE = [
            (0, .1), # play first phrase with .1 minute of silence (including the minimal time of saying the phrase)
            (0, .1),
            (1, .05),
            (0, .05),
        ]

        for phrase_id, tminute in SEQUENCE:
            phrase = PHRASES[phrase_id]
            tsecs = 60 * tminute
            t0 = time.time()
            self.logger.info(phrase)
            pyttsx3.speak(phrase)
            while time.time() - t0 < tsecs:
                pass


# run the app
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    inbox = InputDialog()
    inbox.exec_()
    if inbox.result(): # 1 if they hit Ok, 0 if cancel
        subject_id, session_id = inbox.getInputs()

        # open thread where the <worker> will be placed
        # thread = QtCore.QThread()

        win = myWindow(subject_id, session_id)

        # ####################### audio stuff
        # import livespec
        # w = livespec.SpectrogramWidget()
        # w.read_collected.connect(w.update)
        # mic = livespec.MicrophoneRecorder(w.read_collected)
        # # time (seconds) between reads
        # interval = livespec.FS/livespec.CHUNKSZ
        # t = QtCore.QTimer()
        # t.timeout.connect(mic.read)
        # t.start(1000/interval) #QTimer takes ms
        # win.spect_layout.addWidget(w, 2, 0, 2, 1)
        # ####################### audio stuff

        sys.exit(app.exec_())
