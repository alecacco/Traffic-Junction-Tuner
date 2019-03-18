#!/usr/bin/env python

import argparse
parser = argparse.ArgumentParser(description="Traffic Junction Optimizer - Result Analyzer.")
parser.add_argument("-f","--folder", type=str, help="Result folder to analyze", required=True)
parser.add_argument("-r","--run", type=int, help="Re-run the simulation of a specific individual (default is 0)", required=False, default=0)
parser.add_argument("-pg","--pick-generation", type=str, help="re-simulate a populaton, select which generation (default is last one)", required=False, default=-1)
parser.add_argument("-pi","--pick-individual", type=str, help="re-simulate a populaton, select which individual (default is individual 0)", required=False, default=0)
parser.add_argument("-pr","--pick-repetition", type=str, help="re-simulate a populaton, select which repetition of the individual (default is repetition 0)", required=False, default=0)
parser.add_argument("-pl","--plot", type=int, help="Plot objective throughout generations", required=False, default=1)
parser.add_argument("-pt","--plot-type", type=str, help="Select the types of plots to output, can be more than one, separated by a space. Possible choices are \"box\", \"linemax\", \"linemin\", \"lineavg\".", required=False, default="box")
parser.add_argument("-pp","--plot-pdf", type=str, help="Pdf file name in which plots are are saved (if requested) instead of opening the GUI (will be saved in $folder/results)", required=False, default=None)
parser.add_argument("-t","--table", type=str, help="Print a magnificent table of a specific generation. Default is pick generation", required=False, default="a")

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

#debug output
TJS.debug = True
sumoDebug = False
netconvertDebug = False

#plotting paramenters
objectives = ["+agv_speed","+arrived","-teleported","-accidents"]
signs = [+1 if obj[0]=="+" else -1 for obj in objectives]
titles = ["Average speed","Arrived","Teleported","Accidents"]

#scenario parameters
sumoScenario = "trento"
sumoPort = 27910
sumoEnd = 3600
sumoDelay = 0.1
sumoStepSize = 0.1

#reordering function for population sorting
def get_no(e):
	return int(e[len("population"):-len(".pkl")])

#Plotting procedure
def plot_all():
	plt.ioff()

	plt.figure(figsize=(16,10))
	plt.suptitle(args.folder+" - results")

	plotnumber = len(populations[0][0].fitness)
	index = 0
	for plot in range(plotnumber):
		ax = plt.subplot(int(np.ceil(np.sqrt(plotnumber))),int(np.ceil(np.sqrt(plotnumber))),index+1)

		xticks = list(range(len(populations)))
		
		#**calculations**
		if "linemax" in args.plot_type.split():
			plt.plot(list(range(len(populations))),[np.max([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="max")
		if "lineavg" in args.plot_type.split():
			plt.plot(list(range(len(populations))),[np.mean([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="mean")
		if "linemin" in args.plot_type.split():
			plt.plot(list(range(len(populations))),[np.min([cand.fitness[index]*signs[index] for cand in pop]) for pop in populations], label="min")

		locs, labels = plt.xticks() 

		if "box" in args.plot_type.split():
			plt.boxplot([[cand.fitness[index]*signs[index] for cand in pop] for pop in populations], positions=xticks)

		plt.xticks(locs)

		plt.legend()
		plt.title(titles[index])
		plt.ylabel(objectives[index])
		plt.xlabel("Generation")
		ax.xaxis.set_major_locator(MaxNLocator(integer=True))

		index+=1

	if args.plot_pdf==None:
		plt.show()
	else:
		if not os.path.isdir(args.folder+"/results"):
			os.mkdir(args.folder + "/results")
		plt.savefig(args.folder + "/results/" + args.plot_pdf, format="pdf")


#Table printing procedure
def print_table(table):
	title = ("*** Table of individuals for generation %d **" % table)
	dprint("-"*len(title))
	dprint(title)
	dprint("-"*len(title))
	rows = []
	for ind in populations[table]:
		rows.append([ind.fitness[i]*signs[i] for i in range(len(objectives))]+[ind.candidate['ind']])
	rows = [[i]+rows[i] for i in range(len(rows))]
	rows = [["pop_ind"]+titles+["actual_ind"]]+rows
	for r_i in range(len(rows)):
		row_str = ""
		for e_i in range(len(rows[r_i])):
			row_str=row_str+('{:^'+str(max([len(str(rows[r][e_i])) for r in range(len(rows))])+2)+'}|').format(rows[r_i][e_i])
		dprint('|'+row_str)


def execute_individual(pop,ind,rep=0):
	TJS.execute_scenario(
		"sumo-gui",
		("%s/ind%d_%s" % (
			args.folder,
			populations[pop][ind].candidate['ind'],
			sumoScenario,
		)),		("%s/ind%d_rep%d_%s" % (
			args.folder,
			populations[pop][ind].candidate['ind'],
			populations[pop][ind].candidate['rep'],
			sumoScenario,
		)),
		sumoStepSize,
		sumoPort,
		False,	#no autostart
		sumoEnd,
		sumoDelay,
		False,	#no data collection
		sumoDebug
	)

def __main__():
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

