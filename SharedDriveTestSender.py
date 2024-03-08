# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# Program to test shared file services - sender side

import SenderThread
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import time
import sys

class Window(QMainWindow): 
    def __init__(self): 
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
        try:
            self.s.stop()
            time.sleep(1)
        except:
            pass
        
        if((self.count-1) % self.testTotalRepeats == 0):
            try:
                self.onTime = self.onTimes[round((self.count-1) / self.testTotalRepeats)]
                print("Ontime is ", self.onTime)
            except IndexError:
                self.close()
                return False
        
        self.repeats = 1+1 #+1 for checksum
        self.messageLength = 2 *8
        message = ['0', '1', '1', '1', '0', '1', '0', '0', '0', '1', '1', '0', '1', '0', '1', '1']
            
        time.sleep(1) #Small sleep to avoid weird startups

        self.s = SenderThread.SendMessageThread(parent=self, message=message, onTime=self.onTime, coreToUse=0, machineOne=True, mechanism=self.mechanismToTest, repeats=self.repeats, fakeCpu=False, limiter=0, debugging=self.noMessages, folderToUse=self.folder)
        self.s.debuggingMessage.connect(self.handleSender)
        self.s.killReceiver.connect(self.killThread)
        self.s.start()
        
        self.count += 1
        
    def killThread(self, val):
        print(val)
        if(val == False):
            self.s.stop()
            self.runThreads()
        
    #Lets the user know the sent message
    def handleSender(self, result):
        print("\nSENT:   " + str(result))


        
#Stops function from re-calling itself during threading
if __name__ == "__main__":
    app = QApplication([])
    window = Window()
    sys.exit(app.exec())