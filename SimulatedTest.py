# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# Program to combine both threads to quickly test the system

import ReceiverThread, SenderThread
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import time
import sys
import random
import socket

class Window(QMainWindow): 
    def __init__(self): 
        self.sentMessage = []
        self.receivedMessage = []
        self.mechanismToTest = 0
        self.testTotalRepeats = 5
        self.onTimes = [0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01] #Set of pulse times to test
        self.limiterValues = [50, 52.5, 55, 57.5, 60, 62.5, 65, 67.5, 70] #Set of CPU limiters to test
        self.noiseLevels = [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5] #Set of noise values to test
        self.startIndex = 3 #Index of that list to start on
        self.noMessages = True #Debugging messages or not (True = No messages)
        self.count = 1 + self.testTotalRepeats*self.startIndex
        self.averageNoise = 0
        
        #Change this to change element under test
        self.testerMode = 4 #0 = onTimes, 1= utilisation, 2 = noise level, 3 = 50% noise level test, 4 = nothing changing, 30% usage
        self.recordNoise = True #Will calculate the average noise during window
        
        #Sets up default values
        if(self.testerMode == 0):
            self.onTime = self.onTimes[self.startIndex]
            self.limiter = 0
        elif(self.testerMode == 1):
            self.limiter = self.limiterValues[self.startIndex]
            self.onTime = 0.4
        elif(self.testerMode == 2):
            self.limiter = 0
            self.onTime = 0.4
        elif(self.testerMode == 3 or self.testerMode == 4):
            self.limiter = 70 #30% usage
            self.onTime = 0.4
                
        #Use fakeCPu or not
        if(self.mechanismToTest == 0 or self.mechanismToTest == 3 or self.mechanismToTest == 4):
            self.fakeCpu = True
        else:
            self.fakeCpu = False
        super().__init__() 
        self.runThreads()

        self.show()
        
    #Run the threads and calculate the BER
    def runThreads(self):
        print("Current Error rates - " + str(currentErrorRates))
        print("Current Noise levels - " + str(currentNoiseLevels))
        try:
            self.s.stop()
            self.r.stop()
            time.sleep(1)
        except:
            pass
        
        #Switch based on what we are testing, and set up the variables depending on that
        if(self.testerMode == 0):
            if((self.count-1) % self.testTotalRepeats == 0):
                try:
                    self.onTime = self.onTimes[round((self.count-1) / self.testTotalRepeats)]
                    print("Ontime is ", self.onTime)
                except IndexError:
                    self.close()
                    return False
        elif(self.testerMode == 1):
            if((self.count-1) % self.testTotalRepeats == 0):
                try:
                    self.limiter = self.limiterValues[round((self.count-1) / self.testTotalRepeats)]
                    print("Limiter is ", self.limiter)
                except IndexError:
                    self.close()
                    return False
        elif(self.testerMode == 2 or self.testerMode == 3):
            if((self.count-1) % self.testTotalRepeats == 0):
                try:
                    noise = self.noiseLevels[round((self.count-1) / self.testTotalRepeats)]
                    print("Noise is ", noise)
                    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server.connect(('localhost', 20000))
                    request = "c" + str(noise)
                    server.send(request.encode('utf8'))
                except IndexError:
                    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    server.connect(('localhost', 20000))
                    request = "c0.2"
                    server.send(request.encode('utf8'))
                    self.close()
                    return False
    

        coreToUse = 0 #Which CPU core to test 
        self.repeats = 1+1 #+1 for checksum
        self.messageLength = 2 *8
        message = []
        
        #Generate random binary string
        for i in range(self.messageLength):
            message.append(str(random.randint(0,1)))
            
        #Checks for any 7 zeros in a row, if they exist, it replaces them
        for i in range(0, self.messageLength, 8):
            hasA1 = False
            hasA0 = False
            for k in range(8):
                if(message[i+k] == "1"):
                    hasA1 = True
                if(message[i+k] == "0"):
                    hasA0 = True
            if(hasA1 == False):
                message[i+random.randint(0,7)] = "1"
            if(hasA0 == False):
                message[i+random.randint(0,7)] = "0"

        if(self.mechanismToTest == 1 or self.mechanismToTest == 2):
            time.sleep(2) #Small sleep to avoid weird startups
            
        #Creates receiver thread
        self.r = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=coreToUse, mechanism=self.mechanismToTest, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter, debugging=self.noMessages, messageLength=self.messageLength)
        self.r.debuggingMessage.connect(self.handleReceiver)
        self.r.start()

        if(self.mechanismToTest == 1 or self.mechanismToTest == 2 or self.mechanismToTest == 3):
            time.sleep(2) #Small sleep to avoid weird startups

        #Creates sender thread
        self.s = SenderThread.SendMessageThread(parent=self, message=message, onTime=self.onTime, coreToUse=coreToUse, machineOne=True, mechanism=self.mechanismToTest, repeats=self.repeats, fakeCpu=self.fakeCpu, limiter=self.limiter, debugging=self.noMessages)
        self.s.debuggingMessage.connect(self.handleSender)
        self.s.start()
        
        #Start recording noise
        if(self.recordNoise):
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.connect(('localhost', 20000))
            request = "r"
            server.send(request.encode('utf8'))
        
        self.count += 1
        
    #Handler for when a message has been successfully received
    def handleReceiver(self,result):
        self.s.stop()
        self.r.stop()
        
        #Calculate noise
        if(self.recordNoise):
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.connect(('localhost', 20000))
            request = "f"
            server.send(request.encode('utf8'))
            self.averageNoise = server.recv(255).decode('utf8')
            print("Average Noise: " + str(self.averageNoise))
            currentNoiseLevels.append(round(float(self.averageNoise), 2))
        
        self.receivedMessage = result
        print("\nGOTTEN: " + str(result))
        
        #Calculate BER
        totalBits = len(self.sentMessage)
        errorBits = 0
        for i in range(totalBits):
            try:
                if(str(self.receivedMessage[i]) != str(self.sentMessage[i])):
                    errorBits += 1
            except IndexError:
                errorBits += 1
                
        print(f"Total bits: {str(totalBits)}, Error bits: {str(errorBits)}, Bit error rate: {str((errorBits/totalBits)*100)}%")
        
        currentErrorRates.append((errorBits/totalBits)*100)
        
        self.runThreads()
        
    #Lets the user know the sent message
    def handleSender(self, result):
        self.sentMessage = result
        print("\nSENT:   " + str(result))


        
#Stops function from re-calling itself during threading
if __name__ == "__main__":
    currentErrorRates = []
    currentNoiseLevels = []
    app = QApplication([])
    window = Window()
    sys.exit(app.exec())