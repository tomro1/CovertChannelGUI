# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php 

# This code takes a sample window and records the CPU usage to a file to use for later simulation

import psutil
import time
import json

totalResults = []

filename = input("Enter file name: ")
timeToRecord = int(input("Enter number of minutes to sample for: "))

time.sleep(1 - round(time.time()+0.11, 2) % 1)

t_end = time.time() + 60 * timeToRecord #1 Min

while(time.time() < t_end):
    usage = psutil.cpu_percent(interval=0.1, percpu=True)
    totalResults.append(usage)
    
f = open(filename, "w")
f.write(json.dumps(totalResults))