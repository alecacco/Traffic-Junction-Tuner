#!/usr/bin/env python

#argparse stuff
import argparse
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer.")
parser.add_argument("-g","--generations", type=int, help="number of generation for the genetic algorithm", default=1)
parser.add_argument("-l","--launch", type=str, help="Sumo executable to use. E.G. \"sumo\" or \"sumo-gui\". Default is \"sumo\"", default="sumo")
parser.add_argument("-p","--port", type=int, help="TraCI connection port to Sumo. Default is 27910", default=27910)
parser.add_argument("-s","--scenario", type=str, help="Scenario prefix - uses standard Scenario file extension", default="semaforoS")
parser.add_argument("-r","--recreate", type=int, help="Set to 1 to regenerate the net.xml file from the scenario files, 0 to load the current one. Default is 1", default=1)
parser.add_argument("-d","--debug", type=int, help="Set to 1 to see debug output. Default is 1", default=0)
parser.add_argument("-a","--autostart", type=int, help="Set to 1 to start the simulation automatically. Default is 1", default=0)
parser.add_argument("-e","--end", type=int, help="Simulation duration in step number. Default is 3600.", default=3600)
parser.add_argument("-sd","--step-delay", type=float, help="Delay of each step, useful for GUI demostrations. Default is 0", default=0)

args = parser.parse_args()

#custom print function which deletes [ * ] with debug mode disabled
def dprint(s):
	if args.debug==1 or not (s.split()[0]=="[" and s.split()[-1]=="]"):
		print(s)

#imports
dprint("[ Loading traci library... ]")
import traci
dprint("[ Loading other stuff... ]")
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import subprocess32
import time
import datetime
import os
from inspyred import benchmarks
from inspyred_utils import NumpyRandomWrapper
from multi_objective import run
from inspyred.ec.emo import Pareto

#custom xml writer function
def write_xml(root,location):
	prettyttl = minidom.parseString(ET.tostring(root).decode('utf8')).toprettyxml(indent="   ")
	with open(location,"w") as f:
		f.write(prettyttl.encode("utf8"))	

#SUMO/TraCI parameters
sumoAutoStart=""
if args.autostart==1:
	sumoAutoStart=" --start"
sumoScenario = args.scenario
sumoLaunch = str(args.launch+" -c "+ args.scenario +".sumo.cfg"+sumoAutoStart+" -Q").split(" ")
sumoPort = args.port
sumoEnd = args.end
sumoDelay = args.step_delay

sumoProcess = None

#other parameters
recreateScenario = args.recreate==1
gen = 0
ind = 0

#simulations result
results = []
folder = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H-%M-%S')
os.mkdir(folder)

def execute_scenario():
	dprint("[ launching simulation... ]")
	sumoProcess = subprocess32.Popen(sumoLaunch, stdout=subprocess32.PIPE, stderr=subprocess32.PIPE)
	time.sleep(1)
	t = traci.connect(port=sumoPort)

	accidents = 0
	arrived = 0

	stepsLeft = sumoEnd
	while(stepsLeft>=0):
		stepsLeft-=1
		t.simulationStep()
		if sumoDelay > 0:
			time.sleep(sumoDelay)
		accidents += t.simulation.getCollidingVehiclesNumber()
		arrived += t.simulation.getArrivedNumber()

	t.close()
	sumoProcess.wait()
	dprint ("[ simulation return code: " + str(sumoProcess.returncode)+ " ]")
	return({"accidents":accidents, "arrived":arrived})

def generate_scenario(**kwargs):
	for part in ["node","edge","connection","type","tllogic","output"]:
		if part not in kwargs:
			kwargs[part] = sumoScenario

	netconvertLaunch = str("netconvert \
			--node-files=" + kwargs["node"] + ".nod.xml \
			--edge-files=" + kwargs["edge"] + ".edg.xml \
			--connection-files=" + kwargs["connection"] + ".con.xml \
			--type-files=" + kwargs["type"] + ".typ.xml \
			--tllogic-files=" + kwargs["tllogic"] + ".tll.xml \
			--output-file=" + kwargs["output"] + ".net.xml").split()

	netconvertProcess = subprocess32.Popen(netconvertLaunch,stdout=subprocess32.PIPE)
	netconvertProcess.wait()
	dprint ("[ netconvert return code: " + str(netconvertProcess.returncode) + " ]")

def clean_scenario():
	nod = ET.parse(sumoScenario + ".nod.xml").getroot()
	for e in list(nod)[1:]:
		e.set("type", "priority")
	write_xml(nod, "clean_" + sumoScenario + '.nod.xml')

	tll = ET.parse(sumoScenario + ".tll.xml").getroot()
	tll.clear()
	write_xml(tll, "clean_" + sumoScenario + '.tll.xml')

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

'''
load current generation files and generates next generation tll and nod files based on input parameter
parameter indexes is a list of dictionaries, each of them specifying informations for a specific junction. 
	Example:
	indexes = [
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10}, #THIS is the main junction 
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10},
		{'type':'t','ytime':3,'grtime':10},
	]
'''
def generate_traffic_light(indexes):
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

	write_xml(scenario['tll'].getroot(), folder+"/gen" + str(gen) + "_" + str(ind) + "_" + sumoScenario+".tll.xml")
	write_xml(scenario['nod'].getroot(), folder+"/gen" + str(gen) + "_" + str(ind) + "_" + sumoScenario+".nod.xml")

class TJBenchmark(benchmarks.Benchmark):
	
	results_storage = {}
	junctionNumber = 0

	def evaluatorator(self,objective):
		def evaluator(self,candidates,args):
			global gen
			global ind
			ind = 0
			#generate and execute_scenario
			for candidate in candidates:
				candidate['gen'] = gen
				candidate['ind'] = ind

				generate_traffic_light(candidate['scenario'])

				generate_scenario(
					node = folder + "/gen" + str(gen) + "_" + str(ind) + "_" + sumoScenario,
					tllogic = folder + "/gen" + str(gen) + "_" + str(ind) + "_" + sumoScenario
				)
				sim_result = execute_scenario() 
				TJBenchmark.results_storage[str(candidate['gen'])+'_'+str(candidate['ind'])] = {}
				for key,value in sim_result.items():
					TJBenchmark.results_storage[
						str(candidate['gen'])+'_'+str(candidate['ind'])
					][str(key)] = value
				ind += 1
			gen += 1
			return [
				TJBenchmark.results_storage[
					str(candidate['gen'])+'_'+str(candidate['ind'])
				][objective] 
				for candidate in candidates
			]
		return evaluator

	def __init__(self, junctionNumber=0, objectives=["accidents","arrived"]):
		benchmarks.Benchmark.__init__(self, self.junctionNumber, len(objectives))
		self.junctionNumber = junctionNumber
		#self.bounder = ?
		self.maximize = False
		#self.evaluators = [cls(dimensions).evaluator for cls in objectives]
		self.evaluators = [self.evaluatorator(objective) for objective in objectives]
		clean_scenario()

	'''
	def evaluate_accidents(self,candidate,args):
		return results_storage[candidate]['accidents']

	def evaluator_accidents(self, candidates, args):
		return [evaluate(candidate) for candidate in candidates]

	def evaluate_arrived(self,candidate,args):
		return results_storage[candidate]['arrived']

	def evaluator_arrived(self, candidates, args):
		return [evaluate(candidate) for candidate in candidates]
	'''
	def generator(self, random, args):
		#return [random.uniform(-5.0, 5.0) for _ in range(self.dimensions)]
		global ind
		new_ind = {
			'gen':0,
			'ind':ind,
			'scenario':[ #TODO definitely not ideal, should apply some constraints!!
				{
					'type':random.choice(['p','t']),
					'ytime':random.uniform(high=10,low=1),
					'grtime':random.uniform(high=50,low=10)
				} 
				for _ in range(self.junctionNumber)
			]
		}
		ind +=1
		return new_ind
		
	def evaluator(self, candidates, args):
		fitness = [evaluator(self,candidates, args) for evaluator in self.evaluators]
		return map(Pareto, zip(*fitness))

	def cross(random,mom,dad,args):
		pass

	def mutate(random,candidate,args):
		pass

if __name__ ==  "__main__":
	if recreateScenario:
		dprint("[ Regenerating scenario files... ]")
		generate_scenario()

	problem = TJBenchmark(junctionNumber=9)
	run(NumpyRandomWrapper(),problem, pop_size=10, max_generations=args.generations)
	'''
	#load scenario, convert all junctions to "priority" and saving as gen0 scenario in $folder
	clean_scenario()	

	while gen < args.generations:
		if gen>0:
			generate_scenario(
				node = folder + "/gen" + str(gen) + "_" + str(ind) + "_" + sumoScenario,
				tllogic = folder + "/gen" + str(gen) + "_" + str(ind) + "_" + sumoScenario
			)
		# execute scenario
		sim_result = execute_scenario() 
		results.append(sim_result) 
		# check output
		# decide new parameters
		# edit scenario
		generate_traffic_light([
				{'type':'p','ytime':3,'grtime':10},
				{'type':'p','ytime':3,'grtime':10},
				{'type':'t','ytime':3,'grtime':10}, #THIS FFS is the main junction with a meaningful place to put a traffic light
				{'type':'p','ytime':3,'grtime':10},
				{'type':'p','ytime':3,'grtime':10},
				{'type':'p','ytime':3,'grtime':10},
				{'type':'p','ytime':3,'grtime':10},
				{'type':'p','ytime':3,'grtime':10},
				{'type':'p','ytime':3,'grtime':10},
			])

		gen += 1


	print results
	'''

