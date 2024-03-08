# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# DO NOT RUN directly. This thread is ran by MainProgram.py when needed

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import psutil
import time
import os
import multiprocessing
import math
import socket
import subprocess
import json
import re

#Class to modulate the CPU usage to send a binary signal
class SendMessageThread(QThread):
    #Outputs from the thread back to the main GUI
    finished = pyqtSignal(bool)
    core = pyqtSignal(int)
    killReceiver = pyqtSignal(bool)
    sendingUpdate = pyqtSignal(float)
    debuggingMessage = pyqtSignal(list)

    #Setup function
    def __init__(self, parent, message, onTime, coreToUse, machineOne, mechanism, repeats, fakeCpu, limiter, debugging=False, folderToUse=""):
        QThread.__init__(self, parent)
        self.active = True
        self.coreToUse = coreToUse
        self.onTime = onTime
        self.message = message
        self.startPoint = 0
        self.adjustmentFactor = 0
        self.folderToUse = folderToUse
        self.count = 0
        self.machineOne = machineOne
        self.throttling = 1 #e.g. 0.3 = 30% throttled
        self.mechanism = mechanism #0 - CPU, 1 - Memory
        self.repeats = repeats
        self.fakeCpu = fakeCpu
        self.limiter = limiter
        self.debugging = debugging  
        
        if(self.fakeCpu):
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.connect(('localhost', 20000))

    #Runs the main message function when thread is started
    def run(self):
        if(self.message != ["sync"]):
            self.frameAndSendMessage()
        else:
            self.selectCore()
            self.sendSync()
    
    #Listens for a sync pulse sent by the other machine, if found, sends confirmation
    def listenForSync(self):
        #Bind to a different core to avoid interference when listening
        p = psutil.Process()
        try:
            p.cpu_affinity([self.coreToUse+1])
        except:
            p.cpu_affinity([self.coreToUse-1]) 
        
        totalCpuUsage = ""
        logicalTracker = ""

        #Samples for 7 * 3 * onTime before assuming sync has been unheard and resends
        pause_time = 4 #Set in sendSync function in receiver
        t_end = time.perf_counter() + self.onTime * 7 + pause_time
        while time.perf_counter() < t_end:
            #Sample CPU usage
            if(self.fakeCpu):
                time.sleep(1/5)
            currentCpuUsage = self.getCpuPercent("sync")[self.coreToUse]

            #Monitors core for the sync pattern
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
            if(re.search("1010101", logicalTracker)):   
                print("FOUND")
                print(totalCpuUsage)
                return True
        time.sleep(7 * self.onTime + (7 - pause_time))
        return False
    
    #Function to control the cpu usage monitoring method
    def getCpuPercent(self, request):
        if(self.fakeCpu):
            request = "a" #Anything else
        self.server.send(request.encode('utf8'))
        response = self.server.recv(255).decode('utf8')
        return json.loads(response)
    
    #Modulate to send a sync message 
    def sendSync(self):
        syncWord = ['1', '0', '1', '0', '1', '0', '1', '0']
        message = syncWord
        
        #Continues until connection has been made
        while(self.active):
            self.sendMessageCPU(message, bypass=True)
                    
            #After sending the sync word sit and listen for a little bit (3 sets of 7 bits)
            if(self.listenForSync()):
                #Now send the confirmation pulse
                self.sendConfirmation() 
    
    #Modulate to send a confirmation message 
    def sendConfirmation(self):
        self.count = 0
        
        #Pause for a little before sending the confirmation
        time.sleep(self.onTime * 2)
        confirmationWord = ['1', '0', '1', '0']
        message = confirmationWord
        self.sendMessageCPU(message=message, bypass=True)
        
        #Connection is made
        self.finished.emit(True)
        self.active = False
        
    #Select the core to use based on a sampling window
    def selectCore(self):
        numCores = psutil.cpu_count()
        totals = [0] * numCores
        maximum = [-1] * numCores
        count = 0
        testPeriod = 1 #How many seconds to poll for
        averageWeighting = 0.5
        maximumWeighting = 0.5
        lowest = 100 #Used to select minimum factor
        coreChosen = -1

        print("Selecting core...")

        #Loop for the amount of seconds required
        for count in range(1, testPeriod+1):
            amounts = psutil.cpu_percent(interval=1, percpu=True)
            
            #Calculate the average and maximum
            totals = [totals[i] + amounts[i] for i in range(numCores)]  
            average = [totals[i] / count for i in range(numCores)]  
            for i in range(numCores):
                if(amounts[i] > maximum[i]):
                    maximum[i] = amounts[i]

        #Determine the core to be chosen based on metrics and weightings 
        for i in range(numCores):
            decisionFactor = maximum[i] * maximumWeighting + average[i] * averageWeighting
            if(decisionFactor < lowest):
                lowest = decisionFactor
                coreChosen = i

        #Print reasoning
        print("Average: ", average)
        print("Maximum: ", maximum)
        print("Core chosen: ", coreChosen)
        print("Factor: ",decisionFactor)
        
        #Output back to main thread
        self.coreToUse = coreChosen
        self.core.emit(coreChosen)
        
    #Frame the message with the starting/ending sequence and send
    def frameAndSendMessage(self):
        if(self.mechanism != 5):
            self.baseMessage = ['1','1','1','1','1','1','1','1'] #e.g. the "starting" sequence
            
            checksum = self.calculateChecksum(message=self.message)
            
        if(self.mechanism == 4):
            message = self.baseMessage + self.message
            #Minus 1 accounts for the checksum
            message = message * (self.repeats-1) + self.baseMessage + checksum + self.baseMessage
            self.debuggingMessage.emit(self.message)
            
            message = self.message
            message = (message + self.baseMessage) * (self.repeats-1) + checksum + self.baseMessage
        elif(self.mechanism != 5):
            message = self.baseMessage + self.message
            message = message * (self.repeats-1) + self.baseMessage + checksum + self.baseMessage
            self.debuggingMessage.emit(self.message)
        else:
            message = self.message
            
        #Use the correct function to send the message based on method selected
        if(self.debugging == False):
            print(message)
        if(self.mechanism == 0 or self.mechanism == 3 or self.mechanism == 4):
            self.sendMessageCPU(message)
        elif(self.mechanism == 1):
            self.sendMessageMemory(message)
        elif(self.mechanism == 2):
            self.sendMessageDisk(message)
        elif(self.mechanism == 5):
            self.sendMessageUDP(message)
        self.finished.emit(False)    
    
    #Function to compute the checksum
    def calculateChecksum(self, message):
        checksum = []

        for i in range(8):
            temp = 0
            for k in range(round(len(message) / 8)):
                temp = (temp != bool(int(message[i+8*k])))
            checksum.append(str(int(temp)))
            
        return checksum
        
    #Main sending CPU message handler
    def sendMessageCPU(self, message, bypass=False):
        #Check which mechanism we are using, and change cores used depending
        if(self.mechanism == 0):
            coresToUse = 2
        else:
            coresToUse = psutil.cpu_count() 
        
        if(self.debugging == False):
            print(coresToUse)
        
        #Loop through and create a process for each core used
        q = []
        progress = multiprocessing.Queue()
        if(self.mechanism == 4):
            
            #Split the message across cores
            counter = 0
            messages = []
            for i in range(1, coresToUse):
                messages.append([])
                
            while(counter < len(message)):
                messages[counter % (coresToUse -1)].append(message[counter])
                counter += 1
                
            
            startTime = self.calcStartTime()
            
            #For each core, create a thread and bind to this core
            for i in range(1, coresToUse):
                messages[i-1] = self.baseMessage + messages[i-1]
                
                q.append(multiprocessing.Queue())
                
                if(i == 1):
                    v = True
                else:
                    v = False
                    
                child = multiprocessing.Process(target=sendMessageCPU, args=(i, self.machineOne, self.active, messages[i-1], self.onTime, q[i-1],v,startTime,self.fakeCpu,self.mechanism, self.limiter,self.debugging,progress,bypass,))
                child.start() 
            if(self.debugging == False):
                print(messages)
        else:
            startTime = self.calcStartTime()
            #For each core, create a thread and bind to this core
            for i in range(1, coresToUse):
                q.append(multiprocessing.Queue())
                if(coresToUse == 1):
                    child = multiprocessing.Process(target=sendMessageCPU, args=(self.coreToUse, self.machineOne, self.active, message, self.onTime, q[0], True, startTime,self.fakeCpu,self.mechanism, self.limiter,self.debugging,progress,bypass,))
                else:
                    if(i == 1):
                        v = True
                    else:
                        v = False
                    child = multiprocessing.Process(target=sendMessageCPU, args=(i, self.machineOne, self.active, message, self.onTime, q[i-1],v, startTime,self.fakeCpu,self.mechanism,self.limiter,self.debugging,progress,bypass,))
                child.start()
                
        notDone = True
        successCount = 0
        
        #Checks if threads are finished
        while notDone:
            for i in range(1, coresToUse): 
                if(q[i-1].get() == True): 
                    successCount += 1
                    if(successCount == coresToUse -1):
                        self.killReceiver.emit(True)
                        notDone = False
                elif(q[i-1].get() == False):
                    notDone = False
        
        #While running, update the sending data
        value = 0
        while value != 1:  
            value = progress.get()
            self.sendingUpdate.emit(value)
            
        #Will wait for last to finish, assume all will finish shortly as well
        child.join()
        child.close()
        subprocess.Popen('.\\BES\\bes.exe -e')
       
    #Function to calculate a synced start time for all CPU threads
    def calcStartTime(self):
        if(self.machineOne):
            #Machine one sends on a round 10 second
            desired_time = time.time() + (10 - round(time.time()+1,2) % 10)
            
            if(time.time() - desired_time < 5):
                desired_time += 10
        else:
            desired_time = time.time() + (10 - round(time.time()+6,2) % 10)
        
            if(time.time() - desired_time < 5):
                desired_time += 10
        
        if(self.debugging == False):        
            print("Start time is " + str(desired_time))
        return desired_time 
    
    #Function to send message via memory
    def sendMessageMemory(self, message):
        #Sync with the clock and ensure sync
        if(self.machineOne):
            if(self.debugging == False):
                print("Machine 1")
            if round(time.time()+1,2) % 10 != 0: #Machine one sends on a round 10 second
                if(self.debugging == False):
                    print("Time is: " + str(time.time()) + " Sleeping for: " + str((10 - round(time.time()+1,2) % 10)))
                desired_time = time.time() + (10 - round(time.time()+1,2) % 10)
                
                #Zeros in on the desired time through increasingly small sleeps instead of one big sleep, which can cause issues when throttled
                while(round(time.time()+1,2) % 10 != 0):
                    if((desired_time - time.time()) * 0.5) > 0:
                        time.sleep((desired_time - time.time()) * 0.5)
                    else: #We have gone past the desired time
                        break
        else:
            if(self.debugging == False):
                print("Machine 2")
            if round(time.time()+1,2) % 10 != 5: #Machine two sends on a round 5 seconds
                if(self.debugging == False):
                    print("Time is: " + str(time.time()) + " Sleeping for: " + str((10 - round(time.time()+6,2) % 10)))
                desired_time = time.time() + (10 - round(time.time()+6,2) % 10)
                
                #Zeros in on the desired time through increasingly small sleeps instead of one big sleep, which can cause issues when throttled
                while(round(time.time()+1,2) % 10 != 5):
                    if((desired_time - time.time()) * 0.5) > 0:
                        time.sleep((desired_time - time.time()) * 0.5)
                    else: #We have gone past the desired time
                        break
        
        #Quick check to see if channel is busy
        if(self.active):
            pass
        else:
            print("Channel busy!")
            return
          
        self.killReceiver.emit(True)
        
        time.sleep(1) #Ensure properly killed
        
        #Add a 1 at the end to fix issue
        message.append("1")
        self.count = 0
    
        #For each binary char in the message
        for binary in message:
            self.count += 1
            self.sendingUpdate.emit(self.count / len(message))
            if round(time.time(),1) % self.onTime != 0: 
                time.sleep(self.onTime - round(time.time(),1) % self.onTime)
            l = []
            if(binary == '1'):
                if(self.debugging == False):
                    print("Sending pulse")
                    print("s-", str(time.time()))
                l.append("*" * 1024000000)
            else:
                if(self.debugging == False):
                    print("Sending null")
                    print("s-", str(time.time()))
                time.sleep(0.1)
        
    #Function to send message via disk
    def sendMessageDisk(self, message):
        #Sync with the clock and ensure sync
        if(self.machineOne):
            if(self.debugging == False):
                print("Machine 1")
            if round(time.time()+1,2) % 10 != 0: #Machine one sends on a round 10 second
                if(self.debugging == False):
                    print("Time is: " + str(time.time()) + " Sleeping for: " + str((10 - round(time.time()+1,2) % 10)))
                desired_time = time.time() + (10 - round(time.time()+1,2) % 10)
                
                #Zeros in on the desired time through increasingly small sleeps instead of one big sleep, which can cause issues when throttled
                while(round(time.time()+1,2) % 10 != 0):
                    if((desired_time - time.time()) * 0.5) > 0:
                        time.sleep((desired_time - time.time()) * 0.5)
                    else: #We have gone past the desired time
                        break
        else:
            if(self.debugging == False):
                print("Machine 2")
            if round(time.time()+1,2) % 10 != 5: #Machine two sends on a round 5 seconds
                if(self.debugging == False):
                    print("Time is: " + str(time.time()) + " Sleeping for: " + str((10 - round(time.time()+6,2) % 10)))
                desired_time = time.time() + (10 - round(time.time()+6,2) % 10)
                
                #Zeros in on the desired time through increasingly small sleeps instead of one big sleep, which can cause issues when throttled
                while(round(time.time()+1,2) % 10 != 5):
                    if((desired_time - time.time()) * 0.5) > 0:
                        time.sleep((desired_time - time.time()) * 0.5)
                    else: #We have gone past the desired time
                        break 
            
        #Quick check to see if channel is busy
        if(self.active):
            pass
        else:
            print("Channel busy!")
            return
          
        self.killReceiver.emit(True)
        
        time.sleep(1) #Ensure properly killed
        
        filePath = self.folderToUse + "new.txt"
        
        clusterSize = 4096
        bytesRequested = 100000
        bytesToGenerate = clusterSize * math.ceil(bytesRequested / clusterSize)
        fileExists = False
        sleepTime = self.onTime /5 
        self.count = 0
        
        #For each binary digit in message
        for binary in message:
            self.count += 1
            self.sendingUpdate.emit(self.count / len(message))
            
            #Wait until start time
            timeStamp = time.time() + self.onTime - round(time.time(),2) % self.onTime
            while(time.time() < timeStamp):
                time.sleep(0.01) 
                
            if(self.debugging == False):
                print("First Time: " + str(time.time()))
                
            #Do either 0 or 1
            if(binary == "1"):
                if(fileExists):
                    try:
                        os.remove(filePath) 
                    except FileNotFoundError:
                        pass
                    fileExists = False
                    time.sleep(sleepTime) #Small sleep to avoid retriggering loop
                else:
                    f = open(filePath, "wb")
                    f.write(b'\x21' * bytesToGenerate)
                    f.close()
                    fileExists = True
                    time.sleep(sleepTime)
            else:
                time.sleep(sleepTime)
                
        #Resets to a known state after sending message
        try:
            os.remove(filePath) 
        except:
            pass
        self.killReceiver.emit(False)
                
    #Function to send via UDP method
    def sendMessageUDP(self, message):
        try:
            self.killReceiver.emit(True)
            s = socket.socket(socket.AF_INET , socket.SOCK_DGRAM )
            port1 = 19999
            port2 = 19998
            #Bind to empty port
            try:
                s.bind(("localhost",19996))
            except OSError:
                s.bind(("localhost", 19997))
                
            #Send message on all target ports (port1 and port2) as we don't know which they will bind to
            ip = "localhost"
            time.sleep(1)
            print("sending")
            s.sendto(message.encode() , (ip,int(port1)))
            s.sendto(message.encode() , (ip,int(port2)))
        
        finally:
            s.shutdown(socket.SHUT_RDWR)
            s.close()

    #Kills thread
    def stop(self):
        self._isRunning = False

#Function outside of class to allow for multithreading to handle it
def sendMessageCPU(coreToUse, machineOne, active, message, onTime, q, verbose, startTime, fakeCpu, mechanism, limiter, debugging, progress, bypass):
    #Set back to default      
    if(fakeCpu):
        sendValueViaFakeCpu(0, mechanism, coreToUse)
    subprocess.Popen('.\\BES\\bes.exe -e')
    p = psutil.Process()
    if(verbose):
        if(debugging == False):
            print(p.pid)
    p.cpu_affinity([coreToUse]) 
    if(verbose and debugging == False):
        print("Assigning to core" + str(coreToUse), flush=True)
    
    if(bypass == False):
        while(time.time() < startTime):
            sleepTime = (startTime - time.time())*0.05
            if(sleepTime > 0):
                time.sleep(sleepTime)
    
    #Quick check to see if channel is busy
    if(active):
        pass
    else:
        print("Channel busy!", flush=True)
        q.put(False)
        return
        
    q.put(True)
    count = 0
    
    t_end = time.time() + 1
    
    if(limiter != 0 and fakeCpu == False):
        subprocess.Popen(f'.\\BES\\bes.exe "PID:{str(p.pid)}" {limiter} -m')
        print(f'.\\BES\\bes.exe "PID:{str(p.pid)}" {limiter} -m')
    
    while(time.time() < t_end):
        sleepTime = (t_end - time.time())*0.05
        if(sleepTime > 0):
            time.sleep(sleepTime)

    startPoint = time.perf_counter()

    #For each binary char in the message
    for binary in message:
        #Adjustment factor to ensure pulse is consistent
        if(fakeCpu == False):
            adjustmentFactor = (time.perf_counter() - startPoint - (onTime*(count))) * 1.5
        else:
            adjustmentFactor = (time.perf_counter() - startPoint - (onTime*(count)))
        count += 1
        
        progress.put(count / len(message))
        
        if(verbose and debugging == False):
            print("s-", str(time.time())) #Used to ensure sync when testing
        if binary == '1':
            #Sends a pulse (1)
            if(verbose and debugging == False):
                print("sending pulse", flush=True)
            
            #Ramps up for remaining of pulse left
            if(fakeCpu):
                sendValueViaFakeCpu((100-limiter), mechanism, coreToUse)
                if(onTime - adjustmentFactor) > 0:
                    time.sleep(onTime - adjustmentFactor)
            else:
                t_end = time.perf_counter() + onTime - adjustmentFactor 
                while time.perf_counter() < t_end:
                    pass
        elif binary == '0':
            #Sends a null (0)
            if(verbose and debugging == False):
                print("sending null", flush=True)
                
            if(fakeCpu):
                sendValueViaFakeCpu(0, mechanism, coreToUse)
                t_end = time.time() + onTime - adjustmentFactor
                while(time.time() < t_end):
                    sleepTime = (t_end - time.time())*0.05
                    if(sleepTime > 0):
                        time.sleep(sleepTime)
            else:
                t_end = time.time() + onTime - adjustmentFactor
                while(time.time() < t_end):
                    sleepTime = (t_end - time.time())*0.05
                    if(sleepTime > 0):
                        time.sleep(sleepTime)
        else:
            print("Error - incorrect format", flush=True) #Not a 1 or 0
      
    #Set back to default      
    if(fakeCpu):
        sendValueViaFakeCpu(0, mechanism, coreToUse)
    return True

#"Send" the value using the fakeCPU instead of the real one
def sendValueViaFakeCpu(value, mechanism, coreToUse):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.connect(('localhost', 20000))
    if(mechanism == 4):
        request = str(str(coreToUse) + str("s") + str(value))
    else:
        request = str(str("u") + str(value))
    server.send(request.encode('utf8'))