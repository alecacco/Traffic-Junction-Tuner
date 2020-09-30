#!/usr/bin/env python

import argparse
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer - Result Analyzer.")
parser.add_argument("-d","--debug", type=int, help="Set to 1 to see debug output. Default is 1", default=1)
parser.add_argument("-f","--folder", type=str, help="Result folder to analyze", required=True)
parser.add_argument("-r","--run", type=int, help="Re-run the simulation of a specific individual (default is 0)", required=False, default=0)
parser.add_argument("-pg","--pick-generation", type=str, help="re-simulate a population, select which generation (default is last one)", required=False, default=-1)
parser.add_argument("-pi","--pick-individual", type=str, help="re-simulate a population, select which individual (default is individual 0)", required=False, default=0)
parser.add_argument("-pr","--pick-repetition", type=str, help="re-simulate a population, select which repetition of the individual (default is repetition 0)", required=False, default=0)
parser.add_argument("-pl","--plot", type=int, help="Plot objective throughout generations", required=False, default=1)
parser.add_argument("-pt","--plot-type", type=str, help="Select the types of plots to output, can be more than one, separated by a space. Possible choices are \"matrix\",\"box\", \"linemax\", \"linemin\", \"lineavg\".", required=False, default="box")
parser.add_argument("-t","--table", type=str, help="Print a magnificent table of a specific generation. Default is pick generation", default="-1")
parser.add_argument("-rs","--reference-scenario", type=str, help="Load a .csv file to compare the data to.", required=False)
parser.add_argument("-mp","--matrix-plot", type=str, help="Select what generations to plot in the matrix plot (if requested). Provide a string with all the requested generations separated by a space.", required=False)
parser.add_argument("-st","--save-table", type=str, help="Select generations table to save in csv format. Provide a string with all the requests separated by a space.", required=False)
parser.add_argument("-o","--objectives", type=str, help="Specify objectives of the optimization. If a results_storage file is found, this is ignored and keys from the file are used instead.")
parser.add_argument("-pp","--plot-pdf", type=str, help="Name of the file in which plots are are saved instead of opening the GUI (will be saved in $folder/results)", required=False, default=None)
parser.add_argument("-pf","--plot-format", type=str, help="Specify the format for the saved plot, space separated list, possible choices:\"pdf\",\"eps\". Default is \"pdf\"", default="pdf")
#TODO [...] Use \"t\", \"pg\" and/or \"mp\" to include generations specified for other parameters. Provide a string with all the requests separated by a space. Default is \"t\".", required=False, default="t")

args = parser.parse_args()
if args.table=="a":
	args.table=args.pick_generation

import os,sys
import re
import pickle
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import TJSumoTools as TJS
import plotting_lib as TJP

debug = (args.debug == 1)
def dprint(s):
	s=str(s)
	if debug or not (s.split()[0]=="[" and s.split()[-1]=="]"):
		print("TJA>\t"+s)

files = []
populations = []
reference_scenarios_data = None
res_storage = None

#debug output
TJS.debug = True
sumoDebug = False
netconvertDebug = False

#plotting paramenters
#titles = ["Average speed","Arrived","Teleported","Accidents"]
#objectives = ["+avg_speed","+arrived","-teleported","-accidents"]
titles = []
objectives = []
additional_info = []
signs = []
ranks = {}

#scenario parameters
sumoScenario = "trento"
sumoPort = 27910
sumoEnd = 3600
sumoDelay = 0.1
sumoStepSize = 1

#reordering function for population sorting
def get_no(e):
	return int(e[len("population"):-len(".pkl")])

#generate matrix plot
def generate_plot_matrix():

	requested_gens = args.matrix_plot.split()
	references = "r" in requested_gens
	front_only = "f" in requested_gens

	requested_gens = [int(r) for r in requested_gens if r.isdigit() or (r[0]=="-" and r[1:].isdigit())]

	dprint("[ Requests for matrix plot: " + str(requested_gens) + " ]")

	f = plt.figure(2,figsize=(9,6))
        f.subplots_adjust(wspace=1.0/20,hspace=1.0/15)

	TJP.generate_plot_matrix(
		f,
		[[[ind.fitness[f_i]*signs[f_i] for f_i in range(len(signs))] for ind in populations[p_i]] for p_i in range(len(populations)) if p_i in requested_gens],
		len(objectives),\
		signs,
		titles = titles,
		references = references,
		front_only = front_only,
		series_names = ["Generation "+str(r) for r in requested_gens],
		title = args.folder+" - matrix plot",
		reference_scenarios_data = reference_scenarios_data
	)

	if args.plot_pdf!=None:
		if not os.path.isdir(args.folder+"/results"):
			os.mkdir(args.folder + "/results")
		if "pdf" in args.plot_format.split(" "):
			f.savefig(args.folder + "/results/" + args.plot_pdf + "_matrix.pdf", format="pdf")
		if "eps" in args.plot_format.split(" "):
			f.savefig(args.folder + "/results/" + args.plot_pdf + "_matrix.eps", format="eps")


#generate matrix plot - all values in results storage
def generate_plot_matrix_all():
	requested_gens = args.matrix_plot.split()
	references = "r" in requested_gens
	front_only = "f" in requested_gens

	requested_gens = [int(r) for r in requested_gens if r.isdigit() or (r[0]=="-" and r[1:].isdigit())]

	dprint("[ Requests for matrix plot: " + str(requested_gens) + " ]")

	f = plt.figure(3,figsize=(9,6))

	TJP.generate_plot_matrix(
		f,
		[
			[
				build_fitness([
					ind_st["raw"] 
					for ind_st in res_storage.values() 
					if ind_st["ind"]==ind.candidate["ind"]
				][0])
				for ind in populations[p_i]
			] 
			for p_i in range(len(populations)) if p_i in requested_gens
		],
		len(objectives+additional_info),
		signs + list([0]*len(additional_info)),
		titles = titles+additional_info,
		references = references,
		front_only = front_only,
		series_names = ["Generation "+str(r) for r in requested_gens],
		title = args.folder+" - matrix plot (all parameters)",
		reference_scenarios_data = reference_scenarios_data
	)

	if args.plot_pdf!=None:
		if not os.path.isdir(args.folder+"/results"):
			os.mkdir(args.folder + "/results")
		if "pdf" in args.plot_format.split(" "):
			f.savefig(args.folder + "/results/" + args.plot_pdf + "_matrix_all.pdf", format="pdf")
		if "eps" in args.plot_format.split(" "):
			f.savefig(args.folder + "/results/" + args.plot_pdf + "_matrix_all.eps", format="eps")


#generate parallel coordinates plot
def generate_plot_parcoord():

	requested_gens = args.matrix_plot.split()
	references = "r" in requested_gens
	front_only = "f" in requested_gens

	requested_gens = [int(r) for r in requested_gens if r.isdigit() or (r[0]=="-" and r[1:].isdigit())]

	dprint("[ Requests for parallel coordinates plot: " + str(requested_gens) + " ]")

	f = plt.figure(4,figsize=(9,6))

	reference_scenarios_data_prepared = []
	if references:
		reference_scenarios_data_prepared = [
				[
					[
						fit*signs[f_i] 
						for fit in rs[f_i]
					] 
					for f_i in range(len(rs))
				] 
				for rs in reference_scenarios_data
			]

	TJP.generate_plot_parcoord(
		f,
		[[ind.fitness for ind in populations[p_i]] for p_i in range(len(populations)) if p_i in requested_gens],
		len(objectives),
		signs,
		titles = titles,
		references = references,
		front_only = front_only,
		series_names = ["Generation "+str(r) for r in requested_gens],
		title = args.folder+" - parallel coordinates plot",
		reference_scenarios_data = reference_scenarios_data_prepared
	)

	if args.plot_pdf!=None:
		if not os.path.isdir(args.folder+"/results"):
			os.mkdir(args.folder + "/results")
		if "pdf" in args.plot_format.split(" "):
			f.savefig(args.folder + "/results/" + args.plot_pdf + "_parcoord.pdf", format="pdf")
		if "eps" in args.plot_format.split(" "):
			f.savefig(args.folder + "/results/" + args.plot_pdf + "_parcoord.eps", format="eps")

#Plotting procedure
def plot_all():
	plt.ioff()

	if "linemax" in args.plot_type.split() or "linemin" in args.plot_type.split() or "lineavg" in args.plot_type.split() or "box" in args.plot_type.split() or "vbox" in args.plot_type.split():

		plotnumber = len(populations[0][0].fitness)

		if "vbox" in args.plot_type.split():
			f = plt.figure(1,figsize=(6,5*plotnumber))
		else:
			f = plt.figure(1,figsize=(9,6))
		f.suptitle(args.folder+" - results")

		index = 0
		for plot in range(plotnumber):
			if "vbox" in args.plot_type.split():
				ax = f.add_subplot(plotnumber,1,index+1,
					xlabel="Generation",
					ylabel=objectives[index]
				)
			else:	
				ax = f.add_subplot(int(np.ceil(np.sqrt(plotnumber))),int(np.ceil(np.sqrt(plotnumber))),index+1,
					xlabel="Generation",
					ylabel=objectives[index]
				)

			xticks = list(range(len(populations)))
			plt.xticks(list(range(0,len(populations),len(populations)/5)), rotation='vertical')
			
			#**calculations**
			if "linemax" in args.plot_type.split():
				ax.plot(list(range(len(populations))),[np.max([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="max")
			if "lineavg" in args.plot_type.split():
				ax.plot(list(range(len(populations))),[np.mean([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="mean")
			if "linemin" in args.plot_type.split():
				ax.plot(list(range(len(populations))),[np.min([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="min")


			if "box" in args.plot_type.split() or "vbox" in args.plot_type.split():
				ax.boxplot([[cand.fitness[index]*signs[index] for cand in pop] for pop in populations], positions=xticks)
			
			plt.gca().set_xticklabels([
				tl 
				if (tl%(len(populations)/5)==0) 
				else "" 
				for tl in list(range(0,len(populations)))
			])

			#ax.xticks(locs)

			if "linemax" in args.plot_type.split() or "linemin" in args.plot_type.split() or "lineavg" in args.plot_type.split():
				ax.legend()

			#ax.set_title(titles[index])
			#ax.ylabel(objectives[index])
			#ax.xlabel("Generation")
			#ax.xaxis.set_major_locator(MaxNLocator(integer=True))

			index+=1

		if args.plot_pdf!=None:
			if not os.path.isdir(args.folder+"/results"):
				os.mkdir(args.folder + "/results")
			if "pdf" in args.plot_format.split(" "):
				f.savefig(args.folder + "/results/" + args.plot_pdf + ".pdf", format="pdf")
			if "eps" in args.plot_format.split(" "):
				f.savefig(args.folder + "/results/" + args.plot_pdf + ".eps", format="eps")

	if "matrix" in args.plot_type.split():
		generate_plot_matrix()

	if "parcoord" in args.plot_type.split():
		generate_plot_parcoord()

	if "matrix_all" in args.plot_type.split():
		if "raw" in res_storage.values()[0].keys():
			generate_plot_matrix_all()
		else:
			dprint("ERROR: can't find raw data in the results storage!")

	if args.plot_pdf==None:
		plt.show()

def is_dominated(fitness1,fitness2,invert=False):
	fit1 = fitness1
	fit2 = fitness2
	if invert:
		fitT = fitness1
		fit1 = fit2
		fit2 = fitT

	notworse = True
	betterinsth = False
	for f_i in range(len(fit1)):
		if fit2[f_i] < fit1[f_i]:
			notworse = False
		if fit2[f_i] > fit1[f_i]:
			betterinsth = True

	if (notworse and betterinsth):
		return True
	else:
		return False

def count_dominated(fitness1,fitnesses,invert=False):
	count = 0
	rearranged_fitnesses = fitnesses+[]
	for fitness2 in rearranged_fitnesses:
		if is_dominated(fitness1,fitness2,invert)==True:
			count+=1

	return(str(count)+"/"+str(len(rearranged_fitnesses)))

comb_operators = {
	"+":lambda a,b:b+a,
	"-":lambda a,b:b-a,
	"*":lambda a,b:b*a,
	"/":lambda a,b:b/a,
	"M":lambda a,b:max(a,b),
	"m":lambda a,b:min(a,b)
}
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
def parseRPN(formula,values):
	stack = []
	tokens = formula[2:-1].split(" ")
	tokens.reverse()

	while len(tokens)>0:
		#print(str(tokens)+" <---> "+str(stack))
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

def build_fitness(data):
	operations = {
		"H":np.max,
		"L":np.min,
		"M":np.mean,
		"V":np.var
	}

	reps = len(
		data[
			data.keys()[0]
		])
	traffic_rates = data.keys()

	cobjectives = set()
	for comb_obj in objectives+additional_info:
		cobjectives = cobjectives.union(set([token 
			for token in comb_obj[2:-1].split() 
			if token [2:] in TJS.implemented_objectives 
			and token[0] in ["H","L","M","V"]
			and token[1] in ["H","L","M","V"]
		]))

	data_grouped = {
		cobj:operations[cobj[0]]([
			operations[cobj[1]]([
				data[tr][cobj[2:]]
			])
			for tr in traffic_rates 
		])
		for cobj in cobjectives
	}

	fitness = [parseRPN(comb_obj,data_grouped) for comb_obj in objectives+additional_info]
	return fitness

def load_reference_data(ref_filenames):
	dprint("[ \t\tLoading reference scenario ]")
	res = []
	operations = {
		"H":np.max,
		"L":np.min,
		"M":np.mean,
		"V":np.var
	}
	for ref_filename in ref_filenames:
		with open(ref_filename, 'rb') as ref_file:
			reference_scenario_data = pickle.load(ref_file)
	
		reps = len(
			reference_scenario_data[
				reference_scenario_data.keys()[0]
			])
		traffic_rates = reference_scenario_data.keys()

		cobjectives = set()
		for comb_obj in objectives:
			cobjectives = cobjectives.union(set([token 
				for token in comb_obj[2:-1].split() 
				if token [2:] in TJS.implemented_objectives 
				and token[0] in ["H","L","M","V"]
				and token[1] in ["H","L","M","V"]
			]))

		for cobj in cobjectives:
			reference_scenario_data[cobj] = [
				operations[cobj[0]]([
					reference_scenario_data[tr][i][cobj[2:]] 
					for tr in traffic_rates
				]) 
				for i in range(reps)
			]
		final_reference_scenario_data = {}
		for comb_obj in objectives:
			final_reference_scenario_data[comb_obj] = [parseRPN(comb_obj,{ k:reference_scenario_data[k][i] for k in cobjectives}) for i in range(reps)]

		res.append([final_reference_scenario_data[obj] for obj in objectives])
	
	return res
	
#Table printing procedure
def print_table(table):
	title = ("******** Table of individuals for generation %d ********" % table)
	dprint("-"*len(title))
	dprint(title)
	dprint("-"*len(title))
	rows = []

	ind_i = 0
	for ind in populations[table]:
		dominated = []
		dominating = []
		if reference_scenarios_data != None:
			for rs in range(len(reference_scenarios_data)):
				reference_scenario_data = reference_scenarios_data[rs]
				dominated.append(count_dominated(
					[ind.fitness[i] for i in range(len(objectives))], 
					[[data[i]*signs[i] for i in range(len(objectives))] for data in zip(*reference_scenario_data)]
				))
				dominating.append(count_dominated(
					[ind.fitness[i] for i in range(len(objectives))], 
					[[data[i]*signs[i] for i in range(len(objectives))] for data in zip(*reference_scenario_data)],
					invert=True
				))
		rows.append(
			[
				ind.fitness[i]*signs[i] 
				for i in range(len(objectives))
			] + \
			[ind.candidate["ind"]] + \
			[str(ranks[table][ind_i])] + \
			dominated + \
			dominating + \
			[
				[r for k,r in res_storage.items() if r["ind"]==ind.candidate["ind"]][0][a]
				for a in additional_info
			]
		)
		ind_i +=1
	
	rows = [[i]+rows[i] for i in range(len(rows))]
	
	if args.reference_scenario==None:
		rows = [["pop_ind"]+titles+["actual_ind","pareto"]+additional_info]+rows
	else:
		firstrow = ["pop_ind"]+titles+["actual_ind","pareto"]
		for i in range(len(reference_scenarios_data)):
			firstrow += ["dominated_"+str(i),"dominating_"+str(i)]
		firstrow += additional_info 
		rows = [firstrow] + rows

	rows = rows[:1] + [["-" * len(header) for header in rows[0]]] + rows[1:]
	rows += rows[1:2]


	for r_i in range(len(rows)):
		row_str = ""
		for e_i in range(len(rows[r_i])):
			row_str = row_str + ('{:^'+ str(max([len(str(rows[r][e_i])) for r in range(len(rows))])+2)+'}|').format(rows[r_i][e_i])
		dprint('|'+row_str)

def save_tables():
	"""
		save generation tables to csv files 
	"""
	for table in list(set([int(gen)%len(files) for gen in args.save_table.split(" ") if gen.isdigit() or (gen[0]=="-" and gen[1:].isdigit())])):
		rows = []

		ind_i = 0
		for ind in populations[table]:
			dominated = []
			dominating = []
			if reference_scenarios_data != None:
				for rs in range(len(reference_scenarios_data)):
					reference_scenario_data = reference_scenarios_data[rs]
					dominated.append(count_dominated(
						[ind.fitness[i] for i in range(len(objectives))], 
						[[data[i]*signs[i] for i in range(len(objectives))] for data in zip(*reference_scenario_data)]
					))
					dominating.append(count_dominated(
						[ind.fitness[i] for i in range(len(objectives))], 
						[[data[i]*signs[i] for i in range(len(objectives))] for data in zip(*reference_scenario_data)],
						invert=True
					))
			rows.append([ind.fitness[i]*signs[i] for i in range(len(objectives))]+[ind.candidate['ind']]+[str(ranks[table][ind_i])]+dominated+dominating)
			ind_i += 1

		rows = [[i]+rows[i] for i in range(len(rows))]
		
		if args.reference_scenario==None:
			rows = [["pop_ind"]+titles+["actual_ind","pareto"]]+rows
		else:
			firstrow = ["pop_ind"]+titles+["actual_ind","pareto"]
			for i in range(len(reference_scenarios_data)):
				firstrow += ["dominated_"+str(i),"dominating_"+str(i)]
			rows = [firstrow] + rows

		with open(args.folder+"/results/table_gen"+str(table)+".csv","w+") as f:
			for r_i in range(len(rows)):
				row_str = ""
				for e_i in range(len(rows[r_i])):
					row_str = row_str+('{},').format(rows[r_i][e_i])
				f.write(row_str[:-1]+"\n")

def execute_individual(pop,ind,rep=0):
	"""
	Execute the simulation corresponding to a specific individual, given its population and individual indexes. Makes use of the TJSumoTools library.
	"""
	TJS.execute_scenario(
		"sumo-gui",	#using the gui
		("%s/ind%d_%s" % (
			args.folder,
			populations[pop][ind].candidate['ind'],
			sumoScenario,
		)),		#pick the correct scenario
		("%s/ind%d_rep%d_%s" % (
			args.folder,
			populations[pop][ind].candidate['ind'],
			populations[pop][ind].candidate['rep'],
			sumoScenario,
		)),		#pick the correct route file
		sumoStepSize,
		sumoPort,
		False,	#no autostart
		sumoEnd,
		sumoDelay,
		False,	#no data collection
		sumoDebug
	)

def main():
	global reference_scenarios_data,objectives,res_storage,signs,titles,additional_info,ranks

	dprint("[ Loading results storage ]")
	if args.objectives != None:
		objectives = sorted(args.objectives.split(";"))
		additional_info = []
	elif os.path.exists(args.folder+"/results_storage.pkl"):
		res_storage = pickle.load(open(args.folder+"/results_storage.pkl"))
		objectives = sorted([o for o in res_storage[res_storage.keys()[0]].keys() if o not in ["raw","ind","raw_orig"] and o[0] in ["+","-"]])
		additional_info = [o for o in res_storage[res_storage.keys()[0]].keys() if o not in ["raw","ind","raw_orig"] and o[0] not in ["+","-"]]
	else:
		dprint("ERROR: please specify objectives. Quitting.")
		sys.exit(-1)
	titles = objectives
	signs = [-1 if obj[0]=="-" else +1 for obj in objectives]
	dprint(" Objectives loaded: %s"%(str(objectives)))

	dprint("[ Loading population data ]")
	#Data loading section
	dprint("[ \tLooking for population files ]")
	if os.path.isdir(args.folder):
		raw_files = os.listdir(args.folder)
		for file in raw_files:
			if file.startswith("population") and file.endswith(".pkl"):
				files.append(file)
	else:
		dprint("Invalid folder.")
		return -1

	dprint("[ \tFiltering population requests ]")
	files.sort(key=get_no)

	allowed_populations = set()
	allowed_populations = allowed_populations.union(set([int(args.pick_generation)%len(files), int(args.table)%len(files)]))
	if args.save_table!=None:
		allowed_populations = allowed_populations.union(set([int(gen)%len(files) for gen in args.save_table.split(" ") if gen.isdigit() or (gen[0]=="-" and gen[1:].isdigit()) ]))
	if (
			"matrix" in args.plot_type.split(" ") or 
			"parcoord" in args.plot_type.split(" ") or 
			"matrix_all" in args.plot_type.split(" ")
		) and args.plot==1:
		allowed_populations = allowed_populations.union(set([int(gen)%len(files) for gen in args.matrix_plot.split(" ") if gen.isdigit() or (gen[0]=="-" and gen[1:].isdigit())]))
	if ("linemax" in args.plot_type.split(" ") or "linemin" in args.plot_type.split(" ") or "lineavg" in args.plot_type.split(" ") or "box" in args.plot_type.split(" ") or "vbox" in args.plot_type.split(" ")) and args.plot==1:
		allowed_populations = allowed_populations.union(set(range(len(files))))

	allowed_populations = list(allowed_populations)
	
	dprint("[ \tLoading populations ]")
	file_i = 0
	for file in files:
		if file_i in allowed_populations:
			f = open(args.folder+"/"+file,'rb')
			dprint("loading "+file[:-4])
			populations.append(pickle.load(f))
		else:
			populations.append(None)
		file_i +=1

	if not len(populations[allowed_populations[0]][0].fitness) == len(objectives):
		dprint("ERROR: objectives number (%d) does not match individuals fitness number (%d). Quitting"%(len(populations[0][0].fitness),len(objectives)))
		sys.exit(-1)
	
	dprint("[ \tChecking reference scenario request ]")
	if args.reference_scenario != None:
		reference_scenarios_data = load_reference_data(args.reference_scenario.split(" "))
	elif args.matrix_plot!=None and ("r" in args.matrix_plot.split(" ")) and ("matrix" in args.plot_type.split()):
		print("\033[1;33;40mWARNING:\033[1;37;40m reference scenario not specific, but requested for matrix plot! It will not be shown.")
		args.plot_type = " ".join([pt for pt in args.plot_type.split() if pt!="matrix"])


	for table in list(set([int(args.table)%len(files)]+[int(gen)%len(files) for gen in args.save_table.split(" ") if gen.isdigit() or (gen[0]=="-" and gen[1:].isdigit())])):
		ranks[table] = TJP.get_pareto_ranks([[ind.fitness[f_i]*signs[f_i] for f_i in range(len(signs))] for ind in populations[int(args.table)]],signs,list(range(len(objectives))))

	dprint("[ printing table of individuals ]")
	print_table(int(args.table) % len(populations))

	dprint("[ saving requested tables of individuals ]")
	if args.save_table!=None:
		save_tables()

	if args.plot==1:
		dprint("[ plotting fitnesses ]")
		plot_all()

	if args.run==1:
		dprint("[ running individual: gen %s, ind %s, rep %s ]"%(
			args.pick_generation,
			args.pick_individual,
			args.pick_repetition
		))
		execute_individual(int(args.pick_generation),int(args.pick_individual),rep=int(args.pick_repetition))

if __name__ == "__main__":
	main()

