"""
Initialize a new session
and open the main interface.
"""
import os
import sys
import time
import json
import serial
import random
import logging
import warnings

# import sounddevice as sd

import config as c

# import pyttsx3 # text2speech

from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia

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
        self.subject_id.setText(str(c.DEV_SUBJECT_ID))
        self.session_id.setText(str(c.DEV_SESSION_ID))
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
    win.setInformativeText(c.ABOUT_STRING)
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
        self.subj_sess_ids = f"{sub_id_str}-{ses_id_str}"

        # select directory for save location
        data_dir = QtWidgets.QFileDialog.getExistingDirectory(self,
            "Select data directory to place new subject directory",
            c.DEFAULT_DATA_DIRECTORY,
            QtWidgets.QFileDialog.ShowDirsOnly)
        if not data_dir:
            sys.exit() # if the directory view is cancelled/exited
        else:
            # make sure the export dir doesn't exist and make it if it doesn't
            self.session_dir = os.path.join(data_dir, sub_id_str, ses_id_str)
            exist_ok = (subject_id==c.DEV_SUBJECT_ID and session_id==c.DEV_SESSION_ID)
            os.makedirs(self.session_dir, exist_ok=exist_ok)

        self.init_logger()

        self.portcodes = {
            "DreamReport": 10,
            "Note": 20,
        }

        self.soundfile_dir = c.SOUNDFILE_DIRECTORY
        self.extract_cue_basenames()
        self.preload_soundfiles()

        self.init_recorder()

        self.initUI()

        init_msg = f"Opened TWC interface v{c.VERSION}"
        self.log_info_msg(init_msg)
        # # save the legend as its own file, in case things change later
        # # (later it might make more sense to save version numbers and work from that)
        # legend_out_fname = os.path.join(self.session_dir,
        #     f"{self.subj_sess_ids}_legend.json")
        # with open(legend_out_fname, "w", encoding="utf-8") as f:
        #     json.dump(self.legend, f, indent=4, ensure_ascii=False)
        # # self.log_info_msg(json.dumps(self.legend), print_in_gui=False)


    def showErrorPopup(self, short_msg, long_msg=None):
        self.log_info_msg("ERROR")
        win = QtWidgets.QMessageBox()
        # win.setIcon(QtWidgets.QMessageBox.Critical)
        win.setIconPixmap(QtGui.QPixmap("./img/exit.png"))
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


    def send_port_msg(self, portcode, port_msg):
        """wrapper around serial.send
        to make sure the msg also gets logged to output file and gui
        """
        log_msg = f"{portcode}-{port_msg}"
        if c.PORT_ADDRESS is not None:
            serial.send(portcode)
        else:
            log_msg = "!!!-" + log_msg
        self.log_info_msg(log_msg)


    def init_logger(self):
        """initialize logger that writes to a log file
        as well as the terminal, with independent levels if info
        """
        log_name = f"{self.subj_sess_ids}_twc"
        log_fname = os.path.join(self.session_dir, f"{log_name}.log")
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
            fmt="%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
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
        # save the action items to change the checkmarks later
        self.input_menu_items = []
        for dev in input_devices:
            action = QtWidgets.QAction(dev, self)
            action.setStatusTip(f"Set {dev} as input device")
            action.setCheckable(True)
            if dev == self.recorder.audioInput():
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
        """To uncheck the cue button if something stops on its own."""
        if not self.sender().isPlaying():
            self.cueButton.setChecked(False)



    def recorder_state_change(self, state):
        if state == QtMultimedia.QMediaRecorder.StoppedState:
            self.logViewer.setStyleSheet("border: 0px solid red;")
        elif state == QtMultimedia.QMediaRecorder.RecordingState:
            self.logViewer.setStyleSheet("border: 3px solid red;")

    def handleDreamReportButton(self):
        self.record() # i think this function handles the start/stop decision
        if self.sender().isChecked():
            port_msg = "DreamReport+start"
            # self.logViewer.setStyleSheet("border: 3px solid red;")
            # self.sender().setStyleSheet("background-color : lightgrey")
        else:
            port_msg = "DreamReport+stop"
            # self.logViewer.setStyleSheet("border: 0px solid red;")
            # self.sender().setStyleSheet("background-color : lightblue")
        button_label = self.sender().text()
        portcode = self.portcodes["DreamReport"]
        self.send_port_msg(portcode, port_msg)

    def extract_cue_basenames(self):
        self.cue_basename_list = []
        for cue_basename in os.listdir(self.soundfile_dir):
            if "-" in cue_basename and cue_basename.endswith(".wav"):
                cue_name, portcode = cue_basename.split(".")[0].split("-")
                if cue_name.isalpha() and portcode.isdigit():
                    self.portcodes[cue_basename] = int(portcode)
                    self.cue_basename_list.append(cue_basename)

    def preload_soundfiles(self):
        self.playables = {}
        for cue_basename in self.cue_basename_list:
            cue_fullpath = os.path.join(self.soundfile_dir, cue_basename)
            content = QtCore.QUrl.fromLocalFile(cue_fullpath)
            player = QtMultimedia.QSoundEffect()
            player.setSource(content)
            player.setVolume(0) # 0 to 1
            # player.setLoopCount(1) # QtMultimedia.QSoundEffect.Infinite
            # Connect to a function that gets called when it starts or stops playing.
            # Only need it for the "stop" so it unchecks the cue button when not manually stopped.
            player.playingChanged.connect(self.on_cuePlayingChange)
            self.playables[cue_basename] = player

    @QtCore.pyqtSlot()
    def handleCueButton(self):
        if self.cueButton.isChecked():
            # #### play selected item
            # selected_item = self.rightList.currentItem()
            # if selected_item is not None:
            #     cue_basename = selected_item.text()
            #     portcode = self.portcodes[cue_basename]
            #     port_msg = "CUE+" + cue_basename
            #     self.send_port_msg(portcode, port_msg)
            #     self.playables[cue_basename].play()
            #### play random
            n_list_items = self.rightList.count()
            if n_list_items > 0:
                selected_item = random.choice(range(n_list_items))
                cue_basename = self.rightList.item(selected_item).text()
                portcode = self.portcodes[cue_basename]
                port_msg = "CUE+" + cue_basename
                self.send_port_msg(portcode, port_msg)
                self.playables[cue_basename].play()
        else: # stop
            for k, v in self.playables.items():
                if v.isPlaying():
                    v.stop()
                    self.send_port_msg(1, "STOPPED")

    def handleNoteButton(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "Text Input Dialog", "Custom note:")
        # self.subject_id.setValidator(QtGui.QIntValidator(0, 999)) # must be a 3-digit number
        if ok: # True of OK button was hit, False otherwise (cancel button)
            portcode = self.portcodes["Note"]
            port_msg = "NOTE+" + text
            self.send_port_msg(portcode, port_msg)

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

        leftListHeader = QtWidgets.QLabel("Bank", self)
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
        for c in self.cue_basename_list:
            self.leftList.addItem(c)

        # # all cue buttons are similar so can be created simultaneously
        # self.buttons = {}
        # for k in self.legend.keys():
        #     if k not in ["Dream report", "Note"]:
        #         self.buttons[k] = self.generate_cue_button(k)

        dreamReportButton = QtWidgets.QPushButton("Dream report", self)
        dreamReportButton.setStatusTip("Ask for a dream report and start recording.")
        dreamReportButton.setCheckable(True)
        dreamReportButton.clicked.connect(self.handleDreamReportButton)

        noteButton = QtWidgets.QPushButton("Note", self)
        noteButton.setStatusTip("Open a text box and timestamp a note.")
        noteButton.clicked.connect(self.handleNoteButton)

        buttonsLayout = QtWidgets.QVBoxLayout()
        # buttonsLayout.setMargin(20)
        buttonsLayout.setAlignment(QtCore.Qt.AlignCenter)
        # buttonsLayout.setFixedSize(12, 12)
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

        ## layout for the audio i/o monitoring
        # io_layout = QtWidgets.QGridLayout()
        io_layout = QtWidgets.QVBoxLayout()
        io_header = QtWidgets.QLabel("Audio I/O", self)
        io_header.setAlignment(QtCore.Qt.AlignCenter)
        # io_layout.addWidget(io_header, 0, 0, 1, 2)
        io_layout.addWidget(io_header)

        # add row of headers
        header_layout = QtWidgets.QHBoxLayout()
        for label in ["Output\nVolume", "Input\nGain", "Input\nVisualization"]:
            header_layout.addWidget(QtWidgets.QLabel(label, self))
        io_layout.addLayout(header_layout)

        controls_layout = QtWidgets.QHBoxLayout()
        # create 2 sliders, 1 for output volume another for input gain
        # create volume slider and add to this i/o layout
        # volume slider stuff
        volumeSlider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        ## sliders can only have integer values
        ## so have to use 0-100 and then divide when setting it later
        volumeSlider.setMinimum(0)
        volumeSlider.setMaximum(100)
        # volumeSlider.setTickInterval(10)
        volumeSlider.setSingleStep(1)
        volumeSlider.setValue(0)
        volumeSlider.valueChanged.connect(self.changeOutputVolume)
        controls_layout.addWidget(volumeSlider)
        # formLayout = QtWidgets.QFormLayout()
        # formLayout.addRow(self.tr("&Volume:"), volumeSlider)
        # io_layout.addLayout(formLayout, 1, 0, 1, 2)
        # horizontalLayout = QtWidgets.QHBoxLayout(self)
        # horizontalLayout.addLayout(formLayout)
        # horizontalLayout.addLayout(buttonLayout)

        gainSlider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        gainSlider.valueChanged.connect(self.changeInputGain)
        controls_layout.addWidget(gainSlider)

        ## add a blank widget placeholder for the visualization for now
        input_vis_widget = QtWidgets.QWidget()
        controls_layout.addWidget(input_vis_widget)

        io_layout.addLayout(controls_layout)


        # this main/larger layout holds all the subwidgets and in some cases other layouts
        main_layout = QtWidgets.QGridLayout()
        # main_layout.addLayout(audiocue_layout, 0, 0, 3, 2)
        main_layout.addLayout(cueSelectionLayout, 0, 0, 2, 2)
        main_layout.addLayout(extra_layout, 3, 0, 1, 2)
        main_layout.addLayout(viewer_layout, 0, 2, 2, 1)
        main_layout.addLayout(io_layout, 2, 2, 2, 1)
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

    def changeOutputVolume(self, value):
        # pyqt sliders only take integers but range is 0-1
        # self.volume = value / 100
        float_volume = value / 100
        for player in self.playables.values():
            player.setVolume(float_volume)
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
