# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# Program to test shared file services - receiver side

import ReceiverThread
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import time
import sys

class Window(QMainWindow): 
    def __init__(self): 
        self.sentMessage = []
        self.receivedMessage = []
        self.mechanismToTest = 2 #Disk - Keep as this
        self.testTotalRepeats = 1 #Number of repeats per test
        self.onTimes = [15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5] #Set of pulse times to test
        self.startIndex = 0 #Index of that list to start on
        self.noMessages = True #Debugging messages or not (True = No messages)
        self.folder = 'CHANGE' #Point towards the folder you want to test
        
        #Setup
        self.count = 1 + self.testTotalRepeats*self.startIndex
        self.onTime = self.onTimes[self.startIndex]
        super().__init__() 
        self.runThreads()

        self.show()
        
    #Run the threads and calculate the BER
    def runThreads(self):
        print("Current Error rates - " + str(currentErrorRates))
        
        try:
            self.r.stop()
            time.sleep(1)
        except:
            pass
        
        self.repeats = 1+1 #+1 for checksum
        self.messageLength = 2 *8
        self.sentMessage = ['0', '1', '1', '1', '0', '1', '0', '0', '0', '1', '1', '0', '1', '0', '1', '1']
            
        time.sleep(5) #Small sleep to avoid weird startups
            
        self.r = ReceiverThread.ListenForMessageThread(parent=self, onTime=self.onTime, sync=False, coreToUse=0, mechanism=self.mechanismToTest, repeats=self.repeats, fakeCpu=False, limiter=0, debugging=self.noMessages, messageLength=self.messageLength, folderToUse=self.folder)
        self.r.debuggingMessage.connect(self.handleReceiver)
        self.r.start()
        
        print("Waiting...")
        
        self.count += 1
        
    #Handler for when a message has been successfully received
    def handleReceiver(self,result):
        self.r.stop()
        
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

#Stops function from re-calling itself during threading
if __name__ == "__main__":
    currentErrorRates = []
    app = QApplication([])
    window = Window()
    sys.exit(app.exec())