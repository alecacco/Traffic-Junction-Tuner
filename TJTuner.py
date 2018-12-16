#!/usr/bin/env python

#argparse stuff
import argparse
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer.")

#Simulation parameters
parser.add_argument("-g","--generations", type=int, help="number of generation for the genetic algorithm", default=1)
parser.add_argument("-l","--launch", type=str, help="Sumo executable to use. E.G. \"sumo\" or \"sumo-gui\". Default is \"sumo\"", default="sumo")
parser.add_argument("-p","--port", type=int, help="TraCI connection port to Sumo. Default is 27910", default=27910)
parser.add_argument("-s","--scenario", type=str, help="Scenario prefix - uses standard Scenario file extension", default="semaforoS")
parser.add_argument("-d","--debug", type=int, help="Set to 1 to see debug output. Default is 1", default=0)
parser.add_argument("-a","--autostart", type=int, help="Set to 1 to start the simulation automatically. Default is 1", default=0)
parser.add_argument("-e","--end", type=int, help="Simulation duration in step number. Default is 3600.", default=3600)
parser.add_argument("-sd","--step-delay", type=float, help="Delay of each step, useful for GUI demostrations. Default is 0", default=0)
parser.add_argument("-ha","--hang", type=int, help="Set to 1 to hang the program before the simulation, in order to manually connect to problematic scenarios via TraCI", default=0)
parser.add_argument("-so","--sumo-output", type=int, help="Enable simulator stdout/stderr. WARNING: simulation are _considerably_ verbose.", default = 0)
parser.add_argument("-no","--netconvert-output", type=int, help="Enable netconvert stdout/stderr.", default = 0)

#Genetic algorithm paramenters
parser.add_argument("-mr","--mutation-rate", type=float, help="Rate of mutation. Default is 0.1", default=0.1)
parser.add_argument("-of","--offspring", type=int, help="Maximun number of offspring. Default is 2", default=2)
parser.add_argument("-cr","--crossover-rate", type=float, help="Rate of crossover. Default is 0.8", default=0.8)
parser.add_argument("-ps","--pop-size", type=int, help="Population size, 5 as default", default=5)

#Boundaries parameters
parser.add_argument("-y_min","--yellow_min", type=int, help="Min time for yellow. Default is 1", default = 1)
parser.add_argument("-y_max","--yellow_max", type=int, help="Max time for yellow. Default is 10", default = 10)
parser.add_argument("-gr_min","--green_min", type=int, help="Min time for green and red. Default is 1", default = 1)
parser.add_argument("-gr_max","--green_max", type=int, help="Max time for green and red. Default is 40", default = 40)

args = parser.parse_args()

#imports
import time
import datetime
import os
import sys
import math
import pickle
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

#Bio-imports
from inspyred import benchmarks
from inspyred_utils import NumpyRandomWrapper
from multi_objective import run
from inspyred.ec.emo import Pareto
from inspyred.ec.variators import mutator
from inspyred.ec.variators import crossover

#Simulation generation and execution library
import TJSumoTools as TJS

#custom xml writer function
write_xml = TJS.write_xml

#custom print function which deletes [ * ] with debug mode disabled
dprint = TJS.dprint
TJS.debug = args.debug == 1	#enable debug print
TJS.hang = args.hang == 1	#hang the simulation for external traci connection

#SUMO/TraCI parameters
sumoAutoStart=""
if args.autostart==1:
	sumoAutoStart=" --start"
sumoScenario = args.scenario
sumoLaunch = str(args.launch+" -c "+ args.scenario +".sumo.cfg"+sumoAutoStart+" -Q").split(" ")
sumoPort = args.port
sumoEnd = args.end
sumoDelay = args.step_delay

netconvert_output = args.netconvert_output
sumo_output = args.sumo_output

#other parameters
ind = 0
junctionNumber = 998

#simulations result
results = []
folder = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H-%M-%S')
os.mkdir(folder)

with open(folder+"/launch", "w") as lauch_save:
	launch_string = str(sys.argv)
	lauch_save.write("Launched with "+launch_string)

def clean_scenario():
	nod = ET.parse(sumoScenario + ".nod.xml").getroot()
	for e in list(nod)[1:]:
		e.set("type", "priority")
	write_xml(nod, "clean_" + sumoScenario + '.nod.xml')

	tll = ET.parse(sumoScenario + ".tll.xml").getroot()
	tll.clear()
	write_xml(tll, "clean_" + sumoScenario + '.tll.xml')


class TJBenchmark(benchmarks.Benchmark):

	results_storage = {}
	
	def evaluatorator(self,objective):
		sign = None
		if objective[0]=='-':
			sign = -1
		else:
			sign = +1

		objective= objective[1:]

		def evaluate(self,candidates,args):
			global ind
			#ind = 0
			#generate and execute_scenario
			for candidate in candidates:
				dprint("[ evaluating - ind:"+str(ind)+" ]")
				if not TJBenchmark.results_storage.has_key(pickle.dumps(candidate)):
					dprint("[ need simulation ]")
					candidate['ind'] = ind

					TJS.generate_traffic_light(candidate['scenario'],sumoScenario,folder+"/ind" + str(ind) + "_" + sumoScenario)

					TJS.generate_scenario(
						sumoScenario,
						netconvert_output==1,
						node = folder + "/ind" + str(ind) + "_" + sumoScenario,
						tllogic = folder + "/ind"  + str(ind) + "_" + sumoScenario
					)
					sim_result = TJS.execute_scenario(
						sumoLaunch,
						sumoPort,
						sumoEnd,
						sumoDelay,
						True,
						sumo_output==1
					)
					TJBenchmark.results_storage[pickle.dumps(candidate)] = {}
					for key,value in sim_result.items():
						TJBenchmark.results_storage[
							pickle.dumps(candidate)
						][str(key)] = value
						dprint("[ results: %s %d ]" % (key,value))
					ind += 1
					'''
					TJBenchmark.results_storage[
						pickle.dumps(candidate)
					][objective] *= sign
					'''
				else:
					dprint("[ already simulated ]")

			return [
				TJBenchmark.results_storage[
					pickle.dumps(candidate)
				][objective]*sign
				for candidate in candidates
			]
		return evaluate

	def __init__(self, objectives=["accidents","arrived"]):
		benchmarks.Benchmark.__init__(self, junctionNumber, len(objectives))
		self.bounder = TJTBounder()
		self.maximize = True
		self.evaluators = [self.evaluatorator(objective) for objective in objectives]

		self.variator = [mutate,cross]
		
		clean_scenario()

	def generator(self, random, args):
		dprint("[ generating initial population ]")
		#return [random.uniform(-5.0, 5.0) for _ in range(self.dimensions)]
		global ind
		new_ind = {
			'ind':-1,
			'sigmaMutator':1,
			'scenario':[ #TODO definitely not ideal, should apply some constraints!!
				{
					'type':random.choice(['p','t']),
					'ytime':random.uniform(high=args["yellow_max"],low=args["yellow_min"]),
					'grtime':random.uniform(high=args["green_max"],low=args["green_min"])
					
				}
				for _ in range(junctionNumber)
			]
		}
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
						ytime = round(junction['ytime'] + 10*random.gauss(0,1))
					if(ytime < 0):
						ytime = -1 * ytime
					junction['ytime'] = ytime
					grtime = 0
					while (grtime == 0):
						grtime = round(junction['grtime'] + 10*random.gauss(0,1))
					if(grtime < 0):
						grtime = -1 * grtime
					junction['grtime'] = grtime
					
			elif(junction['type'] == 'p'):
			
				if(sigmaMutator * random.gauss(0,1) > 1):
					junction['type'] = 't'
					ytime = 0
					while (ytime == 0):
						ytime = round(junction['ytime'] + 10*random.gauss(0,1))
					if(ytime < 0):
						ytime = -1 * ytime
					junction['ytime'] = ytime
					grtime = 0
					while (grtime == 0):
						grtime = round(junction['grtime'] + 10*random.gauss(0,1))
					if(grtime < 0):
						grtime = -1 * grtime
					junction['grtime'] = grtime
					
		candidate['scenario']=junctions
		
		
		bounder = args['_ec'].bounder
		candidate = bounder(candidate, args)
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
	newSigmaMutator = (mom["sigmaMutator"]+mom["sigmaMutator"])/2
	#newGen = mom["gen"] + 1
	offspring = {
			'ind':-1,
			'sigmaMutator':newSigmaMutator,
			'scenario':[ #TODO definitely not ideal, should apply some constraints!!
				{
					'type':random.choice(['p','t']),
					'ytime':random.uniform(high=args["yellow_max"],low=args["yellow_min"]),
					'grtime':random.uniform(high=args["green_max"],low=args["green_min"])
					
				}
				for _ in range(junctionNumber)
			]
		}
		
	if(crossoverRate >= random.uniform(0,1)):
		dprint("[ \t->crossover happened ]")
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
		dprint("[ bounder controlling ]")
		for junction in candidate["scenario"]:
			if( junction["ytime"] < args["yellow_min"] ):
				junction["ytime"] = args["yellow_min"]
			if( junction["ytime"] > args["yellow_max"] ):
				junction["ytime"] = args["yellow_max"]
			if( junction["grtime"] < args["green_min"] ):
				junction["grtime"] = args["green_min"]
			if( junction["grtime"] > args["green_max"] ):
				junction["grtime"] = args["green_max"]
		return candidate
		
		
if __name__ ==  "__main__":

	problem = TJBenchmark(objectives=["+agv_speed","+arrived","-teleported","-accidents"])
	margs = {}
	margs["mutationRate"] = args.mutation_rate
	margs["crossoverRate"] = args.crossover_rate
	margs["offspring"] = args.offspring
	margs["variator"] = [cross,mutate]
	margs["max_generations"] = args.generations
	margs["pop_size"] = args.pop_size
	margs["num_vars"] = 2	
	margs["tournament_size"] = 2	
	margs["yellow_min"] = args.yellow_min		
	margs["yellow_max"] = args.yellow_max		
	margs["green_min"] = args.green_min		
	margs["green_max"] = args.green_max
	margs["bounder"] = TJTBounder()
	margs["folder"] = folder

	res = run(
		NumpyRandomWrapper(),
		problem,
		display=False, 
		**margs 
	)
    
	dprint(res)
	
	result_file = open(folder+"/results_storage.pkl", 'wb')
	pickle.dump(problem.results_storage, result_file)
	result_file.close()
