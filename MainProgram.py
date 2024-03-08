# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# Program which handles the main sending/ receiving of messages

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys 
import SenderThread
import ReceiverThread
import psutil
from pathlib import Path
import os
import time
import webbrowser
import pathlib

#Config pop up
class ConfigWindow(QDialog):
    def __init__(self, speedUpFactor, fakeCpu):
        self.onTime = 1.0
        self.repeats = 2
        self.limiter = 0
        self.mechanism = 0
        self.speedUpFactor = speedUpFactor
        self.fakeCpu = fakeCpu
        
        if(self.fakeCpu):
            #Speed things up when testing
            self.onTime = self.onTime / self.speedUpFactor
        
        super().__init__()
        
        #Icon for window
        pixmap = QPixmap()
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/icon.png"
        pixmap.loadFromData( Path(iconFilePath).read_bytes() )
        appIcon = QIcon(pixmap)
        self.setWindowIcon(appIcon)
        
        #Title and setup
        self.setWindowTitle("Settings")
        self.setStyleSheet("font-size: 15pt;")
        layout = QVBoxLayout()
        
        #Label for dropdown
        self.comboboxLabel = QLabel("Sending/Receiving Mechanism") 
        layout.addWidget(self.comboboxLabel)
        
        #Drop down to select sending mechanism 
        self.combobox = QComboBox()
        self.combobox.addItems(['Single core', 'Memory', 'Disk', 'Multi-core average', 'Multi-core speed', 'UDP Packet'])
        layout.addWidget(self.combobox)
        self.combobox.currentIndexChanged.connect(self.mechanismChanged)
        
        #Slider to control pulse time
        self.onTimeSL = QSlider(Qt.Horizontal)
        self.onTimeSL.setRange(2, 52)
        self.onTimeSL.setValue(10)
        self.onTimeSL.setSingleStep(5)
        self.onTimeSL.setPageStep(10)
        self.onTimeSL.setTickPosition(QSlider.TicksBelow)
        self.onTimeSL.setTickInterval(10)
        layout.addWidget(self.onTimeSL)
        self.onTimeSL.valueChanged.connect(self.updatePulseTime)
        
        #Text to show the pulse time
        self.pulseTimeLabel = QLabel('Current Pulse time: 1 seconds')
        layout.addWidget(self.pulseTimeLabel)
        
        #Slider to control number of repeats
        self.repeatSL = QSlider(Qt.Horizontal)
        self.repeatSL.setRange(1, 3)
        self.repeatSL.setValue(1)
        self.repeatSL.setSingleStep(1)
        self.repeatSL.setPageStep(1)
        self.repeatSL.setTickPosition(QSlider.TicksBelow)
        self.repeatSL.setTickInterval(1)
        layout.addWidget(self.repeatSL)
        self.repeatSL.valueChanged.connect(self.updateRepeats)
        
        #Text to show the number of repeats
        self.repeatsLabel = QLabel('Current number of repeats: 1')
        layout.addWidget(self.repeatsLabel)
        
        #Slider to control percentage limiting
        self.limitSL = QSlider(Qt.Horizontal)
        self.limitSL.setRange(10, 100)
        self.limitSL.setValue(100)
        self.limitSL.setSingleStep(10)
        self.limitSL.setPageStep(10)
        self.limitSL.setTickPosition(QSlider.TicksBelow)
        self.limitSL.setTickInterval(10)
        layout.addWidget(self.limitSL)
        self.limitSL.valueChanged.connect(self.updateLimiter)
        
        #Text to show the number of repeats
        self.limitLabel = QLabel('Limiting CPU to: 100%')
        layout.addWidget(self.limitLabel)
        
        #Save changes button
        self.saveButton = QPushButton("Save Changes")
        self.saveButton.clicked.connect(self.saveChanges)
        layout.addWidget(self.saveButton)
        
        #layout.addWidget(self.label)
        self.setLayout(layout)
        
    #Update text for onTime slider
    def updatePulseTime(self, value):
        self.pulseTimeLabel.setText(f'Current Pulse time: {value/10} seconds')
        self.onTime = value/10
        if(self.fakeCpu):
            #Speed things up when testing
            self.onTime = self.onTime / self.speedUpFactor
    
     #Update text for repeats slider
    def updateRepeats(self, value):
        self.repeatsLabel.setText(f'Current number of repeats: {value}')
        self.repeats = value + 1
        
    #Update text for limiter slider
    def updateLimiter(self, value):
        self.limitLabel.setText(f'Limiting CPU to: {value}%')
        self.limiter = 100-value
        
    #Set index to match change 
    def mechanismChanged(self):
        self.mechanism = self.combobox.currentIndex()
    
    #Close the window down
    def saveChanges(self):
        self.close()

#Main GUI element
class Window(QMainWindow): 
    def __init__(self): 
        #Default values
        self.onTime = 1.0
        self.coreToUse = 1
        self.changeMessageBox = False
        self.machineOne = False
        self.message = ""
        self.repeats = 2
        self.fakeCpu = False
        self.limiter = 0
        self.speedUpFactor = 1
        self.fileUploaded = False
        self.mechanism = 0
        self.configActive = False
        self.messageLog = []
        
        if(self.fakeCpu):
            #Speed things up when testing
            self.onTime = self.onTime / self.speedUpFactor
        
        super().__init__() 
        self.setGeometry(0, 0, 400, 550)
        self.setStyleSheet("font-size: 15pt;")
        
        #Set Icon
        pixmap = QPixmap()
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/icon.png"
        pixmap.loadFromData( Path(iconFilePath).read_bytes() )
        appIcon = QIcon(pixmap)
        self.setWindowIcon(appIcon)
        
        #Set Title
        self.setWindowTitle("Covert Channel GUI")
        
        # Create a toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Add actions to the toolbar
        # Settings button
        self.settingsAction = QAction(self)
        self.settingsAction.setText("Config")
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/settings.png"
        pixmap.loadFromData( Path(iconFilePath).read_bytes() )
        self.settingsAction.setIcon(QIcon(pixmap))
        toolbar.addAction(self.settingsAction)
        self.settingsAction.triggered.connect(self.openCloseConfig)

        # Add a separator
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Help button
        self.helpAction = QAction(self)
        self.helpAction.setText("Help")
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/help-circle.png"
        pixmap.loadFromData( Path(iconFilePath).read_bytes() )
        self.helpAction.setIcon(QIcon(pixmap))
        toolbar.addAction(self.helpAction)
        self.helpAction.triggered.connect(self.openHelp)
        
        #Create popup window
        self.configWindow = ConfigWindow(self.speedUpFactor, self.fakeCpu)
        
        #Text to indicate sync message is being sent
        self.sendingText = QLabel("Not sending sync pulse", self) 
        self.sendingText.setGeometry(180, 65, 500, 50) 

        #Text to show received messages
        self.messageText = QLabel("Not listening", self) 
        self.messageText.setGeometry(20, 65, 500, 50) 
        
        #Text to show connected message
        self.connectedMessage = QLabel("", self) 
        self.connectedMessage.setGeometry(20, 140, 500, 50) 
        
        #Text to show connected message
        self.LEDGuide = QLabel("", self) 
        self.LEDGuide.setGeometry(45, 80, 100, 100) 
        self.LEDGuide.setVisible(False)
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/cpu.png"
        pixmap.loadFromData( Path(iconFilePath).read_bytes() )
        self.LEDGuide.setPixmap(pixmap)
                
        #Color box to indicate whether the usage is "on" or "off" (red/green respectively)
        self.colorBox = QLabel(self) 
        self.colorBox.setGeometry(200, 120, 40, 40) 
        self.colorBox.setStyleSheet("background-color : green;")     
        self.colorBox.setVisible(False)
        
        #Binary indicator
        self.colorBoxIndicator = QLabel("0", self)
        self.colorBoxIndicator.setGeometry(212, 120, 40, 40)
        self.colorBoxIndicator.setStyleSheet("font-size: 20pt; color: white")
        self.colorBoxIndicator.setVisible(False)
        
        #Box to see messages sent/received
        self.widget = QWidget()                 
        self.widget.setFixedWidth(360)
        self.widget.setStyleSheet("background:white")
        
        self.vbox = QVBoxLayout()               
        self.vbox.addStretch()
        self.vbox.setSpacing(2)
        
        #Add the horizontal layout to the widget
        self.widget.setLayout(self.vbox)
        
        #Main message box
        self.mainMessageBoxScroll = QScrollArea(self)
        self.mainMessageBoxScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mainMessageBoxScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mainMessageBoxScroll.setWidget(self.widget)
        self.mainMessageBoxScroll.move(20, 190)
        self.mainMessageBoxScroll.resize(360,300)
        self.mainMessageBoxScroll.setWidgetResizable(True)
        self.vscrollbar = self.mainMessageBoxScroll.verticalScrollBar()
        self.vscrollbar.rangeChanged.connect(self.scrollToBottom)
        self.mainMessageBoxScroll.setVisible(False)
        self.mainMessageBoxScroll.setStyleSheet("border: 1px solid black; border-bottom: none")
       
        #Bit of empty space under the message box
        self.emptySpace = QLabel("", self)
        self.emptySpace.setGeometry(20, 490, 360, 40)
        self.emptySpace.setStyleSheet("background: white; border: 1px solid black; border-top: none")
        self.emptySpace.setVisible(False)
        
        #Background for the message sending section
        self.messageBackground = QLabel("", self)
        self.messageBackground.setGeometry(25, 490, 350, 30)
        self.messageBackground.setStyleSheet("background: #e1e2e3; border: 1rem black; border-radius: 15px;")
        self.messageBackground.setVisible(False)
        
        #Box to type custom message to send
        self.messageTextbox = QLineEdit(self, placeholderText="Enter message to send here")
        self.messageTextbox.setStyleSheet("background: #e1e2e3; border: 1rem black; border-radius: 15px;")
        self.messageTextbox.move(40, 490)
        self.messageTextbox.setFrame(False)
        self.messageTextbox.resize(280,30)
        self.messageTextbox.setVisible(False)
        
        #Button to upload files
        self.fileUploadButton = QPushButton("", self)
        self.fileUploadButton.clicked.connect(self.getfiles)
        self.fileUploadButton.setGeometry(310, 490, 30, 30)
        pixmapProfileIcon = QPixmap()
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/upload-square.png"
        pixmapProfileIcon.loadFromData( Path(iconFilePath).read_bytes() )
        self.fileUploadButton.setIcon(QIcon(pixmapProfileIcon))
        self.fileUploadButton.setStyleSheet("border:none;")
        self.fileUploadButton.setVisible(False)
		
        #Button to send message
        self.sendMessageButton = QPushButton('', self)
        self.sendMessageButton.setGeometry(340, 490, 30, 30)
        iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/send.png"
        pixmapProfileIcon.loadFromData( Path(iconFilePath).read_bytes() )
        self.sendMessageButton.setIcon(QIcon(pixmapProfileIcon))
        self.sendMessageButton.setStyleSheet("border:none;")
        self.sendMessageButton.setVisible(False)
        
        #Progress bar for sending message
        self.progress = QProgressBar(self)
        self.progress.setGeometry(200, 120, 150, 20)
        self.progress.setAlignment(Qt.AlignCenter) 
        self.progress.setVisible(False)
        
        #Text to indicate message is being sent
        self.messageSendingText = QLabel("", self) 
        self.messageSendingText.setGeometry(200, 80, 500, 50) 
        
        #Button to start listening for sync pulse
        self.receiveMessage = QPushButton('Listen', self)
        self.receiveMessage.move(10, 50)
        self.receiveMessage.clicked.connect(self.startListeningForMessage)
        
        #Button to send sync pulse
        self.sendSyncButton = QPushButton('Send Pulse', self)
        self.sendSyncButton.setGeometry(180, 50, 150, 30)
        self.sendSyncButton.clicked.connect(self.sendSync)

        #Resets to a known state
        try:
            os.remove("new.txt") 
        except:
            pass

        self.show()
        
    #Update scroller when message happens
    def scrollToBottom(self, minimum, maximum):
        self.vscrollbar.setValue(maximum) 

    def mechanismChanged(self):
        #Creates listener if one not already made
        try:
            #This runs if messageListener already exists
            if(self.messageListener.active == True):
                self.messageListener.stop()
                self.messageListener = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=self.coreToUse, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
                self.messageListener.zeroOrOne.connect(self.updateLED)
                self.messageListener.message.connect(self.updateMessage)
                self.messageListener.currentlyReceiving.connect(self.controlSender)
                self.messageListener.start()
        except AttributeError:
            self.messageListener = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=self.coreToUse, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
            self.messageListener.zeroOrOne.connect(self.updateLED)
            self.messageListener.message.connect(self.updateMessage)
            self.messageListener.currentlyReceiving.connect(self.controlSender)
            self.messageListener.start()
            
        self.switchMethodIcon()

    #Function to call thread to send message from the text box
    def sendMessage(self):
        #Before sending - check if core is already busy (we might have a message coming in!)
        if(self.mechanism == 0):
            currentCpuUsage = psutil.cpu_percent(interval=0.5, percpu=True)[self.coreToUse]
            if(currentCpuUsage > 70):
                print("SIGNAL BUSY") #CHANGE
                return
        
        #Hide buttons
        self.sendMessageButton.setVisible(False)
        self.fileUploadButton.setVisible(False)
        
        #Converts message to array of binary
        if(self.fileUploaded == False):
            self.message = self.messageTextbox.text()
        
        #Cant send nothing
        if(self.message == ""):
            return
        
        #Preps message for sending
        if(self.mechanism != 5):
            message = [*''.join('{0:08b}'.format(ord(x), 'b') for x in self.message)]
        else:
            message = self.message
            
        #Creates threads
        self.messenger = SenderThread.SendMessageThread(parent=self, message=message, onTime=self.onTime, coreToUse=self.coreToUse, machineOne=self.machineOne, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
        self.messenger.start()
        self.messenger.finished.connect(self.finishedSendingMessage)
        self.messenger.killReceiver.connect(self.killReceiver)
        self.messenger.sendingUpdate.connect(self.updateSenderText)
        self.messageSendingText.setText("Sending...")
        self.progress.setVisible(True)
        
        #Deactivates certain options
        self.fileUploaded = False
        self.configActive = False
        
    #Updates the percent complete text
    def updateSenderText(self, sendingUpdate):
        self.progress.setValue(round(sendingUpdate*100))
    
    #Kills the thread
    def killReceiver(self):
        self.messageListener.stop()
    
    #Function to call thread to send sync pulse
    def sendSync(self):
        self.messenger = SenderThread.SendMessageThread(parent=self, message=["sync"], onTime=self.onTime, coreToUse=self.coreToUse, machineOne=self.machineOne, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
        self.messenger.start()
        self.messenger.finished.connect(self.finishedSendingMessage)
        self.messenger.core.connect(self.updateCoreNumber)
        self.sendingText.setText("Sending...") #Gives visual feedback on whats happening
        
    #Updates visual feedback
    def finishedSendingMessage(self, firstPass):
        self.messenger.stop()
        self.progress.setVisible(False)
        self.progress.setValue(0)
        self.configActive = True

        if(firstPass):
            self.configActive = True
            self.machineOne = True
            self.sendMessageButton.clicked.connect(self.sendMessage)
            
            #Hides elements
            self.messageText.setGeometry(20, 25, 0, 0)
            self.sendSyncButton.setGeometry(20, 25, 0, 0) 
            self.receiveMessage.setGeometry(20, 25, 0, 0) 
            
            #Makes elements visible 
            self.messageTextbox.setVisible(True)
            self.mainMessageBoxScroll.setVisible(True)
            self.emptySpace.setVisible(True)
            self.messageBackground.setVisible(True)
            self.LEDGuide.setVisible(True)
            self.fileUploadButton.setVisible(True)
            
            #Update text to indicate connection is made
            self.connectedMessage.setText('Method Selected:')
            self.connectedMessage.setGeometry(20, 40, 500, 50) 
            self.sendingText.setText("")
            
            self.updateLED(0)
            self.changeMessageBox = True
            
        #Creates listener if one not already made
        try:
            #This runs if message has been sent successfully
            if(self.messageListener.active == False):
                #Updates the messagebox indicating it has been sent
                self.addMessage(True, str(self.message))
                self.updateLED(0)
                
                self.messageSendingText.setText("")
        
                self.messageListener = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=self.coreToUse, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
                self.messageListener.zeroOrOne.connect(self.updateLED)
                self.messageListener.message.connect(self.updateMessage)
                self.messageListener.currentlyReceiving.connect(self.controlSender)
                self.messageListener.start()
                
                if(self.mechanism == 5):
                    time.sleep(1)
                
                self.sendMessageButton.setVisible(True)
                self.fileUploadButton.setVisible(True)
        except AttributeError: 
            self.messageSendingText.setText("Channel busy")
            
            self.messageListener = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=self.coreToUse, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
            self.messageListener.zeroOrOne.connect(self.updateLED)
            self.messageListener.message.connect(self.updateMessage)
            self.messageListener.currentlyReceiving.connect(self.controlSender)
            self.messageListener.start()
            
            if(self.mechanism == 5):
                time.sleep(1)
            
            self.sendMessageButton.setVisible(True)
            self.fileUploadButton.setVisible(True)
        
    #Function to start listening for a message
    def startListeningForMessage(self):
        self.messageListener = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=True, coreToUse=self.coreToUse, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
        self.messageListener.zeroOrOne.connect(self.updateLED)
        self.messageListener.message.connect(self.updateMessage)
        self.messageListener.core.connect(self.updateCoreNumber)
        self.messageText.setText("Listening...")
        self.messageListener.currentlyReceiving.connect(self.controlSender)
        self.messageListener.start()
        
    #Function to update core selected number
    def updateCoreNumber(self, core):
        self.coreToUse = core
            
    #Function to update the data on the GUI for the received message
    def updateMessage(self, message):
        if(self.configActive):
            if(self.changeMessageBox):
                self.addMessage(False, str(message))
            else:
                self.addMessage(False, str(message))
            self.updateLED(0)
        else:
            if(str(message) != "Connected to second PC"):
                self.connectedMessage.setText(str(message))
        if(str(message) == "Connected to second PC"):
            self.connectedMessage.setText("Method Selected:")
            self.connectedMessage.setGeometry(20, 40, 500, 50) 
            self.sendingText.setText("")
            
            #We have synced the two channels
            #Hides elements
            self.configActive = True
            self.messageText.setGeometry(20, 25, 0, 0)
            self.sendSyncButton.setGeometry(20, 25, 0, 0) 
            self.sendingText.setGeometry(20, 25, 0, 0) 
            self.receiveMessage.setGeometry(20, 25, 0, 0) 
            
            #Makes elements visible 
            self.messageTextbox.setVisible(True)
            self.sendMessageButton.setVisible(True)
            self.mainMessageBoxScroll.setVisible(True)
            self.emptySpace.setVisible(True)
            self.messageBackground.setVisible(True)
            self.fileUploadButton.setVisible(True)
            self.LEDGuide.setVisible(True)
            
            self.messageSendingText.setText("")
            
            self.messageListener.stop()
            self.sendMessageButton.clicked.connect(self.sendMessage)
            self.messageListener = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=self.coreToUse, mechanism=self.mechanism, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter)
            self.messageListener.message.connect(self.updateMessage)
            self.messageListener.currentlyReceiving.connect(self.controlSender)
            self.messageListener.start()
            
            self.changeMessageBox = True
        
    #Function to control the ability to send messages when receiving them
    def controlSender(self, currentlyReceiving):
        if(currentlyReceiving):
            self.sendMessageButton.setVisible(False)
            self.fileUploadButton.setVisible(False)
            self.messageSendingText.setText("Receiving...")
            self.colorBox.setVisible(True)
            self.colorBoxIndicator.setVisible(True)
            self.configActive = False
            try:
                self.messenger.active = False
            except:
                pass
        else:
            self.sendMessageButton.setVisible(True)
            self.fileUploadButton.setVisible(True)
            self.messageSendingText.setText("")
            self.colorBox.setVisible(False)
            self.colorBoxIndicator.setVisible(False)
            self.configActive = True
            try:
                self.messenger.active = True
            except:
                pass
            
    def addMessage(self, sender, message):
        container = QHBoxLayout()
            
        #Each row has an object in e.g. the message
        object = QLabel() 
        
        #Handles the word wrapping nicely
        object.setWordWrap(True)
        fm = QFontMetrics(self.font())
        width = fm.width(message) + 20
        if width < 200:
            object.setFixedWidth(width)
        else:
            object.setFixedWidth(200)
        object.setText(message)
        object.setMaximumWidth(200)
            
        if(sender):
            #Right side
            object.setStyleSheet('background:#56a1e8; border: 1rem black; border-radius: 13px; padding-left: 5px; padding-right: 5px; padding-top: 2px; padding-bottom: 5px')
            container.addStretch()
            #Checks if the message above was from another person, if so adds a bit of space between
            if(len(self.messageLog) > 0):
                if(self.messageLog[len(self.messageLog) -1] == 0):
                    print("different right")
                    self.vbox.addSpacing(10)
                else:
                    print("same right")
                    prevLayout = self.vbox.itemAt(self.vbox.count()-1).layout()
                    prevLayout.itemAt(1).widget().setStyleSheet( prevLayout.itemAt(1).widget().styleSheet() + "; border-bottom-right-radius: 0px")
                    object.setStyleSheet(object.styleSheet() + "; border-top-right-radius: 0px")

            self.messageLog.append(1)
            container.addWidget(object)
            self.vbox.addLayout(container)
        else:
            #Left side
            object.setStyleSheet('background:#bfbfbf; border: 1rem black; border-radius: 13px; padding-left: 5px; padding-right: 5px; padding-top: 2px; padding-bottom: 5px')
            pixmapProfileIcon = QPixmap()
            iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/profile-circle.png"
            pixmapProfileIcon.loadFromData( Path(iconFilePath).read_bytes() )

            if(len(self.messageLog) > 0):
                if(self.messageLog[len(self.messageLog) -1] == 1):
                    print("different left")
                    self.vbox.addSpacing(10)
                    profileIcon = QLabel("")
                    profileIcon.setPixmap(pixmapProfileIcon)
                    profileIcon.setStyleSheet("border:none;")
                    container.addWidget(profileIcon)
                else:
                    print("same left")
                    prevLayout = self.vbox.itemAt(self.vbox.count()-1).layout()
                    prevLayout.itemAt(1).widget().setStyleSheet( prevLayout.itemAt(1).widget().styleSheet() + "; border-bottom-left-radius: 0px")
                    object.setStyleSheet(object.styleSheet() + "; border-top-left-radius: 0px")
                    iconToRemove = prevLayout.itemAt(0)
                    prevLayout.removeItem(iconToRemove)
                    iconToRemove.widget().deleteLater()
                    prevLayout.insertSpacing(0, 52)
                    profileIcon = QLabel("")
                    profileIcon.setPixmap(pixmapProfileIcon)
                    profileIcon.setStyleSheet("border:none;")
                    container.addWidget(profileIcon)
            else:
                print("initial")
                profileIcon = QLabel("")
                profileIcon.setPixmap(pixmapProfileIcon)
                profileIcon.setStyleSheet("border:none;")
                container.addWidget(profileIcon)
            
            self.messageLog.append(0)
            container.addWidget(object)
            container.addStretch()
            self.vbox.addLayout(container)
            
    #Updates the green/red "LED" indicators color
    def updateLED(self, value):
        if(value == 0):
            self.colorBox.setStyleSheet("background-color : green;")
            self.colorBoxIndicator.setText("0")
        else:
            self.colorBox.setStyleSheet("background-color : red;")
            self.colorBoxIndicator.setText("1")
            
    #Allows user to pick a file to send
    def getfiles(self):
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.AnyFile)
		
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            f = open(filenames[0], 'r')

            self.messageSendingText.setText("Loaded file: " +os.path.basename(filenames[0]))
   
            with f:
                try:
                    data = f.read()
                    self.fileUploaded = True
                    self.message = data
                except UnicodeDecodeError:
                    self.messageSendingText.setText("File not in correct format!")
    
    #Opens the README
    def openHelp(self):
        url = "https://github.com/tomro1/capstone" 

        webbrowser.open(url)

    #Controls the opening and closing of the settings window
    def openCloseConfig(self):
        if(self.configActive):
            self.configWindow.exec_()
            self.onTime = self.configWindow.onTime
            self.mechanism = self.configWindow.mechanism
            self.repeats = self.configWindow.repeats
            self.limiter = self.configWindow.limiter
            self.mechanismChanged()
            
    #Sends message on enter key
    def keyPressEvent(self, qKeyEvent):
        if qKeyEvent.key() == Qt.Key_Return: 
            if(self.sendMessageButton.isVisible() == True):
                self.sendMessage()
        else:
            super().keyPressEvent(qKeyEvent)
            
    #Changes Icon depending on which method is selected
    def switchMethodIcon(self):
        pixmap = QPixmap()
        if(self.mechanism == 0 or self.mechanism==3 or self.mechanism == 4):
            #cpu
            iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/cpu.png"
        elif(self.mechanism == 1):
            #mem
            iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/ram.png"
        elif(self.mechanism == 2):
            #disk
            iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/disk.png"
        elif(self.mechanism == 5):
            #udp
            iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/udp.png"
        else:
            #error 
            iconFilePath = str(pathlib.Path(__file__).parent.resolve()) + "/Icons/prohibition.png"
        pixmap.loadFromData( Path(iconFilePath).read_bytes() )
        self.LEDGuide.setPixmap(pixmap)
        
#Stops function from re-calling itself during threading
if __name__ == "__main__":
    app = QApplication([])
    window = Window()
    sys.exit(app.exec()) 
    