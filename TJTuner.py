#!/usr/bin/env python

#argparse stuff
import argparse
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer.")

#Simulation parameters
parser.add_argument("-g","--generations", type=int, help="number of generation for the genetic algorithm", default=1)
parser.add_argument("-l","--launch", type=str, help="Sumo executable to use. E.G. \"sumo\" or \"sumo-gui\". Default is \"sumo\"", default="sumo")
parser.add_argument("-p","--port", type=int, help="TraCI connection port to Sumo. Default is 27910", default=27910)
parser.add_argument("-s","--scenario", type=str, help="Scenario prefix - uses standard Scenario file extension", default="trento")
parser.add_argument("-d","--debug", type=int, help="Set to 1 to see debug output. Default is 1", default=0)
parser.add_argument("-a","--autostart", type=int, help="Set to 1 to start the simulation automatically. Default is 1", default=0)
parser.add_argument("-e","--end", type=int, help="Simulation duration in step number. Default is 3600.", default=3600)
parser.add_argument("-sd","--step-delay", type=float, help="Delay of each step, useful for GUI demostrations. Default is 0", default=0)
parser.add_argument("-ss","--step-size", type=float, help="Simulation step size. Default is 0.1", default=0.01)
parser.add_argument("-ha","--hang", type=int, help="Set to 1 to hang the program before the simulation, in order to manually connect to problematic scenarios via TraCI", default=0)
parser.add_argument("-so","--sumo-output", type=int, help="Enable simulator stdout/stderr. WARNING: simulation are _considerably_ verbose.", default = 0)
parser.add_argument("-no","--netconvert-output", type=int, help="Enable netconvert stdout/stderr.", default = 0)
parser.add_argument("-j","--jobs", type=int, help="Simulation parallelization. Allow for individuals to be simulated simultaneously. Default is 1", default = 1)
parser.add_argument("-rr","--random-routes", type=int, help="Randomize routes for each simulation. Default is 1 (no randomization, one simulation per individual), values higher than 1 implies multiple repetitions.", default = 1)
parser.add_argument("-rf","--route-frequency", type=int, help="Repetition rate, needed to generate random routes with the Sumo integrated randomTrips.py script. Value in seconds, default 2", default = 1)
parser.add_argument("-rx","--route-file", type=str, help="Force non randomized routes, use a specific route file", default=None)#trento_2")
#TODO add seeds and randomization for bot sumo simulation and netconvert route generation, also manage the seed loading in TJAnalyzer to repeat the exact individual

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
import numpy as np

#Simulation generation and execution library
import TJSumoTools as TJS

#custom xml writer function
write_xml = TJS.write_xml

#custom print function which deletes [ * ] with debug mode disabled
dprint = TJS.dprint
TJS.debug = args.debug == 1	#enable debug print
TJS.hang = args.hang == 1	#hang the simulation for external traci connection

#SUMO/TraCI parameters
sumoAutoStart=args.autostart
sumoScenario = args.scenario
sumoLaunch = args.launch
sumoPort = args.port
sumoEnd = args.end
sumoDelay = args.step_delay
sumoJobs = args.jobs
sumoStepSize = args.step_size
sumoRandomRoutes = args.random_routes
sumoRouteFile = args.route_file
sumoRepetitionRate = args.route_frequency

netconvert_output = args.netconvert_output
sumo_output = args.sumo_output

#other parameters
ind = 0
# junctionNumber = 158 #Bologna scenario
# junctionNumber = 998 #Trento scenario
junctionNumber = 3776 #Milan scenario

folder = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H-%M-%S')
os.mkdir(folder)

with open(folder+"/launch", "w") as launch_save:
	launch_string = " "
	for arg in sys.argv:
		launch_string += str(arg)+" "
	launch_save.write("Launched with \""+launch_string+"\"")

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
			trafficLights_todo = []
			scenarios_todo = []
			routes_todo = []
			simulations_todo = []
			candidates_todo = []
			for candidate in candidates:
				dprint("[ evaluating - ind:"+str(ind)+" ]")
				if not TJBenchmark.results_storage.has_key(pickle.dumps(candidate)):
					dprint("[ need simulation ]")
					candidates_todo.append(candidate)
					candidate['ind'] = ind
					trafficLights_todo.append({
						"scenario": candidate['scenario'],
						"sumoScenario_orig": sumoScenario,
						"sumoScenario_dest": folder + "/ind" + str(ind) + "_" + sumoScenario
					})

					scenarios_todo.append({
						"sumoScenario": sumoScenario,
						"netconvert_output": netconvert_output==1,
						"kwargs":{
							"output": folder + "/ind" + str(ind) + "_" + sumoScenario,
							"node": folder + "/ind" + str(ind) + "_" + sumoScenario,
							"tllogic":  folder + "/ind" + str(ind) + "_" + sumoScenario
						}
					})
					for rep in range(sumoRandomRoutes):
						dprint("[ \tevaluating - rep:"+str(rep)+" ]")
						candidate['rep'] = rep

						routes_todo.append({
							"sumoScenario": folder + "/ind" + str(ind) + "_" + sumoScenario,
							"prefix": "route",
							"sumoEnd": sumoEnd,
							"repetitionRate": sumoRepetitionRate, 
							"output": folder + "/ind" + str(ind) + "_rep" + str(rep) + "_" + sumoScenario,
						})

						current_route = ""
						if sumoRouteFile == None:
							current_route = folder + "/ind" + str(ind) + "_rep" + str(rep) + "_" + sumoScenario
						else:
							current_route = sumoRouteFile

						simulations_todo.append({
							"launch":sumoLaunch,
							"sumoScenario": folder + "/ind" + str(ind) + "_" + sumoScenario,	
							"sumoRoutes": current_route,
							"sumoStepSize": sumoStepSize,
							"sumoPort": sumoPort,
							"sumoAutoStart": sumoAutoStart,
							"sumoEnd": sumoEnd,
							"sumoDelay": sumoDelay,
							"dataCollection": True,
							"sumoOutput": sumo_output==1
						})

					ind += 1

				else:
					dprint("[ already simulated ]")

				'''
				Old call:
				TJS.generate_traffic_light(candidate['scenario'],sumoScenario,folder+"/ind" + str(ind) + "_" + sumoScenario)
				Implementation is not really multithreading atm
				'''
			TJS.generate_traffic_lights(trafficLights_todo,sumoJobs)

			'''
			Old Call:
			TJS.generate_scenario(
				sumoScenario,
				netconvert_output==1,
				output = folder + "/ind"  + str(ind) + "_" + sumoScenario,
				node = folder + "/ind" + str(ind) + "_" + sumoScenario,
				tllogic = folder + "/ind"  + str(ind) + "_" + sumoScenario
			)

			'''

			TJS.generate_scenarios(scenarios_todo,sumoJobs)

			TJS.generate_routes(routes_todo,sumoJobs) #TODO

			raw_results = TJS.execute_scenarios(simulations_todo,sumoJobs,sumoPort)
			results = []

			for res_set in range(len(raw_results)/sumoRandomRoutes):
				avg_res = {}
				for k in ["accidents","arrived","teleported","avg_speed"]:
					avg_res[k] = np.mean([resrep[k] for resrep in raw_results[sumoRandomRoutes*res_set:sumoRandomRoutes*(res_set+1)]])
				results.append(avg_res)

			for c_i in range(len(results)):
				TJBenchmark.results_storage[pickle.dumps(candidates_todo[c_i])] = {}
				for key,value in results[c_i].items():
					TJBenchmark.results_storage[
						pickle.dumps(candidates_todo[c_i])
					][str(key)] = value
					dprint("[ results: %s %f ]" % (key,value))


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
		global ind
		new_ind = {
			'ind':-1,
			'sigmaMutator':1,
			'scenario':[ 
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

	problem = TJBenchmark(objectives=["+avg_speed","+arrived","-teleported","-accidents"])
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
