#!/usr/bin/env python

#argparse stuff
import argparse
import random
import re
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer.")

#Simulation parameters
parser.add_argument("-g","--generations", type=int, 
	help="number of generation for the genetic algorithm", 
	default=1)
parser.add_argument("-l","--launch", type=str, 
	help="Sumo executable to use. E.G. \"sumo\" or \"sumo-gui\". Default is \
	\"sumo\"", default="sumo")
parser.add_argument("-p","--port", type=int, 
	help="TraCI connection port to Sumo. Default is 27910", 
	default=27910)
parser.add_argument("-s","--scenario", type=str, 
	help="Scenario prefix - uses standard Scenario file extension", 
	default="trento")
parser.add_argument("-d","--debug", type=int, 
	help="Set to 1 to see debug output. Default is 1", 
	default=0)
parser.add_argument("-a","--autostart", type=int, 
	help="Set to 1 to start the simulation automatically. Default is 1", 
	default=0)
parser.add_argument("-e","--end", type=int, 
	help="Simulation duration in step number. Default is 3600.", 
	default=3600)
parser.add_argument("-sd","--step-delay", type=float, 
	help="Delay of each step, useful for GUI demostrations. Default is 0", 
	default=0)
parser.add_argument("-ss","--step-size", type=float, 
	help="Simulation step size. Default is 0.1", 
	default=0.01)
parser.add_argument("-ha","--hang", type=int, 
	help="Set to 1 to hang the program before the simulation, in order to \
	manually connect to problematic scenarios via TraCI", 
	default=0)
parser.add_argument("-so","--sumo-output", type=int, 
	help="Enable simulator stdout/stderr. WARNING: simulation are \
	_considerably_ verbose.", 
	default = 0)
parser.add_argument("-no","--netconvert-output", type=int, 	help="Enable \
	netconvert stdout/stderr.", 
	default = 0)
parser.add_argument("-j","--jobs", type=int, 
	help="Simulation parallelization. Allow for individuals to be simulated \
	simultaneously. Default is 1", 
	default = 1)
parser.add_argument("-rr","--random-routes", type=int, 
	help="Randomize routes for each simulation. Default is 1 (one route \
	per individual).", 
	default = 1)
parser.add_argument("-srr","--single-route-repetitions", type=str, 
	help="Random repetition of the simulation for each generated route \
	(of each individual). If multiple repetitions are requested, multiple \
	simulation on each route will be performed, each with a different seed. \
	Use \"R\" to use sumo --random option instead of TJT seeds. \
	Default is 1.", 
	default = "1")
parser.add_argument("-tr","--traffic-rates", type=str, 	help="Traffic rates, \
	needed to generate random routes with the Sumo integrated randomTrips.py \
	script. Values in seconds, separated by a space, default \"1.5 2 2.5 3\"", 
	default = 2)
parser.add_argument("-rx","--route-file", type=str, help="Force non randomized \
	routes, use a specific route file", 
	default=None)
#TODO add seeds and randomization for bot sumo simulation and netconvert route generation, also manage the seed loading in TJAnalyzer to repeat the exact individual

#Genetic algorithm paramenters
parser.add_argument("-mr","--mutation-rate", type=float, 
	help="Rate of mutation. Default is 0.1", 
	default=0.1)
parser.add_argument("-of","--offspring", type=int, 
	help="Maximun number of offspring. Default is 2", 
	default=2)
parser.add_argument("-cr","--crossover-rate", type=float, 
	help="Rate of crossover. Default is 0.8", 
	default=0.8)
parser.add_argument("-ps","--pop-size", type=int, 
	help="Population size, 5 as default", 
	default=5)
parser.add_argument("-cobj","--combined-objectives", type=str, 
	help="TODO")
"""Objectives of the evolutionary algorithm.\
Fitness for these objectives will be calculated from simulation \
results, taking mean, variance, worst or best. Use respectively \"M\"\
, \"V\", \"W\", \"B\" in some signed 2-sized combination followed by an \
objective definition. Put \"+\", \"-\" or \"*\" before to specify if the \
objective should be minimized, maximized or collected but not used for \
fitness. E.g. \"+WBarrived\" to minimize the arrived vehicles of the worst \
traffic frequency considering the best repetition, or \"-VMarrived\" to \
maximize the variance or arrived vehicles among traffic frequencies, \
considering the best achieved repetition. Default is \"-MMarrived \
+MMteleport +MMaccidents\". Avalable objectives identifiers are \
\"arrived\", \"teleport\", \"accidents\", \"avg_speed\", \"fuel\"",
default="-MMarrived	+MMteleport +MMaccidents")
"""
parser.add_argument("-nf","--normalize-fitness", type=int, 
	help="Automatically normalize fitness values if set to  1. Default is 1.", 
	default=1)


#Boundaries parameters
parser.add_argument("-y_min","--yellow_min", type=int, 
	help="Min time for yellow. Default is 1", 
	default = 1)
parser.add_argument("-y_max","--yellow_max", type=int, 
	help="Max time for yellow. Default is 10", 
	default = 10)
parser.add_argument("-gr_min","--green_min", type=int, 
	help="Min time for green and red. Default is 1", 
	default = 1)
parser.add_argument("-gr_max","--green_max", type=int, 
	help="Max time for green and red. Default is 40", 
	default = 40)

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

#custom print function which doesn't log strings like [ * ] with debug mode disabled
def dprint(s):
	s=str(s)
	if args.debug or not (s.split()[0]=="[" and s.split()[-1]=="]"):
		print("TJT>\t"+s)

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
sumoRandom = False
sumoRouteRepetitions = 1
if args.single_route_repetitions.isdigit():
	sumoRouteRepetitions = int(args.single_route_repetitions)
elif args.single_route_repetitions == "R":
	sumoRouteRepetitions = 1
	sumoRandom = True
else:
	dprint("WARNING: invalid single-route-repetitions parameter, needs to be a \
		positive integer or \"R\". Continuing with \"1\"")

sumoTrafficRates = [float(rf) for rf in args.traffic_rates.split(" ")]

def isfloatvalue(v):
	return re.match("^[+-]?\d(\.\d+)?",v)!=None

def iscomplexobjective(obj):
	return (
		(obj[2:] in TJS.implemented_objectives) and \
		(
			obj[0] in ["H","L","M","V"] and \
			obj[1] in ["H","L","M","V"]
		)
	)

comb_operators = {
	"+":lambda a,b:a+b,
	"-":lambda a,b:a-b,
	"*":lambda a,b:a*b,
	"/":lambda a,b:a/b,
	"M":lambda a,b:max(a,b),
	"m":lambda a,b:min(a,b)
}
eaObjectives_comb = sorted(args.combined_objectives.split(";"))

eaObjectives_complex = set() #args.complex_objectives.split(" ")
for comb_obj in eaObjectives_comb:
	eaObjectives_complex = eaObjectives_complex.union([
		obj for obj in comb_obj[2:-1].split(" ") if obj not in comb_operators.keys() and not isfloatvalue(obj)
	])
eaObjectives_complex = sorted(list(eaObjectives_complex))

eaObjectives = [co for co in eaObjectives_comb if (co[0]=="+" or co[0]=="-")]
normalize = args.normalize_fitness==1

netconvert_output = args.netconvert_output
sumo_output = args.sumo_output

#other parameters
ind = 0
junctionNumber = None

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

def get_max_speed_limit(scenario):
	edgefile = ET.parse(scenario+".edg.xml").getroot()
	speeds = [
		float(edge.get("speed"))
		for edge in edgefile 
		if (
			edge.tag=="edge" and 						# exclude roundabouts and other types of edges
			edge.get("type").split(".")[0]=="highway"	# exclude railways, which are edges but speed is much higher
		)
	]
	return max(speeds)

def normalize_fitness(fitness,ind,traffic_rate,routes,repetitions):
	global sumoScenario,sumoTrafficRates

	speednorm_coeff = 2.0
	teleport_coeff = 10.0

	normalize = lambda value,minv,maxv : float(value-minv)/float(maxv-minv)
	getroutes = lambda ind,tr,rou:len(list(ET.parse(
		folder+"/"+\
		"ind"+str(ind)+\
		"_traffic"+str(tr)+\
		"_rep"+str(rou)+"_"+\
		sumoScenario + ".rou.xml"
		).getroot()))

	i=0
	for rou in range(routes):
		for rep in range(repetitions):
			for k in fitness.keys():
				previous = fitness[k][i]*1
				maxv = -42
				if k=="accidents" or k=="arrived":
					maxv = getroutes(ind,sumoTrafficRates[traffic_rate],rou)
					fitness[k][i] = normalize(fitness[k][i],0,maxv)
					#print(k+" "+str(fitness[k][i]))
				elif k=="avg_speed":
					maxv = speednorm_coeff*get_max_speed_limit(sumoScenario)
					fitness[k][i] = normalize(fitness[k][i],0,maxv)
				elif k=="teleported":
					maxv = teleport_coeff*getroutes(ind,sumoTrafficRates[traffic_rate],rou)
					fitness[k][i] = normalize(fitness[k][i],0,maxv)
				else:
					dprint("Can't normalize %s"%(k))
				#print("Normalization for %s (between 0 and %f): %f -> %f"%(k,maxv,previous,fitness[k][i]))
			i+=1

	#print("%s  \t%d\t%d\t%d\t%d"%(str(fitness),ind,traffic_rate,routes,repetitions))
	return fitness
		

"""
Objectives checker, return True with valid objectives
"""
def validate_objectives(objectives):
	#print(objectives)
	valid = True
	for comb_obj in objectives:
		if (
			comb_obj[0] in ["+","-","*"] and \
			comb_obj[1] == "[" and comb_obj[-1] == "]"
		):
			count = 0
			for obj in comb_obj[2:-1].split(" "):
				if obj in comb_operators.keys():	# RPN operator
					if count < 2:						# a RPN operator must have 2 parameters to work on
						valid = False					# invalid RPN formula
					else:
						count-=1
				elif isfloatvalue(obj) or \
					iscomplexobjective(obj):			# RPN value, either int/float or objective token. 
					count+=1
				else:
					valid = False						# invalid token
				
			if count != 1:
				valid = False							# invalid RPN formula - not enough operands
		else:
			valid = False
	return valid

def parseRPN(formula,values):
	stack = []
	tokens = formula[2:-1].split(" ")
	tokens.reverse()

	while len(tokens)>0:
		print(str(tokens)+" <---> "+str(stack))
		current = tokens.pop()
		if current in comb_operators.keys():
			op1 = stack.pop()
			op2 = stack.pop()
			stack.append(comb_operators[current](op1,op2))
		elif isfloatvalue(current):
			stack.append(float(current))
		elif iscomplexobjective(current):
			stack.append(values[current])
		else:
			dprint("ERROR parsing RPN fitnesses.")
			return 0

	if len(stack) != 1:
		dprint("ERROR: RPN fitnesses stack does not contain single elements")
		return 0
	else:
		return stack.pop()


class TJBenchmark(benchmarks.Benchmark):

	results_storage = {}
	
	def evaluatorator(self,objective):
		sign = None
		if objective[0]=='-':
			sign = -1
		else:
			sign = +1

		def evaluate(self,candidates,args):
			global ind
			#ind = 0
			#generate and execute_scenario
			trafficLights_todo = []
			scenarios_todo = []
			routes_todo = []
			simulations_todo = []
			candidates_todo = []

			data_to_collect = list(set([co[2:] for co in eaObjectives_complex]))
			dprint("[ Requesting simulation with data collection %s ]"%(str(data_to_collect)))

			for candidate in candidates:
				dprint("[ evaluating - ind:"+str(ind)+" ]")
				if not TJBenchmark.results_storage.has_key(pickle.dumps(candidate)):
					dprint("[ need simulation ]")
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
					for sumoTrafficRate in sumoTrafficRates:
						for rep in range(sumoRandomRoutes):
							dprint("[ \tevaluating - rep:"+str(rep)+" ]")
							candidate['rep'] = rep

							routes_todo.append({
								"sumoScenario": folder + "/ind" + str(ind) + "_" + sumoScenario,
								"prefix": "route",
								"sumoEnd": sumoEnd,
								"repetitionRate": sumoTrafficRate, 
								"output": folder + "/ind" + str(ind) + "_traffic" + str(sumoTrafficRate) + "_rep" + str(rep) + "_" + sumoScenario,
							})

							current_route = ""
							if sumoRouteFile == None:
								current_route = folder + "/ind" + str(ind) + "_traffic" + str(sumoTrafficRate) + "_rep" + str(rep) + "_" + sumoScenario
							else:
								current_route = sumoRouteFile

							for rep in range(sumoRouteRepetitions):
								current_seed = -1
								if not sumoRandom:
									current_seed = str(random.randint(0,99999))

								simulations_todo.append({
									"launch":sumoLaunch,
									"sumoScenario": folder + "/ind" + str(ind) + "_" + sumoScenario,	
									"sumoRoutes": current_route,
									"sumoStepSize": sumoStepSize,
									"sumoPort": sumoPort,
									"sumoAutoStart": sumoAutoStart,
									"sumoEnd": sumoEnd,
									"sumoDelay": sumoDelay,
									"objectives": data_to_collect,
									"sumoOutput": sumo_output==1,
									"sumoSeed": current_seed
								})
					candidates_todo.append(candidate)
					ind += 1

				else:
					dprint("[ already simulated ]")

			if len(scenarios_todo)>0:
				# generate traffic light corresponding to each individual genome
				TJS.generate_traffic_lights(trafficLights_todo,sumoJobs)

				# generate a sumo net.xml scenario for each individual
				TJS.generate_scenarios(scenarios_todo,sumoJobs)

				# generate random routes for each individual
				TJS.generate_routes(routes_todo,sumoJobs)

				# execute simulation of all the individuals
				raw_results = TJS.execute_scenarios(simulations_todo, sumoJobs, sumoPort)

				individuals = len(raw_results)/(len(sumoTrafficRates)*sumoRandomRoutes*sumoRouteRepetitions)

				dprint("[ Processing fitness data of %d individuals ]"%(individuals))

				for curr_ind in range(individuals):
					ind_results = {}
					orig_results = {}
					for tr in range(len(sumoTrafficRates)):
						res_subset = raw_results[
							(len(sumoTrafficRates)*sumoRandomRoutes*sumoRouteRepetitions) 	* (curr_ind) +
							(sumoRandomRoutes*sumoRouteRepetitions) 						* (tr)  :
							(len(sumoTrafficRates)*sumoRandomRoutes*sumoRouteRepetitions) 	* (curr_ind) +
							(sumoRandomRoutes*sumoRouteRepetitions) 						* (tr+1)
						]
						dprint("[ GROUPING: %d:%d]" %(
							(len(sumoTrafficRates)*sumoRandomRoutes*sumoRouteRepetitions) 	* (curr_ind) +
							(sumoRandomRoutes*sumoRouteRepetitions) 						* (tr) ,
							(len(sumoTrafficRates)*sumoRandomRoutes*sumoRouteRepetitions) 	* (curr_ind) +
							(sumoRandomRoutes*sumoRouteRepetitions) 						* (tr+1)
						))
						
						dprint("[ Grouping fitness of %d executions ]"%(len(res_subset)))

						res = {}
						for k in data_to_collect:	
							res[k] = [resrep[k] for resrep in res_subset]	#list of associated runs
						if normalize:
							ind_results[sumoTrafficRates[tr]] = normalize_fitness(res,curr_ind,tr,sumoRandomRoutes,sumoRouteRepetitions)
							orig_results[sumoTrafficRates[tr]] = res
						else:
							ind_results[sumoTrafficRates[tr]] = res

					# compute complex objectives combinations
					cobj_res = {}
					for cobj in eaObjectives_complex:

						best = np.max 
						worst = np.min

						method_traffic_frequency = \
							best if cobj[0]=="H" else\
							worst if cobj[0]=="L" else\
							np.var if cobj[0]=="V" else\
							np.mean #if cobj[1]=="M"						
						method_repetitions = \
							best if cobj[1]=="H" else\
							worst if cobj[1]=="L" else\
							np.var if cobj[1]=="V" else\
							np.mean #if cobj[1]=="M"

						cobj_res[cobj] = (method_traffic_frequency([
								method_repetitions(ind_results[tr][cobj[2:]]) 
								for tr in sumoTrafficRates
							])
						)
					
					# compute final combined objectives
					TJBenchmark.results_storage[
						pickle.dumps(
							candidates_todo[curr_ind]
						)
					] = {}
					
					for comb_obj in eaObjectives_comb:
						TJBenchmark.results_storage[
							pickle.dumps(candidates_todo[curr_ind])
						][comb_obj] = parseRPN(comb_obj, cobj_res)
						
					#TODO add adv obj here	

					TJBenchmark.results_storage[pickle.dumps(candidates_todo[curr_ind])]["ind"] = candidates_todo[curr_ind]["ind"]
					TJBenchmark.results_storage[pickle.dumps(candidates_todo[curr_ind])]["raw"] = ind_results
					if normalize:
						TJBenchmark.results_storage[pickle.dumps(candidates_todo[curr_ind])]["raw_orig"] = orig_results	#TODO check values


				#save updated result file 
				result_file = open(folder+"/results_storage.pkl", 'wb')
				pickle.dump(problem.results_storage, result_file)
				result_file.close()
			
			return [
				TJBenchmark.results_storage[
					pickle.dumps(candidate)
				][objective] * sign 
				for candidate in candidates
			]
		return evaluate

	def __init__(self, objectives=["+[MMaccidents]"]):
		global junctionNumber

		junctionNumber = len(list(ET.parse(sumoScenario + ".nod.xml").getroot()))-1
		dprint("[ optimizing %d junctions ]"%(junctionNumber))

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

	if not validate_objectives(eaObjectives_comb):
		dprint("ERROR: invalid objectives. Cannot parse RPN formula.")
		sys.exit(-1)

	problem = TJBenchmark(objectives=eaObjectives)
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

	result_file = open(folder+"/results_storage.pkl", 'wb')
	pickle.dump(problem.results_storage, result_file)
	result_file.close()  
