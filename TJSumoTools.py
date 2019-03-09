#!/usr/bin/env python
import os
import subprocess32
import traci
import time
import numpy
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from threading import RLock
from threading import Thread


debug = True
hang = False
pollingTime = 1

FNULL = open(os.devnull, 'w')

#custom print function which deletes [ * ] with debug mode disabled
def dprint(s):
	s=str(s)
	if debug or not (s.split()[0]=="[" and s.split()[-1]=="]"):
		print(s)

#custom xml writer function
def write_xml(root,location):
	prettyttl = minidom.parseString(ET.tostring(root).decode('utf8')).toprettyxml(indent="   ")
	with open(location,"w") as f:
		f.write(prettyttl.encode("utf8"))

def execute_scenario(launch,scenario,routes,step_size,port,autostart,end,delay,dataCollection,debug,wait=True):
	dprint("[ launching simulation... ]")
	sumoAutoStart=""
	if autostart==True:
		sumoAutoStart=" --start"
	sumoLaunch = str(launch
		+" -n " + scenario +".net.xml"
		+" -r " + routes + ".rou.xml" 
		+ sumoAutoStart
		+" -Q" 
		+ " --step-length " + ("%.2f" % step_size) 
		+ " --remote-port " + str(port)
		#TODO PSEUDO-RANDOM SEED
	).split(" ")

	if (debug):
		sumoProcess = subprocess32.Popen(sumoLaunch) 
	else:
		sumoProcess = subprocess32.Popen(sumoLaunch, stdout=FNULL, stderr=FNULL)

	while (hang==1):
		pass

	time.sleep(2)
	t = traci.connect(port=port)

	if wait==True:
		#Original single simulation code
		accidents = 0
		arrived = 0
		teleported = 0
		agv_speeds = []

		stepsLeft = end
		while(stepsLeft>=0):
			stepsLeft-=1
			t.simulationStep()
			if delay > 0:
				time.sleep(delay)
			if dataCollection:
				accidents += t.simulation.getCollidingVehiclesNumber()
				arrived += t.simulation.getArrivedNumber()
				teleported += t.simulation.getStartingTeleportNumber()

				vehicleIDs = t.vehicle.getIDList()
				if len(vehicleIDs)>0:
					agv_speeds.append(numpy.mean([t.vehicle.getSpeed(veh) for veh in vehicleIDs]))

		if dataCollection:
			dprint("[ sim results: accidents %d, arrived %d, teleported %d, avg speed %f ]"%(accidents,arrived,teleported,numpy.mean(agv_speeds)))
		else:
			dprint("[ simulation completed with no data collection ]")
		
		t.close()
		sumoProcess.wait()
		dprint("[ simulation return code: " + str(sumoProcess.returncode)+ " ]")
		return({
			"accidents":accidents, 
			"arrived":arrived, 
			"teleported":teleported, 
			"agv_speed":numpy.mean(agv_speeds)
		})	
	else:
		dprint("[ simulation launched and running ]")
		return {"process":sumoProcess,"traci":t}

def generate_scenario(sumoScenario,debug,wait=True,**kwargs):
	for part in ["node","edge","connection","type","tllogic","output"]:
		if not kwargs.has_key(part):
			kwargs[part] = sumoScenario
		else:
			dprint("[ custom file generating scenario ]")

	netconvertLaunch = str("netconvert \
			--node-files=" + kwargs["node"] + ".nod.xml \
			--edge-files=" + kwargs["edge"] + ".edg.xml \
			--connection-files=" + kwargs["connection"] + ".con.xml \
			--type-files=" + kwargs["type"] + ".typ.xml \
			--tllogic-files=" + kwargs["tllogic"] + ".tll.xml \
			--output-file=" + kwargs["output"] + ".net.xml").split()

	if (debug):
		netconvertProcess = subprocess32.Popen(netconvertLaunch)
	else:
		netconvertProcess = subprocess32.Popen(netconvertLaunch,stdout=FNULL,stderr=FNULL)
	if wait==True:
		netconvertProcess.wait()
		dprint("[ netconvert return code: " + str(netconvertProcess.returncode) + " ]")
	else: 
		return netconvertProcess
		dprint("[ netconvert process running ]")

def tl_combinations(connectionSets):
	res = []
	base = ""
	'''
	for i in range(connections):
		base+="r"
	for i in range(connections):
		res.append(base[:i]+"G"+base[i+1:])
		res.append(base[:i]+"y"+base[i+1:])
	'''
	# | : : | : | : : : : | => generate base "rrr"
	# => generate combinations
	# => expand combinations according to sets

	for c in connectionSets:
		base += "r"

	for i in range(len(connectionSets)):
		res.append(base[:i]+"G"+base[i+1:])
		res.append(base[:i]+"y"+base[i+1:])

	for l in range(len(res)):
		for i in range(len(connectionSets)):
			ri = len(connectionSets)-1-i
			for e in range(connectionSets[ri]-1):
				res[l] = res[l][:ri]+res[l][ri]+res[l][ri:]


	return res

def generate_traffic_light(indexes,sumoScenario,name):
	scenario = {
		"edg" : ET.parse(sumoScenario+'.edg.xml'),
		"con" : ET.parse(sumoScenario+'.con.xml'),
		"tll" : ET.parse("clean_" + sumoScenario + '.tll.xml'),
		"nod" : ET.parse("clean_" + sumoScenario + '.nod.xml')
	}
	'''
	#load all scenario files as ET
	for f in os.listdir("."):
		ff = f.split('.')
		if len(ff)==3 and ff[0]==sumoScenario and ff[1] in ["edg","con"]:
			scenario[ff[1]]=ET.parse(f)
	for f in os.listdir(folder):
		ff = f.split('.')
		if len(ff)==3 and ff[0]==sumoScenario and ff[1] in ["tll","nod"]:
			scenario[ff[1]]=ET.parse(folder + "/" + f)
	'''
	connectionsToAppend = []
	for index in range(len(indexes)):
		if indexes[index]['type'] == 't':
			#node we are turning into a TL
			nodeid = list(scenario['nod'].getroot())[1:][index].get('id')

			edgeids =[]
			for e in list(scenario['edg'].getroot()):
				if e.get('from')==nodeid or e.get('to')==nodeid:
					edgeids.append(e.get('id'))

			connectionSets = []
			c_i=0
			for e in list(scenario['edg'].getroot()):
				if e.get('to') == nodeid:
					connectionSet = 0
					for c in list(scenario['con'].getroot()):
						if c.get('from')==e.get('id') and c.get('to') in edgeids:
							c.set('tl',str(nodeid))
							c.set('linkIndex',str(c_i))
							c_i+=1
							connectionsToAppend.append(c)
							connectionSet+=1
					connectionSets.append(connectionSet)

			newTLL = ET.SubElement(scenario['tll'].getroot(),'tlLogic')
			newTLL.set('id',str(nodeid))
			newTLL.set('type','static')
			newTLL.set('programID','0')
			newTLL.set('offset','0')

			#alternate durations, first it the red/green phase, then the yellow phase.
			yellow = False
			for logic in tl_combinations(connectionSets):
				phase = ET.SubElement(newTLL,'phase')
				if yellow:
					phase.set('duration',str(indexes[index]['ytime'])) #TODO testing parameter, use meaningful parameters
				else:
					phase.set('duration',str(indexes[index]['grtime'])) #TODO testing parameter, use meaningful parameters
				phase.set('state',logic)
				yellow = not yellow

			#update node file to trafficL_light
			scenario['nod'].getroot()[1:][index].set('type','traffic_light')

		else: # if indexes[index]['type'] == 'p':
			#update node file to priority
			scenario['nod'].getroot()[1:][index].set('type','priority')

	for c in connectionsToAppend:
		scenario['tll'].getroot().append(c)

	write_xml(scenario['tll'].getroot(), name +".tll.xml")
	write_xml(scenario['nod'].getroot(), name +".nod.xml")

#TODO: no multithreading for now on traffic light generation!
def generate_traffic_lights(parametersList, jobs):
	for parameterSet in parametersList:
		generate_traffic_light(parameterSet['scenario'],parameterSet['sumoScenario_orig'],parameterSet['sumoScenario_dest'])

def generate_scenarios(parametersList, jobs,**kwargs):
	done = 0
	todo_queue=parametersList+[]
	currentJobs = 0
	processes = {}
	while done < len(parametersList) or currentJobs>0:
		while currentJobs<jobs and len(todo_queue)>0:
			print("adding one NETCONVERT process")
			parameterSet = todo_queue.pop()
			p = generate_scenario(parameterSet["sumoScenario"],parameterSet["netconvert_output"],wait=False,**parameterSet["kwargs"])
			processes[p.pid]=p
			currentJobs+=1
		pidtodelete=[]
		for pid, p in processes.iteritems():
			p.poll()

			if p.returncode != None:
				print("found an ended NETCONVERT process")
				done+=1
				currentJobs-=1
				dprint("[ netconvert for "+ str(pid)+" return code: " + str(p.returncode) + " ]")
				pidtodelete.append(pid)
		for pid in pidtodelete:
			del(processes[pid])

def execute_scenarios(parametersList, jobs):

	lock = RLock()
	results_d = {}
	results = []
	'''
		accidents = 0
		arrived = 0
		teleported = 0
		agv_speeds = []
			\->avg_speed = ##
	'''

	done = 0
	todo_queue=parametersList+[]
	todo_queue.reverse()
	currentJobs = 0
	processes = {}
	simid_inc = 0
	while done < len(parametersList) or currentJobs>0:
		#print("done("+str(len(parametersList))+"): "+str(done)+" & currentJobs: "+str(currentJobs))
		while currentJobs<jobs and len(todo_queue)>0:
			print("adding one SUMO process")
			parameterSet = todo_queue.pop()
			sim = execute_scenario(
				parameterSet["launch"],
				parameterSet["sumoScenario"],
				parameterSet["sumoRoutes"],
				parameterSet["sumoStepSize"],
				parameterSet["sumoPort"]+simid_inc,
				parameterSet["sumoAutoStart"],
				parameterSet["sumoEnd"],
				parameterSet["sumoDelay"],
				parameterSet["dataCollection"],
				parameterSet["sumoOutput"],
				wait=False
			)
			processes[simid_inc]={
				"process":sim["process"],
				"traci":sim["traci"],
				"stepsLeft": parameterSet['sumoEnd'],
				"sumoDelay": parameterSet["sumoDelay"],
				"dataCollection": parameterSet["dataCollection"],				
				"accidents": 0,
				"arrived": 0,
				"teleported": 0,
				"agv_speeds": []	
			}
			thread = Thread(target = advance_simulation, args = (simid_inc, processes[simid_inc],results_d,lock))
			thread.start()

			currentJobs+=1
			simid_inc+=1

		simidtodelete=[]
		for simid, procinfo in processes.iteritems():
			procinfo["process"].poll()
			if procinfo["process"].returncode != None:
				print("found an ended SUMO process")
				done+=1
				currentJobs-=1
				dprint("[ simulation "+ str(simid)+" return code: " + str(procinfo["process"].returncode) + " ]")
				simidtodelete.append(simid)

		for simidtd in simidtodelete:
			del(processes[simidtd])	

		time.sleep(pollingTime)

	#simids = results_d.keys()
	#simids.sort()
	simids = list(range(simid_inc))
	for res in simids:
		results.append(results_d[res])
	'''
	#TRIVIAL SINGLE-SIMULATION-AT-A-TIME SOLUTION
	for parameterSet in parametersList:
		print("EXECUTING SCENARIO" + parameterSet["sumoScenario"]+" PORT "+str(parameterSet["sumoPort"]))
		results.append(execute_scenario(
			parameterSet["launch"],
			parameterSet["sumoScenario"],
			parameterSet["sumoRoutes"],
			parameterSet["sumoStepSize"],
			parameterSet["sumoPort"],
			parameterSet["sumoAutoStart"],
			parameterSet["sumoEnd"],
			parameterSet["sumoDelay"],
			parameterSet["dataCollection"],
			parameterSet["sumoOutput"],
		))
	'''

	print("dict: " + str(len(results_d)))
	print("list: " + str(len(results)))
	return results

def advance_simulation(simid, procinfo, results_d, lock):
	#data collection via traci
	while(procinfo["stepsLeft"]>=0):
		procinfo["stepsLeft"]-=1
		procinfo["traci"].simulationStep()
		if procinfo["sumoDelay"] > 0:
			time.sleep(procinfo["sumoDelay"])
		if procinfo["dataCollection"]:
			procinfo["accidents"] += procinfo["traci"].simulation.getCollidingVehiclesNumber()
			procinfo["arrived"] += procinfo["traci"].simulation.getArrivedNumber()
			procinfo["teleported"] += procinfo["traci"].simulation.getStartingTeleportNumber()

			vehicleIDs = procinfo["traci"].vehicle.getIDList()
			if len(vehicleIDs)>0:
				procinfo["agv_speeds"].append(numpy.mean([procinfo["traci"].vehicle.getSpeed(veh) for veh in vehicleIDs]))				
	
	procinfo["traci"].close()

	lock.acquire()
	try:
		results_d[simid]={
			"accidents":procinfo["accidents"], 
			"arrived":procinfo["arrived"], 
			"teleported":procinfo["teleported"], 
			"agv_speed":numpy.mean(procinfo["agv_speeds"])
		}						
	finally:
		lock.release()