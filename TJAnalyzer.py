#!/usr/bin/env python

import argparse
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer - Result Analyzer.")
parser.add_argument("-f","--folder", type=str, help="Result folder to analyze", required=True)
parser.add_argument("-r","--run", type=int, help="Re-run the simulation of a specific individual (default is 0)", required=False, default=0)
parser.add_argument("-pg","--pick-generation", type=str, help="re-simulate a populaton, select which generation (default is last one)", required=False, default=-1)
parser.add_argument("-pi","--pick-individual", type=str, help="re-simulate a populaton, select which individual (default is individual 0)", required=False, default=0)
parser.add_argument("-pr","--pick-repetition", type=str, help="re-simulate a populaton, select which repetition of the individual (default is repetition 0)", required=False, default=0)
parser.add_argument("-pl","--plot", type=int, help="Plot objective throughout generations", required=False, default=1)
parser.add_argument("-pt","--plot-type", type=str, help="Select the types of plots to output, can be more than one, separated by a space. Possible choices are \"matrix\",\"box\", \"linemax\", \"linemin\", \"lineavg\".", required=False, default="box")
parser.add_argument("-pp","--plot-pdf", type=str, help="Pdf file name in which plots are are saved (if requested) instead of opening the GUI (will be saved in $folder/results)", required=False, default=None)
parser.add_argument("-t","--table", type=str, help="Print a magnificent table of a specific generation. Default is pick generation", required=False, default="-1")
parser.add_argument("-rs","--reference-scenario", type=str, help="Load a .csv file to compare the data to.", required=False, default=None)
parser.add_argument("-mp","--matrix-plot", type=str, help="Select what generations to plot in the matrix plot (if requested). Provide a string with all the requested generations separated by a space. Default is -1", required=False, default="-1")

args = parser.parse_args()
if args.table=="a":
	args.table=args.pick_generation

import os
import pickle
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import TJSumoTools as TJS

dprint = TJS.dprint

files = []
populations = []
reference_scenario_data = None

#debug output
TJS.debug = True
sumoDebug = False
netconvertDebug = False

#plotting paramenters
titles = ["Average speed","Arrived","Teleported","Accidents"]
objectives = ["+agv_speed","+arrived","-teleported","-accidents"]
#titles = ["Arrived","Teleported","Accidents"]
#objectives = ["+arrived","-teleported","-accidents"]
signs = [+1 if obj[0]=="+" else -1 for obj in objectives]

#scenario parameters
sumoScenario = "trento"
sumoPort = 27910
sumoEnd = 3600
sumoDelay = 0.1
sumoStepSize = 0.1

#reordering function for population sorting
def get_no(e):
	return int(e[len("population"):-len(".pkl")])

def get_pareto_front(population,objectives_indexes):
		#I AM SO SORRY
		#TL;DR: counts how many individuals of the same generation dominates its fitness for the current fitnesses. 
		#If 0, then it belongs to the pareto front of the generation
		#I mean, it **should** do it, it's kinda impossible to understand though	

	return [
		#take the individual within the current generation gen...
		population[c]
		for c in range(len(population)) 
		#...only if no other individual in its generation dominates it, meaning that...
		if (
			# ...the number individuals dominating...
			int(count_dominated(
				[
					#...our actual individual c...
					population[c][k]*signs[k]
					#...for the current objectives i,j...
					for k in objectives_indexes
				],
				[
					#...considering the entire actual population gen...
					[
						#...but only considering the current objectives i,j...
						population[ind][k]*signs[k]
					 	for k in objectives_indexes
					] for ind in range(len(population))
				]
				#...[keeping in mind that the function return a "fraction" of dominating individuals, e.g. 20/30, and we need the first part]...
				).split("/")[0]
			#...MUST be 0, i.e. no other individuals dominates the actual individual...
			)==0)
		]

def generate_plot_matrix():
	plt.ioff()

	f = plt.figure(2,figsize=(16,10))
	f.suptitle(args.folder+" - matrix plot")

	requested_gens = args.matrix_plot.split()
	references = "r" in requested_gens
	front_only = "f" in requested_gens

	requested_gens = [int(r) for r in requested_gens if r.isdigit() or (r[0]=="-" and r[1:].isdigit())]

	dprint("[ Requests for matrix plot: " + str(requested_gens) + " ]")
	matrix_size = len(objectives)
	index = 0
	for i in range(matrix_size): 
		for j in range(matrix_size):
			if i>j:
				ax = f.add_subplot(matrix_size,matrix_size,index+1)
				color = 0
				pareto_fronts = []
				for gen in requested_gens:
					population = [[ind.fitness[o]*signs[o] for o in range(len(objectives))] for ind in populations[gen]]
					pareto1 = get_pareto_front(population,[i,j])
					if not front_only:
						ax.scatter(
							[population[c][j] for c in range(len(population)) if population[c] not in pareto1],
							[population[c][i] for c in range(len(population)) if population[c] not in pareto1],
							color="C"+str(color%10),
						)
					pareto_fronts.append(([ind[j] for ind in pareto1],[ind[i] for ind in pareto1]))
					color+=1
					if color==3:
						color+=1
				if references:
					ref_quantity = len(reference_scenario_data[0])
					ref_gen = [[reference_scenario_data[o][c] for o in range(len(objectives))] for c in range(ref_quantity)]
					pareto2 = get_pareto_front(ref_gen,[i,j])
					if not front_only:
						ax.scatter(
							[ref_gen[c][j]for c in range(len(ref_gen)) if ref_gen[c] not in pareto2],
							[ref_gen[c][i] for c in range(len(ref_gen)) if ref_gen[c] not in pareto2],
							color="C"+str(color%10)
						)
					pareto_fronts.append(([ind[j] for ind in pareto2],[ind[i] for ind in pareto2]))
				color = 0
				for fr in pareto_fronts:
					ax.scatter(
						fr[0],
						fr[1],
						marker="D",
						color="C"+str(color%10),
						edgecolors='r'
					) 
					color+=1
					if color==3:
						color+=1

			elif i==j:
				ax = f.add_subplot(matrix_size,matrix_size,index+1)
				ax.set_axis_off()
				ax.text(0.5, 0.5, titles[i], ha="center", va="center", fontsize=25, wrap=True)	 
			index+=1

	#legend
	ax = f.add_subplot(matrix_size,matrix_size,matrix_size)
	top_offset = 0.05
	line_height = 0.2

	ax.axis("off")
	ax.text(0,1-top_offset,"Legend:", va="top",wrap=True)

	color = 0
	for req_i in range(len(requested_gens)):
		req = requested_gens[req_i]
		ax.text(0,1-top_offset-(line_height*(req_i+1)),
			"Generation " + str(req),
			color="C"+str(color%10),
			va="top",wrap=True,bbox={'facecolor':'white','edgecolor':'black'}
		)
		color+=1
		if color==3:
			color+=1

	if references:
		ax.text(0,1-top_offset-(line_height*(len(requested_gens)+1)),
			"Reference individuals",
			color="C"+str(color%10),
			va="top",wrap=True,bbox={'facecolor':'white','edgecolor':'black'}
		)



	if args.plot_pdf!=None:
		if not os.path.isdir(args.folder+"/results"):
			os.mkdir(args.folder + "/results")
		f.savefig(args.folder + "/results/" + args.plot_pdf + "_matrix", format="pdf") #TODO use multipage backend thing


#Plotting procedure
def plot_all():
	plt.ioff()

	if "linemax" in args.plot_type.split() or "linemin" in args.plot_type.split() or "lineavg" in args.plot_type.split() or "box" in args.plot_type.split():

		f = plt.figure(1,figsize=(16,10))
		f.suptitle(args.folder+" - results")

		plotnumber = len(populations[0][0].fitness)
		index = 0
		for plot in range(plotnumber):
			ax = f.add_subplot(int(np.ceil(np.sqrt(plotnumber))),int(np.ceil(np.sqrt(plotnumber))),index+1,
				xlabel="Generation",
				ylabel=objectives[index]
			)

			xticks = list(range(len(populations)))
			
			#**calculations**
			if "linemax" in args.plot_type.split():
				ax.plot(list(range(len(populations))),[np.max([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="max")
			if "lineavg" in args.plot_type.split():
				ax.plot(list(range(len(populations))),[np.mean([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="mean")
			if "linemin" in args.plot_type.split():
				ax.plot(list(range(len(populations))),[np.min([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="min")

			#locs, labels = ax.xticks() 

			if "box" in args.plot_type.split():
				ax.boxplot([[cand.fitness[index]*signs[index] for cand in pop] for pop in populations], positions=xticks)

			#ax.xticks(locs)

			ax.legend()
			ax.set_title(titles[index])
			#ax.ylabel(objectives[index])
			#ax.xlabel("Generation")
			#ax.xaxis.set_major_locator(MaxNLocator(integer=True))

			index+=1

		if args.plot_pdf!=None:
			if not os.path.isdir(args.folder+"/results"):
				os.mkdir(args.folder + "/results")
			f.savefig(args.folder + "/results/" + args.plot_pdf, format="pdf")

	if "matrix" in args.plot_type.split():
		generate_plot_matrix()

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

def load_reference_data(ref_filename):
	with open(ref_filename, 'rb') as ref_file:
		reference_scenario_data = pickle.load(ref_file)
	return [[refrep[obj[1:]] for refrep in reference_scenario_data] for obj in objectives]

#Table printing procedure
def print_table(table):
	title = ("******** Table of individuals for generation %d ********" % table)
	dprint("-"*len(title))
	dprint(title)
	dprint("-"*len(title))
	rows = []

	for ind in populations[table]:
		dominated = []
		dominating = []
		#print([[data[i]*signs[i] for i in range(len(objectives))] for data in reference_scenario_data])
		if args.reference_scenario!=None:
			dominated.append(count_dominated(
				[ind.fitness[i] for i in range(len(objectives))], 
				[[data[i]*signs[i] for i in range(len(objectives))] for data in zip(*reference_scenario_data)]
			))
			dominating.append(count_dominated(
				[ind.fitness[i] for i in range(len(objectives))], 
				[[data[i]*signs[i] for i in range(len(objectives))] for data in zip(*reference_scenario_data)],
				invert=True
			))
		rows.append([ind.fitness[i]*signs[i] for i in range(len(objectives))]+[ind.candidate['ind']]+dominated+dominating)
	
	rows = [[i]+rows[i] for i in range(len(rows))]
	
	if args.reference_scenario==None:
		rows = [["pop_ind"]+titles+["actual_ind"]]+rows
	else:
		rows = [["pop_ind"]+titles+["actual_ind","dominated","dominating"]]+rows

	rows = rows[:1] + [["-" * len(header) for header in rows[0]]] + rows[1:]
	rows += rows[1:2]


	for r_i in range(len(rows)):
		row_str = ""
		for e_i in range(len(rows[r_i])):
			row_str = row_str+('{:^'+str(max([len(str(rows[r][e_i])) for r in range(len(rows))])+2)+'}|').format(rows[r_i][e_i])
		dprint('|'+row_str)

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

def __main__():
	global reference_scenario_data
	#Data loading section
	if os.path.isdir(args.folder):
		raw_files = os.listdir(args.folder)
		for file in raw_files:
			if file.startswith("population") and file.endswith(".pkl"):
				files.append(file)
	else:
		dprint("Invalid folder.")
		return -1

	files.sort(key=get_no)

	allowed_populations = None
	if (args.plot==0):
		allowed_populations = list(set([int(args.pick_generation)%len(files), int(args.table)%len(files)]))

	file_i = 0
	for file in files:
		if allowed_populations==None or (file_i in allowed_populations):
			f = open(args.folder+"/"+file,'rb')
			dprint("loading "+file[:-4])
			populations.append(pickle.load(f))
		else:
			populations.append(None)
		file_i +=1

	if args.reference_scenario!=None:
		reference_scenario_data = load_reference_data(args.reference_scenario)
	elif "r" in args.matrix_plot.split():
		print("\033[1;33;40mWARNING:\033[1;37;40m reference scenario not specific, but requested for matrix plot! It will not be shown.")

	dprint("[ printing table of individuals ]")
	print_table(int(args.table) % len(populations))

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
	__main__()

