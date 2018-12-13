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
parser.add_argument("-mr","--mutation-rate", type=float, help="Rate of mutation. Default is 0.1", default=0.1)
parser.add_argument("-of","--offspring", type=int, help="Maximun number of offspring. Default is 2", default=2)
parser.add_argument("-cr","--crossover-rate", type=float, help="Rate of crossover. Default is 0.8", default=0.8)
parser.add_argument("-ps","--pop-size", type=int, help="Population size, 5 as default", default=5)
parser.add_argument("-ha","--hang", type=int, help="Set to 1 to hang the program before the simulation, in order to manually connect to problematic scenarios via TraCI", default=0)
parser.add_argument("-so","--sumo-output", type=int, help="Enable simulator stdout/stderr. WARNING: simulation are _considerably_ verbose.", default = 0)
parser.add_argument("-no","--netconvert-output", type=int, help="Enable netconvert stdout/stderr.", default = 0)

parser.add_argument("-y_min","--yellow_min", type=int, help="Min time for yellow. Default is 1", default = 1)
parser.add_argument("-y_max","--yellow_max", type=int, help="Max time for yellow. Default is 10", default = 10)
parser.add_argument("-gr_min","--green_min", type=int, help="Min time for green and red. Default is 1", default = 1)
parser.add_argument("-gr_max","--green_max", type=int, help="Max time for green and red. Default is 40", default = 40)

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
import math
import pickle

from inspyred import benchmarks
from inspyred_utils import NumpyRandomWrapper
from multi_objective import run
from inspyred.ec.emo import Pareto
from inspyred.ec.variators import mutator
from inspyred.ec.variators import crossover

FNULL = open(os.devnull, 'w')

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
ind = 0
junctionNumber = 998

#simulations result
results = []
folder = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H-%M-%S')
os.mkdir(folder)


def execute_scenario():
	dprint("[ launching simulation... ]")
	if args.sumo_output==1:
		sumoProcess = subprocess32.Popen(sumoLaunch) 
	else:
		sumoProcess = subprocess32.Popen(sumoLaunch, stdout=FNULL, stderr=FNULL)
	time.sleep(1)
	#while (args.hang==1):
	#	pass
	t = traci.connect(port=sumoPort)

	accidents = 0
	arrived = 0
	teleported = 0

	stepsLeft = sumoEnd
	while(stepsLeft>=0):
		stepsLeft-=1
		t.simulationStep()
		if sumoDelay > 0:
			time.sleep(sumoDelay)
		accidents += t.simulation.getCollidingVehiclesNumber()
		arrived += t.simulation.getArrivedNumber()
		teleported += t.simulation.getStartingTeleportNumber()

	dprint("[ sim results: accidents %d, arrived %d, teleported %d ]"%(accidents,arrived,teleported))

	t.close()
	sumoProcess.wait()
	dprint ("[ simulation return code: " + str(sumoProcess.returncode)+ " ]")
	return({"accidents":accidents, "arrived":arrived, "teleported":teleported})

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

	if (args.netconvert_output==1):
		netconvertProcess = subprocess32.Popen(netconvertLaunch)
	else:
		netconvertProcess = subprocess32.Popen(netconvertLaunch,stdout=FNULL,stderr=FNULL)
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

	write_xml(scenario['tll'].getroot(), folder+"/ind" + str(ind) + "_" + sumoScenario+".tll.xml")
	write_xml(scenario['nod'].getroot(), folder+"/ind" + str(ind) + "_" + sumoScenario+".nod.xml")

class TJBenchmark(benchmarks.Benchmark):

	results_storage = {}
	
	def evaluatorator(self,objective):
		def evaluate(self,candidates,args):
			global ind
			#ind = 0
			#generate and execute_scenario
			for candidate in candidates:
				if not TJBenchmark.results_storage.has_key(pickle.dumps(candidate)):
					dprint("[ evaluating - ind:"+str(ind)+" ]")
					candidate['ind'] = ind

					generate_traffic_light(candidate['scenario'])

					generate_scenario(
						node = folder + "/ind" + str(ind) + "_" + sumoScenario,
						tllogic = folder + "/ind" + sumoScenario
					)
					sim_result = execute_scenario()
					TJBenchmark.results_storage[pickle.dumps(candidate)] = {}
					for key,value in sim_result.items():
						TJBenchmark.results_storage[
							pickle.dumps(candidate)
						][str(key)] = value
					ind += 1
			#gen += 1
			return [
				TJBenchmark.results_storage[
					pickle.dumps(candidate)
				][objective]
				for candidate in candidates
			]
		return evaluate

	def __init__(self, objectives=["accidents","arrived"]):
		benchmarks.Benchmark.__init__(self, junctionNumber, len(objectives))
		self.bounder = TJTBounder()
		self.maximize = False
		self.evaluators = [self.evaluatorator(objective) for objective in objectives]

		#self.variator = [mutator,crossover]
		
		clean_scenario()

	def generator(self, random, args):
		dprint("[ generating initial population ]")
		#return [random.uniform(-5.0, 5.0) for _ in range(self.dimensions)]
		global ind
		new_ind = {
			'ind':ind,
			'sigmaMutator':1,
			'scenario':[ #TODO definitely not ideal, should apply some constraints!!
				{
					'type':random.choice(['p','t']),
					'ytime':random.uniform(high=10,low=1),
					'grtime':random.uniform(high=50,low=10)
					
				}
				for _ in range(junctionNumber)
			]
		}
		ind +=1
		return new_ind

	def evaluator(self, candidates, args):
		fitness = [evaluator(self,candidates, args) for evaluator in self.evaluators]
		dprint("[ evaluation results: " + str(fitness) + " ]")
		return map(Pareto, zip(*fitness))
		
		
@mutator
def mutate(random, candidate, args):
	dprint("[ entering mutate ]")
	if(args["mutationRate"] >= random.uniform(0,1)):
		dprint("[ \t->mutation happened ]")
		sigmaMutator = candidate['sigmaMutator']
		candidate['sigmaMutator'] = candidate['sigmaMutator'] * math.exp( (1.0/math.sqrt(junctionNumber)) * random.gauss(0,1) )
		if(candidate['sigmaMutator']  < 0.01):
			candidate['sigmaMutator']  = 0.01
		junctions = candidate['scenario']
		for junction in junctions:
		
			if(junction['type'] == 't'):
			
				if(sigmaMutator*random.gauss(0,1) > 1):
						junction['type']  = 'p'
				else:
					ytime = 0
					while (ytime == 0):
						ytime = round(junction['ytime'] + random.gauss(0,1))
					if(ytime < 0):
						ytime = -1 * ytime
					junction['ytime'] = ytime
					grtime = 0
					while (grtime == 0):
						grtime = round(junction['grtime'] + random.gauss(0,1))
					if(grtime < 0):
						grtime = -1 * grtime
					junction['grtime'] = grtime
					
			elif(junction['type'] == 'p'):
			
				if(sigmaMutator * random.gauss(0,1) > 1):
					junction['type'] = 't'
					ytime = 0
					while (ytime == 0):
						ytime = round(junction['ytime'] + random.gauss(0,1))
					if(ytime < 0):
						ytime = -1 * ytime
					junction['ytime'] = ytime
					grtime = 0
					while (grtime == 0):
						grtime = round(junction['grtime'] + random.gauss(0,1))
					if(grtime < 0):
						grtime = -1 * grtime
					junction['grtime'] = grtime
					
		candidate['scenario']=junctions
	return candidate
	"""
	def mutate(random, candidate, args):
		treshold = random.uniform(0,1)
		mutationTreshold = random.uniform(0,1)
		li = candidate['scenario']
		for junction in li:
			if(mutationTreshold<0.99):
				if(junction['type'] == 't'):
					if(treshold<0.33):
						junction['type']  = 'p'
					elif(treshold<0.66):
						ytime = round(junction['ytime'] +random.gauss(0,1))
						if(ytime < 0):
							ytime = -1*ytime
						junction['ytime'] = ytime
					else:
						grtime = round(junction['grtime']+random.gauss(0,1))
						if(grtime < 0):
							grtime = -1*grtime
						junction['grtime'] = grtime
				elif(junction['type'] == 'p'):
					if(treshold <0.5):
						junction['type'] = 't'
					elif(treshold <0.75):
						ytime = round(junction['ytime'] +random.gauss(0,1))
						if(ytime < 0):
							ytime = -1*ytime
						junction['ytime'] = ytime
					else:
						grtime = round(junction['grtime']+random.gauss(0,1))
						if(grtime < 0):
							grtime = -1*grtime
						junction['grtime'] = grtime
		candidate['scenario']=li
		return candidate
		"""
@crossover
def cross(random, mom, dad, args):
	dprint("[ entering crossover ]")
	offspringNumber = args["offspring"]
	crossoverRate = args["crossoverRate"]
	offsprings =[]
	#newGen = mom["gen"] + 1
	offspring = {
			'ind':-1,
			'sigmaMutator':1,
			'scenario':[ #TODO definitely not ideal, should apply some constraints!!
				{
					'type':random.choice(['p','t']),
					'ytime':random.uniform(high=args.y_max,low=args.y_min),
					'grtime':random.uniform(high=args.gr_max,low=args.gr_min)
					
				}
				for _ in range(junctionNumber)
			]
		}
		
	if(crossoverRate >= random.uniform(0,1)):
		dprint("[ ->crossover happened ]")
		for i in range(offspringNumber):
			junction = 0
			for couple in zip(mom['scenario'],dad['scenario']):
				
				tresholdType = random.uniform(0,1)
				tresholdGrtime = random.uniform(0,1)
				tresholdYtime = random.uniform(0,1)

				if(tresholdType < 0.5):
					offspring['scenario'][junction]['type'] = couple[0]['type'] 
				else:
					offspring['scenario'][junction]['type'] = couple[1]['type']

				offspring['scenario'][junction]['grtime'] = couple[0]['grtime'] * tresholdGrtime + couple[1]['grtime'] * (1-tresholdGrtime)
				offspring['scenario'][junction]['ytime'] = couple[0]['ytime'] * tresholdYtime + couple[1]['ytime'] * (1-tresholdYtime)
				junction += 1
				
			offsprings.append(offspring)
			
	return offsprings
	
class TJTBounder(object):    
    def __call__(self, candidate, args):
        
		for junction in candidate["scenario"]
			if( junction["ytime"] < args.y_min ):
				junction["ytime"] = args.y_min
			if( junction["ytime"] > args.y_max ):
				junction["ytime"] = args.y_max
			if( junction["grtime"] < args.gr_min ):
				junction["grtime"] = args.gr_min
			if( junction["grtime"] > args.gr_max ):
				junction["grtime"] = args.gr_max
		
        return candidate
		
		
if __name__ ==  "__main__":
	if recreateScenario:
		dprint("[ Regenerating scenario files... ]")
		generate_scenario()

	problem = TJBenchmark(objectives=["accidents","teleported"])
	margs = {}
	margs["mutationRate"] = args.mutation_rate
	margs["crossoverRate"] = args.crossover_rate
	margs["offspring"] = args.offspring
	margs["variator"] = [cross,mutate]
	margs["max_generations"] = args.generations
	margs["pop_size"] = args.pop_size
	margs["num_vars"] = 2	
	margs["tournament_size"] = 2	
	margs["y_min"] = args.y_min		
	margs["y_max"] = args.y_max		
	margs["gr_min"] = args.gr_min		
	margs["gr_max"] = args.gr_max
	
	res = run(
		NumpyRandomWrapper(),
		problem, 
		**margs 
	)
    
	dprint(res)

	result_file = open(folder+"/result.pkl", 'wb')
	pickle.dump(problem.results_storage, result_file)
	result_file.close()
