# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# This code acts as an intermediate stage for the CPU, and needs to be running during testing. Using this you can either use real CPU data or simulated

import asyncio
import psutil
import json
import time
from copy import deepcopy
import numpy

#Creates a simple aync server
async def handle_client(reader, writer):
    global data
    global newData
    global pulseTime
    global totalNoise
    global startedRecording
    request = None
    while request != 'quit': 
        request = (await reader.read(255)).decode('utf8')
        print(request)
        #If we receive "poll" or "sync" send back the live CPU data
        if(request == "poll"):
            response = json.dumps(psutil.cpu_percent(interval=0.1, percpu=True))
        elif(request == "sync"):
            response = json.dumps(psutil.cpu_percent(interval=0.1, percpu=True))
        elif(request[0] == "u"): #Updates simulated values with value given
            if(startedRecording):
                timeStamp = round(((round(time.time(), 2)*100) % (num_samples)*0.1)*10)
                totalNoise.append(data[timeStamp][0])
            for k in range(len(data)):
                for i in range(len(data[k])):
                    newData[k][i] = data[k][i] + float(request[1:])
                    if(newData[k][i] > 100):
                       newData[k][i] = 100.0
            response = str("done")
        elif(request.find("s") != -1): #Updates a single core with the value given
            core = int(request[:request.find("s")])
            value = request[request.find("s")+1:]
            if(startedRecording):
                timeStamp = round(((round(time.time(), 2)*100) % (num_samples)*0.1)*10)
                totalNoise.append(data[timeStamp][0])
            print("Core: " + str(core) + " value: " + str(value))
            for k in range(len(data)):
                newData[k][core] = data[k][core] + float(value)
                if(newData[k][core] > 100):
                    newData[k][core] = 100.0
            response = str("done")
        elif(request[0] == "c"): #Change simulated noise level 
            data = numpy.random.normal(float(request[1:]), std, size=(num_samples, 16))
            data[data > 1] = 1
            data[data < 0] = 0
            data = data * 100
            data = data.round(3).tolist()
            newData = deepcopy(data)
            response = ""
        elif(request[0] == "p"): #Notifies of the pulse time
            pulseTime = float(request[1:])
            print(pulseTime)
            response = ""
        elif(request[0] == "r"): #Start recording average noise
            startedRecording = True
            response = ""
        elif(request[0] == "f"): #Finished recording average noise
            startedRecording = False
            response = str(sum(totalNoise) / len(totalNoise))
            totalNoise = []
        else:
            #If anything else is sent, just send back the simulated value for the current time
            timeStamp = round(((round(time.time(), 2)*100) % (num_samples)*0.1)*10)
            print(timeStamp)
            response = str(newData[timeStamp])
        writer.write(response.encode('utf8'))
        await writer.drain()
    writer.close()

#Run the actual server
async def run_server():
    server = await asyncio.start_server(handle_client, 'localhost', 20000)
    async with server:
        await server.serve_forever()

#Load data from a file
f = open("Benchmark5", "r")
data = json.loads(f.read())

std = 0.1 #Prevents errors 
totalNoise = []
startedRecording = False

num_samples = len(data)

#Shows average noise per core from dataset
for k in range(16):
    total = 0
    for i in range(num_samples):
        total += data[i][k]
    print("Average for core " + str(k) + " is: " + str(total/num_samples))

#Gaussian additive noise - uncomment to load use this instead of loading from file
""" mean = 0.3
std = 0.1
num_samples = 48
data = numpy.random.normal(mean, std, size=(num_samples, 16))
data[data > 1] = 1
data[data < 0] = 0
data = data * 100
data = data.round(3).tolist() """

newData = deepcopy(data)

pulseTime = 1

asyncio.run(run_server())
