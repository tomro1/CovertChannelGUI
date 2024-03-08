# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# Simulation program - with heavy abstraction

import random
import numpy
import scipy.io

def mainLoop(messageLength, repeats, cpuUtilisation, detectionThreshold, mean, std, percentageOfOnes,  verbose=False):
    message = []
    sentMessage = []
    
    #Generates a random sequence of 0s and 1s
    for i in range(messageLength):
        message.append(random.choice([0, cpuUtilisation]))
        if(message[i] > detectionThreshold):
            sentMessage.append(1)
        else:
            sentMessage.append(0)
        
    if(verbose):
        print("Sent: " + str(sentMessage))
    message = message * repeats
    
    if(verbose):
        print(message)

    #Gaussian additive noise
    num_samples = messageLength * repeats
    data = numpy.random.normal(mean, std, size=(num_samples, 16))
    data[data > 1] = 1
    data[data < 0] = 0
    data = data * 100
    data = data.round(3).tolist()

    for i in range(len(message)):
        message[i] += data[i][0]
        if(message[i] > 100):
            message[i] = 100

    #Noise has been added
    if(verbose):
        print(message)

    #Computes what message would be received
    receivedMessage = []
    for i in range(len(message)):
        if(message[i] > detectionThreshold):
            receivedMessage.append(1)
        else:
            receivedMessage.append(0)

    if(verbose):
        print(receivedMessage)

    #Calculates average using majority voting
    computedMessage = []
    for k in range(messageLength):
        sumOfBinary = 0
        for i in range(repeats):
            sumOfBinary += receivedMessage[k+messageLength*i]

        if((1-(abs(sumOfBinary - repeats) / repeats))) >= percentageOfOnes:
            computedMessage.append(1)
        else:
            computedMessage.append(0)
    
    if(verbose):        
        print("Received: " + str(computedMessage))
                
    #Calculate BER
    totalBits = messageLength
    errorBits = 0
    for i in range(totalBits):
        try:
            if(str(computedMessage[i]) != str(sentMessage[i])):
                errorBits += 1
        except IndexError:
            errorBits += 1
         
    if(verbose):   
        print(f"Total bits: {str(totalBits)}, Error bits: {str(errorBits)}, Bit error rate: {str((errorBits/totalBits)*100)}%")
    return (errorBits/totalBits)*100

messageLength = 10 * 8
repeats = 10
verbose = False

#Cpu Usage
cpuUtilisation = 50
detectionThreshold = cpuUtilisation / 2

#Noise
mean = 0.4
std = 0.1

#Runs the main test sequence, changing 3 variables at a time to produce a 3 scatter graphs
ydata = []
for repeats in [20,50,100]:
    averageBER = []
    xdata = []
    for innerLoop in range(0, 101, 5):
        mean = innerLoop/100
        detectionThreshold = cpuUtilisation / 2
        xdata.append(innerLoop)
        BER = []
        for i in range(1000):
            BER.append(mainLoop(messageLength, repeats, cpuUtilisation, detectionThreshold, mean, std, percentageOfOnes=1, verbose=verbose))
        averageBER.append(sum(BER) / len(BER))
        print("Running sim " + str(innerLoop))
    ydata.append(averageBER)
    
    
print(averageBER) 

#Data to write to a matlab file
lines = 3
legend = ["20 Repeats", "50 Repeats", "100 Repeats"]
filename = "MOREmeanBERrep-50util" + ".mat"

#Note purely for personal use
note = "Varying mean noise compared to BER, with number of repeats varying. CPU util=50%, std=0.1, detection=25%"

scipy.io.savemat(filename, dict(lines=str(lines), xdata1=xdata, ydata1=ydata[0], xlabel="Mean Noise Level (%)", ylabel="Average Bit Error Rate (%)", xdata2=xdata, xdata3=xdata, ydata2=ydata[1], ydata3=ydata[2], legend=legend, note=note))