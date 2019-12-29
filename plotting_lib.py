import matplotlib.pyplot as plt
import numpy as np

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

def get_pareto_front(population,signs,objectives_indexes):
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

def get_pareto_ranks(population,signs,objectives_indexes):
	ranks = [-1]*len(population)
	curpop = [p for p in population]
	currank = 0
	while len(curpop)>0:
		pareto = get_pareto_front(curpop,signs,objectives_indexes)
		for p in pareto:
			ranks[population.index(p)] = currank
			curpop.remove(p)
		currank += 1
	return ranks


def generate_plot_matrix(f,data,objectives,signs,titles=None,references=False,front_only=False,series_names=[],title="Matrix plot",reference_scenarios_data=[]):
	plt.ioff()

	f.suptitle(title)

	if titles == None:
		titles = ["" for _ in range(objectives)]

	matrix_size = objectives

	#legend
	ax = f.add_subplot(matrix_size,matrix_size,matrix_size)
	top_offset = 0.05
	# the 0.2 height factor was calibrated for 3x3 matrix plot
	# NOTE for larger ones we overdraw the legend outside its axis, so too many  
	# populations WILL cause the legend to be drawn UNDER to the bottom-right label axis
	line_height = 0.2/3.0*objectives 

	ax.axis("off")
	ax.text(0,1-top_offset,"Legend:", va="top",wrap=True)

	color = 0
	for serie_name_i in range(len(series_names)):
		serie_name = series_names[serie_name_i]
		ax.text(0,1-top_offset-(line_height*(serie_name_i+1)),
			serie_name,
			color="C"+str(color%10),
			va="top",wrap=True,bbox={'facecolor':'white','edgecolor':'black'},

		)
		color+=1
		if color==3:
			color+=1


	if references:
		for rs in range(len(reference_scenarios_data)):
			ax.text(0,1-top_offset-(line_height*(len(data)+1+rs)),
				"Reference "+str(rs),
				color="C"+str(color%10),
				va="top",wrap=True,bbox={'facecolor':'white','edgecolor':'black'}
			)
			color+=1
			if color==3:
				color+=1

	index = 0
	for i in range(matrix_size): 
		for j in range(matrix_size):
			if i>j:
				ax = f.add_subplot(matrix_size,matrix_size,index+1)
				plot_limits = {
					"x":[np.inf,-np.inf],
					"y":[np.inf,-np.inf]
				}
				color = 0
				pareto_fronts = []
				for pop in data:
					population = [[ind[o] for o in range(objectives)] for ind in pop]
					pareto1 = get_pareto_front(population,signs,[i,j])
					if not front_only:
						ax.scatter(
							[population[c][j] for c in range(len(population)) if population[c] not in pareto1],
							[population[c][i] for c in range(len(population)) if population[c] not in pareto1],
							color="C"+str(color%10),
						)
						plot_limits["x"][0] = np.min([plot_limits["x"][0]]+[population[c][j] for c in range(len(population))])
						plot_limits["x"][1] = np.max([plot_limits["x"][1]]+[population[c][j] for c in range(len(population))])
						plot_limits["y"][0] = np.min([plot_limits["y"][0]]+[population[c][i] for c in range(len(population))])
						plot_limits["y"][1] = np.max([plot_limits["y"][1]]+[population[c][i] for c in range(len(population))])
					else:
						plot_limits["x"][0] = np.min([plot_limits["x"][0]]+[population[c][j] for c in range(len(population)) if population[c] in pareto1])
						plot_limits["x"][1] = np.max([plot_limits["x"][1]]+[population[c][j] for c in range(len(population)) if population[c] in pareto1])
						plot_limits["y"][0] = np.min([plot_limits["y"][0]]+[population[c][i] for c in range(len(population)) if population[c] in pareto1])
						plot_limits["y"][1] = np.max([plot_limits["y"][1]]+[population[c][i] for c in range(len(population)) if population[c] in pareto1])						
					pareto_fronts.append(([ind[j] for ind in pareto1],[ind[i] for ind in pareto1]))
					color+=1
					if color==3:
						color+=1
				if references:
					for rs in range(len(reference_scenarios_data)):
						reference_scenario_data = reference_scenarios_data[rs]
						ref_quantity = len(reference_scenario_data[0])
						ref_gen = [[reference_scenario_data[o][c] for o in range(objectives)] for c in range(ref_quantity)]
						pareto2 = get_pareto_front(ref_gen,signs,[i,j])
						if not front_only:
							ax.scatter(
								[ref_gen[c][j]for c in range(len(ref_gen)) if ref_gen[c] not in pareto2],
								[ref_gen[c][i] for c in range(len(ref_gen)) if ref_gen[c] not in pareto2],
								color="C"+str(color%10)
							)
							plot_limits["x"][0] = np.min([plot_limits["x"][0]]+[ref_gen[c][j] for c in range(len(ref_gen))])
							plot_limits["x"][1] = np.max([plot_limits["x"][1]]+[ref_gen[c][j] for c in range(len(ref_gen))])
							plot_limits["y"][0] = np.min([plot_limits["y"][0]]+[ref_gen[c][i] for c in range(len(ref_gen))])
							plot_limits["y"][1] = np.max([plot_limits["y"][1]]+[ref_gen[c][i] for c in range(len(ref_gen))])
						else:
							plot_limits["x"][0] = np.min([plot_limits["x"][0]]+[ref_gen[c][j] for c in range(len(ref_gen)) if ref_gen[c] in pareto2])
							plot_limits["x"][1] = np.max([plot_limits["x"][1]]+[ref_gen[c][j] for c in range(len(ref_gen)) if ref_gen[c] in pareto2])
							plot_limits["y"][0] = np.min([plot_limits["y"][0]]+[ref_gen[c][i] for c in range(len(ref_gen)) if ref_gen[c] in pareto2])
							plot_limits["y"][1] = np.max([plot_limits["y"][1]]+[ref_gen[c][i] for c in range(len(ref_gen)) if ref_gen[c] in pareto2])							
						pareto_fronts.append(([ind[j] for ind in pareto2],[ind[i] for ind in pareto2]))
						color+=1
						if color==3:
							color+=1
				
				ax.set_xlim((plot_limits["x"][0] - (plot_limits["x"][1]-plot_limits["x"][0])*0.05,plot_limits["x"][1] + (plot_limits["x"][1]-plot_limits["x"][0])*0.05))
				ax.set_ylim((plot_limits["y"][0] - (plot_limits["y"][1]-plot_limits["y"][0])*0.05,plot_limits["y"][1] + (plot_limits["y"][1]-plot_limits["y"][0])*0.05))
				
				if j>0:
					ax.set_yticklabels(""*len(ax.get_yticklabels()))
				if i<matrix_size-1:
					ax.set_xticklabels(""*len(ax.get_xticklabels()))

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
				ax.text(0.5, 0.5, titles[i], ha="center", va="center", wrap=True)	 
			index+=1



def generate_plot_parcoord(f,data,objectives,signs,titles=None,references=False,front_only=False,series_names=[],title="Matrix plot",reference_scenarios_data=[]):
	plt.ioff()

	f.suptitle(title)

	if titles == None:
		titles = ["" for _ in range(objectives)]

	refdata = []
	if references:
		refdata = [[[rs[o][i] for o in range(objectives)] for i in range(len(rs[0]))] for rs in reference_scenarios_data]

	axes = [f.add_subplot(1,objectives-1,i+1) for i in range(objectives-1)]
	coeff = []
	f.subplots_adjust(wspace=0)
	for ax_i in range(len(axes)):
		ax = axes[ax_i]
		ax.set_xticks([0,1])	
		ax.set_xticklabels([titles[ax_i],""])

		ymin = 0
		ymax = 0
		if references:
			ymin = np.min([
				np.min([np.min([ind[ax_i] for ind in pop]) for pop in data]),
				np.min([np.min([ind[ax_i] for ind in pop]) for pop in refdata]),
			])
			ymax = np.max([
				np.max([np.max([ind[ax_i] for ind in pop]) for pop in data]),
				np.max([np.max([ind[ax_i] for ind in pop]) for pop in refdata]),
			])
		else:
			ymin = np.min([np.min([ind[ax_i] for ind in pop]) for pop in data])
			ymax = np.max([np.max([ind[ax_i] for ind in pop]) for pop in data])

		ax.set_ylim((ymin,ymax))
		ax.set_xlim((0,1))
		coeff.append((ymin,ymax-ymin))
	
	ax = axes[-1].twinx()
	ax.set_xticklabels([titles[-2],titles[-1]])
	ymin = 0
	ymax = 0
	if references:
		ymin = np.min([
			np.min([np.min([ind[-1] for ind in pop]) for pop in data]),
			np.min([np.min([ind[-1] for ind in pop]) for pop in refdata]),
		])
		ymax = np.max([
			np.max([np.max([ind[-1] for ind in pop]) for pop in data]),
			np.max([np.max([ind[-1] for ind in pop]) for pop in refdata]),
		])
	else:
		ymin = np.min([np.min([ind[-1] for ind in pop]) for pop in data])
		ymax = np.max([np.max([ind[-1] for ind in pop]) for pop in data])

	ax.set_ylim((ymin,ymax))
	ax.set_xlim((0,1))
	coeff.append((ymin,ymax-ymin))

	color = 0
	for pop_i in range(len(data)+len(refdata)):
		if pop_i<len(data):
			pop = data[pop_i]
		else:
			pop = refdata[pop_i-len(data)]

		for ind in pop:
			is_in_pareto = ind in get_pareto_front(pop,[1]*objectives,[i in range(objectives)])
			if is_in_pareto and pop_i<len(data):
				linewidth = 2
				linestyle = "-"
				marker = "o"
			elif pop_i>=len(data):
				linewidth = 1
				linestyle = "-"
				marker = "o"
			else:
				linewidth = 1
				linestyle = ":"
				marker = ""
			for ax_i in range(len(axes)):
				ax = axes[ax_i]
				if is_in_pareto and pop_i<len(data):
					line, = ax.plot([
						ind[ax_i],
						(ind[ax_i+1]-coeff[ax_i+1][0])/float(coeff[ax_i+1][1])*coeff[ax_i][1]+coeff[ax_i][0]],
						color="C"+str(color),
						marker = marker,
						linewidth = linewidth,
						linestyle = linestyle,
						zorder=5
					)
				elif pop_i>=len(data):
					line, = ax.plot([
						ind[ax_i],
						(ind[ax_i+1]-coeff[ax_i+1][0])/float(coeff[ax_i+1][1])*coeff[ax_i][1]+coeff[ax_i][0]],
						color="C"+str(color),
						marker = marker,
						linewidth = linewidth,
						linestyle = linestyle,
					)
				else:
					ax.plot([
						ind[ax_i],
						(ind[ax_i+1]-coeff[ax_i+1][0])/float(coeff[ax_i+1][1])*coeff[ax_i][1]+coeff[ax_i][0]],
						color="C"+str(color),
						marker = marker,
						linewidth = linewidth,
						linestyle = linestyle,
					)
		if pop_i < len(data): 
			line.set_label(series_names[pop_i])
		else: 
			line.set_label("Reference "+str(pop_i-len(data)))
		color = (color+1)%10
		if color==3:
			color+=1

	axes[-1].legend()
