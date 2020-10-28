#!/usr/bin/env python
import os
import subprocess32
import traci
import time
import numpy as np
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from threading import RLock
from threading import Thread

debug = False
hang = False
pollingTime = 10

implemented_objectives = ["arrived","teleported","accidents","fuel","avg_speed","var_speeds","CO2","PMx"]
junction_types = ["priority","traffic_light"]

FNULL = open(os.devnull, 'w')

#custom print function which doesn't log strings like [ * ] with debug mode disabled
def dprint(s):
	s=str(s)
	if debug or not (s.split()[0]=="[" and s.split()[-1]=="]"):
		print("TJS>\t"+s)

#custom xml writer function
def write_xml(root,location):
	prettyttl = minidom.parseString(ET.tostring(root).decode('utf8')).toprettyxml(indent="   ")
	with open(location,"w") as f:
		f.write(prettyttl.encode("utf8"))

def execute_scenario(launch,scenario,routes,step_size,port,autostart,end,delay,debug,seed,objectives=[],wait=True):
	dprint("[ launching simulation on port "+ str(port) + "... ]")
	sumoAutoStart = ""
	if autostart == True:
		sumoAutoStart = " --start"
	sumoRandom = ""
	if seed=="-1":
		sumoRandom = " --random"
	else:
		sumoRandom = " --seed " +str(seed)
	print((".rou.xml,".join(routes) if type(routes)==list  else routes)+".rou.xml" )
	sumoLaunch = str(launch
		+" -n " + scenario +".net.xml"
		+" -r " + (".rou.xml,".join(routes) if type(routes)==list  else routes)+".rou.xml" 
		+ sumoAutoStart
		+ sumoRandom
		+" -Q" 
		+ " --step-length " + ("%.2f" % step_size) 
		+ " --remote-port " + str(port)
		#TODO PSEUDO-RANDOM SEED (seed parameter)
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
		avg_speeds = []
		sum_fuel_consumption = []

		stepsLeft = end
		while(stepsLeft>=0):
			stepsLeft-=1
			t.simulationStep()
			if delay > 0:
				time.sleep(delay)
			if len(objectives)>0:
				if "accidents" in objectives:
					accidents += t.simulation.getCollidingVehiclesNumber()
				if "arrived" in objectives:
					arrived += t.simulation.getArrivedNumber()
				if "teleported" in objectives:
					teleported += t.simulation.getStartingTeleportNumber()

				if "fuel" in objectives or "avg_speed" in objectives:
					vehicleIDs = t.vehicle.getIDList()
					if len(vehicleIDs)>0:
						if "avg_speed" in objectives:
							avg_speeds.append(np.mean([t.vehicle.getSpeed(veh) for veh in vehicleIDs]))
						if "fuel" in objectives:
							sum_fuel_consumption.append(np.sum([t.vehicle.getFuelConsumption(veh) for veh in vehicleIDs]))

		if len(objectives)>0:
			dprint("[ sim results: accidents %d, arrived %d, teleported %d, avg speed %f ]"%(accidents,arrived,teleported,np.mean(avg_speeds)))
		else:
			dprint("[ simulation completed with no data collection ]")
		
		t.close()
		sumoProcess.wait()
		dprint("[ simulation return code: " + str(sumoProcess.returncode)+ " ]")
		return({
			"accidents":accidents, 
			"arrived":arrived, 
			"teleported":teleported, 
			"avg_speed":np.mean(avg_speeds),
			"sum_fuel_consumption":np.sum(sum_fuel_consumption)
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

def generate_traffic_light(indexes,sumoScenario,name,ind_map=None):
	scenario = {
		"edg" : ET.parse(sumoScenario+'.edg.xml'),
		"con" : ET.parse(sumoScenario+'.con.xml'),
		"tll" : ET.parse("clean_" + sumoScenario + '.tll.xml'),	#contains default tll & con
		"nod" : ET.parse("clean_" + sumoScenario + '.nod.xml')
	}
	if ind_map==None:
		ind_map=[True]*len(indexes) #NOTE this does not consider allowed junction_types, will not match the right junction settings, but it's all True so it's not a problem

	default_tll_connections =  [c for c in scenario["tll"].getroot() if c.tag=="connection"]
	for t in scenario["tll"].getroot():
		if t.tag=="connection":
			scenario["tll"].getroot().remove(t)

	connectionsToAppend = []
	nodes = list(scenario['nod'].getroot())[1:]
	ind_index=0
	for index in range(len(indexes)):
		if nodes[index].get("type") in junction_types:
			if ind_map[ind_index]:
				if indexes[ind_index]['type'] == 't':
					#node we are turning into a TL
					nodeid = nodes[index].get('id')

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
							phase.set('duration',str(indexes[ind_index]['ytime'])) #TODO testing parameter, use meaningful parameters
						else:
							phase.set('duration',str(indexes[ind_index]['grtime'])) #TODO testing parameter, use meaningful parameters
						phase.set('state',logic)
						yellow = not yellow

					#update node file to trafficL_light
					scenario['nod'].getroot()[1:][index].set('type','traffic_light')

				else:# indexes[index]['type'] == 'p':
					#update node file to priority
					scenario['nod'].getroot()[1:][index].set('type','priority')
				#else:#indexes[index]['type'] == '??':
					#update node file to ??
					#scenario['nod'].getroot()[1:][index].set('type','??')
			ind_index+=1

	for c in default_tll_connections:
		scenario['tll'].getroot().append(c)
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
			parameterSet = todo_queue.pop()
			p = generate_scenario(parameterSet["sumoScenario"],parameterSet["netconvert_output"],wait=False,**parameterSet["kwargs"])
			processes[p.pid]=p
			currentJobs+=1
		pidtodelete=[]
		for pid, p in processes.iteritems():
			p.poll()

			if p.returncode != None:
				done+=1
				currentJobs-=1
				dprint("[ netconvert for "+ str(pid)+" return code: " + str(p.returncode) + " ]")
				pidtodelete.append(pid)
		for pid in pidtodelete:
			del(processes[pid])

def execute_scenarios(parametersList, jobs, port):

	lock = RLock()
	results_d = {}
	results = []
	'''
		accidents = 0
		arrived = 0
		teleported = 0
		avg_speeds = []
			\->avg_speed = ##
	'''

	portPool = 	list(np.array((range(jobs)))+port)
	dprint("[ Port pool: " + str(portPool[0]) + "-" + str(portPool[-1]) + " ]")

	done = 0
	todo_queue=parametersList+[]
	todo_queue.reverse()
	currentJobs = 0
	processes = {}
	simid_inc = 0
	while done < len(parametersList) or currentJobs>0:
		while currentJobs<jobs and len(todo_queue)>0:
			parameterSet = todo_queue.pop()
			usable_port = portPool.pop()
			sim = execute_scenario(
				parameterSet["launch"],
				parameterSet["sumoScenario"],
				parameterSet["sumoRoutes"],
				parameterSet["sumoStepSize"],
				usable_port,
				parameterSet["sumoAutoStart"],
				parameterSet["sumoEnd"],
				parameterSet["sumoDelay"],
				parameterSet["sumoOutput"],
				parameterSet["sumoSeed"],
				objectives = parameterSet["objectives"],
				wait=False
			)
			processes[simid_inc]={
				"process":sim["process"],
				"traci":sim["traci"],
				"sumoPort": usable_port,
				"stepsLeft": parameterSet['sumoEnd'],
				"sumoDelay": parameterSet["sumoDelay"],
				"objectives": parameterSet["objectives"],
				"accidents": 0,
				"arrived": 0,
				"teleported": 0,
				"avg_speed": [],
				"fuel": [],
				"CO2": [],
				"PMx": []
			}
			thread = Thread(target = advance_simulation, args = (simid_inc, processes[simid_inc],results_d,lock))
			thread.start()

			currentJobs+=1
			simid_inc+=1

		simidtodelete=[]
		for simid, procinfo in processes.iteritems():
			procinfo["process"].poll()
			if procinfo["process"].returncode != None:
				done+=1
				currentJobs-=1
				portPool.append(procinfo["sumoPort"])
				dprint("[ simulation "+ str(simid)+" return code: " + str(procinfo["process"].returncode) + " ]")
				simidtodelete.append(simid)

		for simidtd in simidtodelete:
			del(processes[simidtd])	

		#yeah, I know, it's busy waiting, sub-ideal to say the least, 
		# "it's just for testing" - AC 2020
		current_time = time.time()
		while time.time()<current_time+pollingTime:
			pass

		#time.sleep(pollingTime)

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
	
	return results

def advance_simulation(simid, procinfo, results_d, lock):
	#data collection via traci
	while(procinfo["stepsLeft"]>=0):
		procinfo["stepsLeft"]-=1
		print(str(simid)+" step")
		procinfo["traci"].simulationStep()
		if procinfo["sumoDelay"] > 0:
			time.sleep(procinfo["sumoDelay"])
		if len(procinfo["objectives"])>0:
			if "accidents" in procinfo["objectives"]:
				procinfo["accidents"] += procinfo["traci"].simulation.getCollidingVehiclesNumber()
			if "arrived" in procinfo["objectives"]:
				procinfo["arrived"] += procinfo["traci"].simulation.getArrivedNumber()
			if "teleported" in procinfo["objectives"]:
					procinfo["teleported"] += procinfo["traci"].simulation.getStartingTeleportNumber()

			print(str(simid)+" start retrieving")
			if "fuel" in procinfo["objectives"] or "avg_speed" in procinfo["objectives"] or "var_speeds" in procinfo["objectives"] or "CO2" in procinfo["objectives"] or "PMx" in procinfo["objectives"]:
				vehicleIDs = procinfo["traci"].vehicle.getIDList()
				if len(vehicleIDs)>0:
					if "avg_speed" in procinfo["objectives"]:
						procinfo["avg_speed"].append(np.mean([procinfo["traci"].vehicle.getSpeed(veh) for veh in vehicleIDs]))				
					if "var_speeds" in procinfo["objectives"]:
						procinfo["avg_speed"].append(np.var([procinfo["traci"].vehicle.getSpeed(veh) for veh in vehicleIDs]))				
					if "fuel" in procinfo["objectives"]:
						procinfo["fuel"].append(np.sum([procinfo["traci"].vehicle.getFuelConsumption(veh) for veh in vehicleIDs]))
					if "CO2" in procinfo["objectives"]:
						procinfo["CO2"].append(np.sum([procinfo["traci"].vehicle.getCO2Emission(veh) for veh in vehicleIDs]))
					if "PMx" in procinfo["objectives"]:
						procinfo["PMx"].append(np.sum([procinfo["traci"].vehicle.getPMxEmission(veh) for veh in vehicleIDs]))
			print(str(simid)+" stop retrieving")
	
	procinfo["traci"].close()

	lock.acquire()
	try:
		results_d[simid]={}
		for k in procinfo["objectives"]:
			if type(procinfo[k])==list:
				results_d[simid][k] = np.mean(procinfo[k])
			else:
				results_d[simid][k] = procinfo[k]
	finally:
		lock.release()

def generate_route(route,wait=True):
	dprint("[ generating route... ]")
	randomTripsLaunch = str(os.environ["SUMO_HOME"]+"/tools/randomTrips.py \
			-n " + route['sumoScenario'] + ".net.xml \
			--prefix " + route["prefix"] 
			+ ((" --trip-attributes=type=\"type_"+route['emissionClass']+"\"") if "emissionClass" in route.keys() else "")
			+ " -p " + str(route["repetitionRate"])
			+ " -e " + str(route["sumoEnd"])
			+ ((" --additional-file " + route["output"] + ".add.xml") if "emissionClass" in route.keys() else "")
			+ " -o " + route["output"] + ".trips.xml"
			+ " -r " + route["output"] + ".rou.xml"
		).split()

	if "emissionClass" in route.keys():
		with open(route["output"]+".add.xml","w+") as addfile:
			addfile.write(
				"<additional>\n<vType vClass=\"passenger\" id=\"type_"+route['emissionClass']+"\" emissionClass=\""+route["emissionClass"]+"\" length=\"5\" maxSpeed=\"70\" carFollowModel=\"Krauss\" accel=\"2.6\" decel=\"4.5\" sigma=\"0.5\"/>\n</additional>"
			)

	if (debug):
		randomTripsProcess = subprocess32.Popen(randomTripsLaunch)
	else:
		randomTripsProcess = subprocess32.Popen(randomTripsLaunch,stdout=FNULL,stderr=FNULL)

	if wait==True:
		randomTripsProcess.wait()
		os.remove(route["output"] + ".rou.alt.xml")
		dprint("[ randomtrips return code: " + str(randomTripsProcess.returncode) + " ]")
	else: 
		return randomTripsProcess
		dprint("[ randomtrips process running ]")


def generate_routes(routes, jobs):
	#TODO multithreading
	#for route in routes:
	#	generate_route(route)
	done = 0
	todo_queue=routes+[]
	currentJobs = 0
	processes = {}
	while done < len(routes) or currentJobs>0:
		while currentJobs<jobs and len(todo_queue)>0:
			parameterSet = todo_queue.pop()
			p = generate_route(parameterSet,wait=False)
			processes[p.pid]=p
			currentJobs+=1
		pidtodelete=[]
		for pid, p in processes.iteritems():
			p.poll()
			if p.returncode != None:
				done+=1
				currentJobs-=1
				dprint("[ randomtrips for "+ str(pid)+" return code: " + str(p.returncode) + " ]")
				pidtodelete.append(pid)
		for pid in pidtodelete:
			del(processes[pid])
