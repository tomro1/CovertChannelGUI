# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# DO NOT RUN directly. This thread is ran by MainProgram.py when needed

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import psutil
import time
import re
import socket
import json
import math
import os

#Class to listen for message
class ListenForMessageThread(QThread):
    #Outputs back to main thread
    message = pyqtSignal(str)
    core = pyqtSignal(int)
    currentlyReceiving = pyqtSignal(bool)
    debuggingMessage = pyqtSignal(list)
    zeroOrOne = pyqtSignal(int)

    #Setup function
    def __init__(self, parent, onTime, sync, coreToUse, mechanism, repeats, fakeCpu, limiter, debugging=False, messageLength=-1, folderToUse='/'):
        QThread.__init__(self, parent)
        self.coreToUse = coreToUse
        self.active = True
        self.onTime = onTime #Needs to be synced with the sender
        self.firstPulseRecorded = False
        self.startPoint = -1
        self.pulseCounter = 0
        self.receivedMessage = ''
        self.folderToUse = folderToUse
        self.count = 0
        self.sync = sync
        self.mechanism = mechanism #0 - CPU, 1 - Memory, etc
        self.repeats = repeats
        self.fakeCpu = fakeCpu
        self.limiter = limiter
        self.debugging = debugging 
        self.threshold = (100-self.limiter) * 0.8 #slightly under the limit
        
        if(self.debugging):
            self.timeOut = time.time() + 30 + (repeats+2) * 8 * onTime + (messageLength * onTime) * repeats
        else:
            self.timeOut = time.time() + 60 * 60 * 24 #One day
        
        if(self.fakeCpu):
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.connect(('localhost', 20000))
        
        #Bind to a different core to avoid interference when listening
        if(self.mechanism == 0):
            p = psutil.Process()
            try:
                p.cpu_affinity([self.coreToUse+1])
            except:
                p.cpu_affinity([self.coreToUse-1]) 
                
        if(self.mechanism == 3 or self.mechanism == 4):
            p = psutil.Process()
            p.cpu_affinity([0])
        
        if(self.debugging == False):
            print("Receiver thread created")

    #Function that handles the startup of the thread, changing depending on whether we want to sync or not
    def run(self):
        if(self.fakeCpu):
            request = "p" + str(self.onTime)
            self.server.send(request.encode('utf8'))
            time.sleep(1)
        
        if(self.sync):
            self.listenForSync()
        else:
            self.currentlyReceiving.emit(False)
            self.switchBasedOnMechanism()

    #Function to listen for the initial sync pulse on all cores
    def listenForSync(self):
        #Sets up arrays for all cores
        numCores = psutil.cpu_count()
        totalCpuUsage = []
        logicalTracker = []
        running = True

        for i in range(numCores):
            totalCpuUsage.append("")
            logicalTracker.append("")

        while running:
            
            if(self.fakeCpu):
                time.sleep(1/5)
            #Sample CPU usage for all cores
            currentCpuUsage = self.getCpuPercent("sync")
            
            #Monitor all cores for the pattern listed
            for i in range(numCores):
                if(currentCpuUsage[i] > 50):
                    totalCpuUsage[i] += "1"
                else:
                    totalCpuUsage[i] += "0"
                    
                if(re.search(".*111.*", totalCpuUsage[i])):
                    logicalTracker[i] += "1"
                    totalCpuUsage[i] = ""
                elif(re.search(".*000.*", totalCpuUsage[i])):
                    logicalTracker[i] += "0"
                    totalCpuUsage[i] = ""
                
                #If our strings are getting a bit long, cut them shorter 
                if(len(logicalTracker[i]) == 15):
                    logicalTracker[i] = logicalTracker[i][-12:]
                
                #If we have found the sync pattern
                if(re.search("1010101", logicalTracker[i])):
                    #Debug 
                    if(self.debugging == False):
                        print("FOUND")
                        print(i)
                        print(totalCpuUsage)
                    
                    running = False
                    
                    #Show to the user what's going on
                    self.message.emit("Found signal on core "+str(i))
                    self.coreToUse = i
                    self.sendSync()
                    
                    #Send back to main thread
                    self.core.emit(i)
                    break  
    
    #Function to sit and listen for the confirmation pulse
    def listenForConfirmation(self):
        #Bind to a different core to avoid interference when listening
        p = psutil.Process()
        try:
            p.cpu_affinity([self.coreToUse+1])
        except:
            p.cpu_affinity([self.coreToUse-1]) 
        
        t_start = time.perf_counter()
        totalCpuUsage = ""
        logicalTracker = ""
        running = True

        while running:
            if(self.fakeCpu):
                time.sleep(1/5)
            #Sample CPU usage
            currentCpuUsage = self.getCpuPercent("sync")[self.coreToUse]
            
            if(currentCpuUsage > 50):
                totalCpuUsage += "1"
            else:
                totalCpuUsage += "0"
                
            if(re.search(".*111.*", totalCpuUsage)):
                logicalTracker += "1"
                totalCpuUsage = ""
            elif(re.search(".*000.*", totalCpuUsage)):
                logicalTracker += "0"
                totalCpuUsage = ""
            
            #If our strings are getting a bit long, cut them shorter 
            if(len(logicalTracker) == 15):
                logicalTracker = logicalTracker[-12:]
            
            #If we have found the sync pattern
            if(re.search("101", logicalTracker)):   
                #Tell the main thread which core again, and confirm the connection has been made
                print("FOUND CONFIRMATION")
                running = False
                self.core.emit(self.coreToUse)
                self.message.emit("Connected to second PC")
                break
            
            #We haven't received confirmation in time so restart protocol
            if(time.perf_counter() > (t_start + self.onTime * 7)):
                running = False
                print("NOT FOUND")
                self.listenForSync() 
                break

    #Modulate to send a sync message 
    def sendSync(self):
        self.count = 0
        
         #Small pause between resending pulse
        time.sleep(self.onTime * 4)
        syncWord = ['1', '0', '1', '0', '1', '0', '1', '0'] 
        
        #Syncs with the clock
        message = syncWord
        if(self.onTime < 1):
            while round(time.time(),2) % 1 != 0: #Sync with the clock
                pass
        else:
            while round(time.time(),2) % self.onTime != 0: #Sync with the clock
                pass
            
        self.startPoint = time.perf_counter()
        
        #Assigns to the correct core
        p = psutil.Process()
        p.cpu_affinity([self.coreToUse]) 
        
        #Sends message
        for binary in message:
            #Adjustment to ensure sync remains throughout sending
            self.adjustmentFactor = (time.perf_counter() - self.startPoint - (self.onTime*(self.count))) * 1.5
            self.count += 1
            
            #Used to ensure sync when testing
            print(time.time()) 
            if binary == '1':
                #Sends a pulse (1)
                print("sending pulse")
                
                #Ramps up for remaining of pulse left
                if(self.fakeCpu):
                    self.sendValueViaFakeCpu(100, 0, self.coreToUse)
                    if(self.onTime - self.adjustmentFactor) > 0:
                        time.sleep(self.onTime - self.adjustmentFactor)
                else:
                    t_end = time.perf_counter() + self.onTime - self.adjustmentFactor 
                    while time.perf_counter() < t_end:
                        pass
            elif binary == '0':
                if(self.fakeCpu):
                    self.sendValueViaFakeCpu(0, 0, self.coreToUse)
                    t_end = time.time() + self.onTime - self.adjustmentFactor
                    while(time.time() < t_end):
                        sleepTime = (t_end - time.time())*0.05
                        if(sleepTime > 0):
                            time.sleep(sleepTime)
                else:
                    t_end = time.time() + self.onTime - self.adjustmentFactor
                    while(time.time() < t_end):
                        sleepTime = (t_end - time.time())*0.05
                        if(sleepTime > 0):
                            time.sleep(sleepTime)
            else:
                print("Error - incorrect format") #Not a 1 or 0
         
        #Now we listen for confirmation
        self.listenForConfirmation()

    #"Send" the value using the fakeCPU instead of the real one
    def sendValueViaFakeCpu(self, value, mechanism, coreToUse):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.connect(('localhost', 20000))
        if(mechanism == 4):
            request = str(str(coreToUse) + str("s") + str(value))
        else:
            request = str(str("u") + str(value))
        server.send(request.encode('utf8'))

    #Controls which function to run based on the mechanism or method selected
    def switchBasedOnMechanism(self):
        if(self.mechanism == 0 or self.mechanism == 3 or self.mechanism == 4):
            self.syncMessages()
        elif(self.mechanism == 1):
            self.receiveMessageMemory()
        elif(self.mechanism == 2):
            self.receiveMessageDisk()
        elif(self.mechanism == 5):
            self.receiveMessageUDP()

    #Function to sync the receiver to the sender based on the 1111111 pulse
    def syncMessages(self):
        while self.active:
            if(self.firstPulseRecorded == False and time.time() > self.timeOut):
                self.debuggingMessage.emit([])
                break
            #Sample CPU usage
            if(self.mechanism == 0):
                currentCpuUsage = self.getCpuPercent("sync")[self.coreToUse]
            elif(self.mechanism == 3 or self.mechanism == 4):
                value = self.getCpuPercent("sync")[-1:]
                currentCpuUsage = sum(value) / len(value) 
            #If haven't started recording yet and receive a first pulse
            if(currentCpuUsage > self.threshold):
                if(self.firstPulseRecorded == False):
                    #Stops ability to send message
                    self.currentlyReceiving.emit(True)
                    
                    #Rounds down to find the intended sending pulse
                    self.startPoint = math.floor(time.time()) #Only for a pulse width of 1
                    self.firstPulseRecorded = True
                    if(self.debugging == False): 
                        print(self.startPoint)
                #If we have recorded a cpu usage of above 90 for 8 cycles (7 for bit of leeway)
                if(time.time() - self.startPoint >= self.onTime * 7):
                    if(self.debugging == False): 
                        print("recording")
                    self.receiveMessageCPU()
                    break
            else:
                self.firstPulseRecorded = False

    #Functions to receive a full message based on mechanism
    def receiveMessageCPU(self):
        #Have received our start sequence so properly start recording message  
        message = []
        self.pulseCounter = 0
        self.receivedMessage = ''
        repeatCount = 0
        totalMessage = []
        checksumRecording = False
        errorDetected = False
        entireMessage = ['1','1','1','1','1','1','1', '1']
        
        #Ensures sync with the clock and with each other
        while(time.time() < self.startPoint + self.onTime * 8):
            time.sleep(0.001)
    
        #Indefinitely
        while self.active:
            if(time.time() > self.timeOut):
                self.debuggingMessage.emit(totalMessage)
                break
            
            startPoint = time.perf_counter()
            if(self.debugging == False):
                print("r-", str(time.time()))
            
            if(self.mechanism == 4):
                self.pulseCounter += psutil.cpu_count()-1
            else:
                self.pulseCounter += 1
            
            #Sleep for initial quarter of pulse to avoid ramping portion
            time.sleep(self.onTime/4)
            
            t_end = time.perf_counter() + self.onTime/2
            
            currentCpuUsage = []
            
            if(self.mechanism == 0 or self.mechanism == 3):
                currentCpuUsage.append(0)
            else:
                for i in range(psutil.cpu_count() -1):
                    currentCpuUsage.append(0)
                
            count = 0
            #Calculate an average of the cpu usage over this central onTime/2 window
            while time.perf_counter() < t_end:
                #Sample CPU usage
                if(self.mechanism == 0):
                    currentCpuUsage[0] = currentCpuUsage[0] + self.getCpuPercent("poll")[self.coreToUse] 
                elif(self.mechanism == 3):
                    value = self.getCpuPercent("poll")[1:]
                    currentCpuUsage[0] = currentCpuUsage[0] + (sum(value) / len(value))
                elif(self.mechanism == 4):
                    value = self.getCpuPercent("poll")
                    for i in range(len(currentCpuUsage)):
                        currentCpuUsage[i] = currentCpuUsage[i] + value[i+1]
                count += 1
            
            if(count == 0):
                print("ERROR: Sampler couldn't keep up!!")
                self.debuggingMessage.emit(entireMessage)
                self.message.emit("Error receiving")
                self.currentlyReceiving.emit(False)
                self.syncMessages()
                
            #Calculate average CPU usage
            for i in range(len(currentCpuUsage)):
                averageCpuUsage = currentCpuUsage[i] / count
                if(self.debugging == False):
                    print(averageCpuUsage)
                
                #Calculate binary equivalent
                if(averageCpuUsage >= self.threshold):
                    message.append(1)
                    self.zeroOrOne.emit(1)
                elif(averageCpuUsage < self.threshold):
                    message.append(0)
                    self.zeroOrOne.emit(0)
                else: #Error
                    print("ERROR2")
                
            #We have received a whole character 
            while(self.pulseCounter >= 8):
                total = 0
                
                #Convert binary to decimal
                for i in range(8):
                    total += message[i] * 2**(7-i)
                if(total == 255): #We have reached the end of our message
                    repeatCount += 1
                    if(self.debugging == False):
                        print("REPEAT COUNT IS " + str(repeatCount))
                    #We have reached the end of all our repeats
                    if(repeatCount == self.repeats):
                        for value in message[:8]:
                            entireMessage += str(value)
                        if(self.debugging == False): 
                            print("done")
                        if(self.debugging == False):
                            print(totalMessage)
                        self.calculateAverageMessage(totalMessage=totalMessage)
                        time.sleep(1) #Small sleep to stop accidentally listening to same message
                        self.syncMessages()
                        break
                    
                    #We are now recording the checksum
                    if(repeatCount == self.repeats -1):
                        checksumRecording = True
                        if(self.debugging == False):
                            print("CHECKSUM")
                elif((total == 0 and checksumRecording == False) or errorDetected): #Something is wrong
                    if(self.debugging == False): 
                        print(totalMessage)
                        print("ERROR1")
                    if(self.recoverMessage(entireMessage)):
                        pass
                    else:
                        self.debuggingMessage.emit(entireMessage[8:])
                        self.message.emit("Error receiving")
                        self.currentlyReceiving.emit(False)
                    self.syncMessages()
                    break
                elif(total == 0 and checksumRecording == True):
                    errorDetected = True #If we detect a string of 0's again on the next pass, this will error
                else:
                    #Keep track of the total message for later
                    totalMessage += message[:8]
                    if(self.debugging == False):
                        print(totalMessage)

                    if(checksumRecording == False):
                        #If neither case, we have a normal character, figure out what it is and add it to our message
                        self.receivedMessage += chr(total)
                    
                self.pulseCounter = self.pulseCounter - 8
                if(self.debugging == False):
                    print(message[:8])
                for value in message[:8]:
                    entireMessage += str(value)
                message = message[8:] #Remove handled chars from the message

                #Debugging
                if(self.debugging == False):
                    print("\n Receiving.. : " + self.receivedMessage + "\n")
                    
            #Sleeps for remaining quarter of pulse
            t_end = startPoint + self.onTime
            if(time.perf_counter() < t_end):
                if(self.onTime - (time.time() % self.onTime) > 0):
                    time.sleep(self.onTime - (time.time() % self.onTime))
            
    #Function to control the cpu usage monitoring method
    def getCpuPercent(self, request):
        if(self.fakeCpu):
            request = "a" #Anything else
            self.server.send(request.encode('utf8'))
            response = self.server.recv(255).decode('utf8')
            return json.loads(response)
        else:
            return psutil.cpu_percent(interval=0.1, percpu=True)
    
    #Function to receive message via the memory method
    def receiveMessageMemory(self):
        baselineTotal = 0
        baseline = -1
        count = 0
        self.receivedMessage = ''
        entireMessage = []

        t_end = time.perf_counter() + 1 #1 Second polling window
        while(time.perf_counter() < t_end):
            baselineTotal += psutil.virtual_memory().percent
            count += 1
            
        #Record baseline usage to compare to 
        baseline = baselineTotal / count
        if(self.debugging == False):
            print("Baseline is: " + str(baseline))

        baselineTotal = 0
        count = 0
        firstPulseFound = False
        message = []
        threshold = 1
        startedRecording = False
        totalMessage = []
        repeatCount = 0
        checksumRecording = False

        while self.active:
            if(firstPulseFound == False and time.time() > self.timeOut):
                self.debuggingMessage.emit([])
                break
            currentUsage = psutil.virtual_memory().percent
            if(currentUsage > baseline + threshold):
                message.append(1)
                self.zeroOrOne.emit(1)
                if(self.debugging == False):
                    print(1)
                #Stops ability to send message
                self.currentlyReceiving.emit(True)
                firstPulseFound = True
                while True:
                    if(psutil.virtual_memory().percent < baseline + threshold):
                        break
                break
            
        while self.active: 
            startPoint = time.time()
            #Sleep for first 1/6 of ontime
            time.sleep(self.onTime / 6)
            
            #Then sample
            currentUsage = psutil.virtual_memory().percent
            if(self.debugging == False):
                print("Time: " + str(time.time()))
                print("Usage: " + str(currentUsage))
            if(currentUsage > baseline + threshold):
                message.append(1)
                self.zeroOrOne.emit(1)
                if(self.debugging == False):
                    print(1)
            else:
                message.append(0)
                self.zeroOrOne.emit(0)
                if(self.debugging == False):
                    print(0)
            
            if(len(message) == 8):
                total = 0
                #Convert binary to decimal
                for i in range(8):
                    total += message[i] * 2**(7-i)
                
                if(total == 255 and startedRecording): #We have reached the end of our message
                    repeatCount += 1
                    #We have reached the end of all our repeats
                    if(repeatCount == self.repeats):
                        for value in message[:8]:
                            entireMessage += str(value)
                        if(self.debugging == False):
                            print("done")
                        self.calculateAverageMessage(totalMessage=totalMessage)
                        self.receiveMessageMemory()
                        break
                    
                    #We are now recording the checksum
                    if(repeatCount == self.repeats -1):
                        checksumRecording = True
                elif(total == 0): #Something is wrong
                    for value in message[:8]:
                        entireMessage += str(value)
                    if(self.recoverMessage(entireMessage)):
                        pass
                    else:
                        self.debuggingMessage.emit(entireMessage[8:])
                        self.message.emit("Error receiving")
                        self.currentlyReceiving.emit(False)
                    self.receiveMessageMemory()
                    break
                elif(startedRecording):
                    #Keep track of the total message for later
                    totalMessage += message
                    if(self.debugging == False):
                        print(totalMessage)
                
                    if(checksumRecording == False):
                        #If neither case, we have a normal character, figure out what it is and add it to our message
                        self.receivedMessage += chr(total)
                    
                if(total == 255 and startedRecording == False):
                    startedRecording = True
                    total = 1
                    
                for value in message[:8]:
                    entireMessage += str(value)
                message = []
                
            t_end = startPoint + self.onTime
            if(time.time() < t_end):
                if(self.onTime - (time.time() % self.onTime) > 0):
                    time.sleep(self.onTime - (time.time() % self.onTime))
    
    #Get size used by a folder and all subfolders
    def get_size(self, start_path, sizeToLookFor):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total_size += os.path.getsize(fp)
                except FileNotFoundError: #Sometimes file gets deleted during checking
                    total_size += sizeToLookFor

        return total_size
    
    #Method to receive message via the disk method
    def receiveMessageDisk(self):
        polingWindow = self.onTime /2 
        clusterSize = 4096
        sizeRequested = 100000
        sizeToLookFor = clusterSize * math.ceil(sizeRequested / clusterSize)
        baseline = self.get_size(self.folderToUse, sizeToLookFor)
        message = []
        firstPulseFound = False
        repeatCount = 0
        startedRecording = False
        totalMessage = []
        checksumRecording = False
        self.receivedMessage = ''
        entireMessage = []

        print("Baseline: " + str(baseline))

        #Sync for the first 1
        while self.active:
            if(firstPulseFound == False and time.time() > self.timeOut):
                self.debuggingMessage.emit([])
                break
                
            baseline = self.get_size(self.folderToUse, sizeToLookFor)
            time.sleep(self.onTime / 100)
            if(self.get_size(self.folderToUse, sizeToLookFor)-baseline == sizeToLookFor):
                timeStamp = round(time.time()+polingWindow/2,2) % self.onTime
                t_end = time.time() + self.onTime - timeStamp
                start_time = t_end
                offset = t_end - time.time() + polingWindow/2
                firstPulseFound == True
                self.currentlyReceiving.emit(True)
                self.zeroOrOne.emit(1)
                message.append(1)
                break

        #Main loop after first 1 recorded
        while self.active:
            if(firstPulseFound == False and time.time() > self.timeOut):
                self.debuggingMessage.emit([])
                break
            found = False
            
            #Wait until the right time, ensures sync
            t_end = start_time + self.onTime - offset 
            
            while(time.time() < t_end): 
                time.sleep(0.01) 
            start_time = time.time()
            baseline = self.get_size(self.folderToUse, sizeToLookFor)
            
            t_end = time.time() + polingWindow #Time to "listen for"
            while time.time() < t_end:
                if(abs(self.get_size(self.folderToUse, sizeToLookFor) - baseline) == sizeToLookFor and found == False):
                    if(firstPulseFound == False):
                        #Stops ability to send message
                        self.currentlyReceiving.emit(True)
                        if(self.debugging == False):    
                            print(time.time())
                    found = True
                    offset = polingWindow/2 - (time.time() - (t_end - polingWindow)) #Current time minus start time 
                    firstPulseFound = True
                time.sleep(0.01)

            #Record 1 or 0
            if(found):
                message.append(1)
                self.zeroOrOne.emit(1)
            elif(firstPulseFound):
                message.append(0)
                self.zeroOrOne.emit(0)
            
            if(self.debugging == False):  
                print(message)
                
            if(len(message) == 8 and firstPulseFound):
                total = 0
                #Convert binary to decimal
                for i in range(8):
                    total += message[i] * 2**(7-i)
                    
                if(total == 255 and startedRecording): #We have reached the end of our message
                    repeatCount += 1
                    #We have reached the end of all our repeats + checksum
                    if(repeatCount == self.repeats):
                        for value in message[:8]:
                            entireMessage += str(value)
                        if(self.debugging == False):
                            print("done")
                        self.calculateAverageMessage(totalMessage=totalMessage)
                        self.receiveMessageDisk()
                        break
                    
                    #We are now recording the checksum
                    if(repeatCount == self.repeats -1):
                        checksumRecording = True
                elif(total == 0): #Something is wrong
                    for value in message[:8]:
                        entireMessage += str(value)
                    if(self.recoverMessage(entireMessage)):
                        pass
                    else:
                        self.debuggingMessage.emit(entireMessage[8:])
                        self.message.emit("Error receiving")
                        self.currentlyReceiving.emit(False)
                    self.receiveMessageDisk()
                    break
                elif(startedRecording):
                    #Keep track of the total message for later
                    totalMessage += message
                    if(self.debugging == False):
                        print(totalMessage)
                
                    if(checksumRecording == False):
                        #If neither case, we have a normal character, figure out what it is and add it to our message
                        self.receivedMessage += chr(total)
                        if(self.debugging == False):
                            print(self.receivedMessage)
                
                if(total == 255 and startedRecording == False):
                    startedRecording = True
                    total = 1
                    
                for value in message[:8]:
                    entireMessage += str(value)
                message = []
              
    #Method to receive message via udp
    def receiveMessageUDP(self):
        self.s = socket.socket(socket.AF_INET , socket.SOCK_DGRAM )
        #Find a free port to bind to
        try:
            self.s.bind(("localhost",19999))
            print("receiver bound to 19999")
        except OSError:
            self.s.bind(("localhost", 19998))
            print("receiver bound to 19998")
        while self.active:
            try:
                #Receive from said port
                msg = self.s.recvfrom(1024)
                if(self.active):
                    self.message.emit(msg[0].decode())    
                    self.currentlyReceiving.emit(False)
            except OSError:
                break
    
    #Function to take the errored message and try to recover something useful from it
    def recoverMessage(self, entireMessage):
        while len(entireMessage) > 0:
            triggered = True
            
            # Attempt to find a string of 8 1s somewhere in the message
            positionOfLast = len(entireMessage) - 1 - entireMessage[::-1].index('1')
            for i in range(8):
                try:
                    if(entireMessage[positionOfLast - i] == '0'):
                        entireMessage = entireMessage[0:positionOfLast]
                        triggered = False
                        break
                except IndexError:
                    print("Recovery Failed")
                    return False
            if(triggered):
                moveOn = True
                for i in range(8): #Looks at the middle set and ensures they are also all 1's
                    try:
                        if(entireMessage[positionOfLast-16-i] == "0"):
                            moveOn = False
                    except IndexError:
                        print("Recovery Failed")
                        return False
                if(moveOn):
                    break
                else:
                    entireMessage = entireMessage[0:positionOfLast]
        if(len(entireMessage) == 0):
            print("Recovery Failed")
            return False
        
        
        totalMessage = []
        
        #Gets checksum and trims message down to size
        checksum = entireMessage[positionOfLast-7:positionOfLast-15]
        
        cutMessage = entireMessage[0:positionOfLast-7]
        cutMessage = list(reversed(cutMessage))
        
        #Checks each 8 string of message and ensures it has at least 1 0, otherwise this is an identifier sequence
        for i in range(0, len(cutMessage), 8):
            tempList = cutMessage[i:i+8]
            continueOn = False
            for k in range(len(tempList)):
                tempList[k] = int(tempList[k])
                if(tempList[k] == 0):
                    continueOn = True
            if(continueOn):
                totalMessage += tempList
        
        #Append the missing 1s
        try:
            entireMessage = ['1'] * (8-len(tempList)) + entireMessage[0:positionOfLast+1]
        except UnboundLocalError:
            entireMessage = ['1'] * (8) + entireMessage[0:positionOfLast+1]
        
        print("EntireMessage: " + str(entireMessage))
                        
        totalMessage = list(reversed(totalMessage))
        totalMessage += checksum
        
        print("TotalMessage: " + str(totalMessage))
        
        #Now message is recovered
        self.calculateAverageMessage(totalMessage=totalMessage)
        
        return True
               
    #Function to calculate the average message based on the repeats used
    def calculateAverageMessage(self, totalMessage):
        #Make sure we don't include the checksum
        actualRepeats = self.repeats - 1
        
        #Recalculate number of repeats actually received 
        estimatedLength = (len(totalMessage)-8) / actualRepeats
        
        if((8 * math.ceil(estimatedLength / 8))== 0):
            actualRepeats = self.repeats - 1
        else:
            actualRepeats = math.floor((len(totalMessage)-8) / (8 * math.ceil(estimatedLength / 8)))
        
        #Remove the checksum from the calculation
        messageLength = round((len(totalMessage)-8) / actualRepeats) #16
        print(len(totalMessage))
        print(estimatedLength)
        print(actualRepeats)
        print(messageLength)
        print(totalMessage)
        self.receivedMessage = ""
        message = []

        #Recalculate received message based on repeats
        for k in range(messageLength): #0-13
            sumOfBinary = 0
            for i in range(actualRepeats): #0-4
                sumOfBinary += totalMessage[k+messageLength*i]
            
            #sumOfBinary - actualRepeats = number of 0s
            percentageOfOnes = 1 #If we have detected more than threshold number of 1's, we have received a 1
            if((1-abs(sumOfBinary - actualRepeats) / actualRepeats)) >= percentageOfOnes:
                message.append(1)
            else:
                message.append(0)
            
        
        self.debuggingMessage.emit(message)
            
        if(self.debugging == False):
            print(message)
            
        #Calculate the checksum
        checksum = []

        for i in range(8):
            temp = 0
            for k in range(round(len(message) / 8)):
                try:
                    temp = (temp != bool(int(message[i+8*k])))
                except IndexError:
                    self.message.emit("Error receiving due to checksum")
                    self.currentlyReceiving.emit(False)
                    break
            checksum.append(int(temp))
        
        #Convert binary to decimal
        for k in range(round(messageLength /8)):
            total = 0
            for i in range(8):
                try:
                    total += message[i + k*8] * 2**(7-i)
                except IndexError:
                    self.message.emit("Error receiving due to checksum")
                    self.currentlyReceiving.emit(False)
                    break
            self.receivedMessage += chr(total)
            
        self.zeroOrOne.emit(0)
        
        #Checks if checksum matches
        if(checksum != totalMessage[-8:]):
            if(self.debugging == False): 
                print(checksum)
                print(totalMessage[-8:])
                print("ERROR IN CHECKSUM")
            self.message.emit("Error receiving due to checksum")
            self.currentlyReceiving.emit(False)
        else:
            if(self.debugging == False): 
                print("SUCCESS IN CHECKSUM")
            #Tell main program we have finished
            print(self.receivedMessage)
            self.message.emit(self.receivedMessage)
            self.currentlyReceiving.emit(False)
    
    #Kills thread
    def stop(self):
        try:
            self.s.shutdown(socket.SHUT_RDWR)
            self.s.close()
        except OSError:
            pass
        except AttributeError:
            pass
        if(self.debugging == False): 
            print("Stopping")
        self.active = False
        self._isRunning = False
        