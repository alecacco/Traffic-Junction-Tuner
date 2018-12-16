from pylab import *

from inspyred.ec.emo import NSGA2
from inspyred.ec import terminators, variators, replacers, selectors
from inspyred.ec import EvolutionaryComputation

import inspyred_utils
import plot_utils
import pickle

def save_observer(population, num_generations, num_evaluations, args):
	print("saved population"+str(num_generations))
	population_save = open(args["folder"]+"/population"+str(num_generations)+".pkl", 'wb')
	pickle.dump(population, population_save)
	population_save.close()


def run(random, problem, display=False, num_vars=0, use_bounder=True,
		variator=None, **kwargs) :
	""" run NSGA2 on the given problem """
	
	#create dictionaries to store data about initial population, and lines
	initial_pop_storage = {}
	
	algorithm = NSGA2(random)
	algorithm.terminator = terminators.generation_termination
	if variator is None :
		#algorithm.variator = [variators.blend_crossover,
		#                      variators.gaussian_mutation]
		pass
	else :
		algorithm.variator = problem.variator

	kwargs["num_selected"]=kwargs["pop_size"]
	if use_bounder :
		kwargs["bounder"]=problem.bounder

	# TODO: make custom observer that dumps each generation into a list, then at the end spit it out in a pickle
	if display and problem.objectives == 2:
		# don't like inspyred's plot observer, so use our custom one
		algorithm.observer = [plot_utils.multi_objective_plotting_observer,
							  inspyred_utils.initial_pop_observer,
							  save_observer]

		animator = plot_utils.MultiObjectiveAnimator(
						kwargs.setdefault("objective_1","Objective 1"),
						kwargs.setdefault("objective_2","Objective 2"),
						kwargs.setdefault("constraint_function",None))
	else :
		algorithm.observer = inspyred_utils.initial_pop_observer
		animator = None
		algorithm.observer = [save_observer]


	final_pop = algorithm.evolve(evaluator=problem.evaluator,
						  maximize=problem.maximize,
						  initial_pop_storage=initial_pop_storage,
						  num_vars=num_vars, animator=animator,
						  generator=problem.generator,
						  **kwargs)

	'''
	archive_file = open(kwargs["folder"]+"/archive.pkl", 'wb')
	pickle.dump(algorithm.archive, archive_file)
	archive_file.close()


	best_guy = final_pop[0].candidate[0:num_vars]
	best_fitness = final_pop[0].fitness
	final_pop_fitnesses = asarray([guy.fitness for guy in final_pop])
	final_pop = asarray([guy.candidate[0:num_vars] for guy in final_pop])

	if animator is not None :
		animator.stop()
	
	if display :
		# Plot the parent and the offspring on the fitness landscape
		# (only for 1D or 2D functions)
		if num_vars == 1 :
			plot_utils.plot_results_multi_objective_1D(problem,
								  initial_pop_storage["individuals"],
								  initial_pop_storage["fitnesses"],
								  final_pop, final_pop_fitnesses,
								  'Initial Population', 'Final Population',
								  len(final_pop_fitnesses[0]))

		elif num_vars == 2 :
			plot_utils.plot_results_multi_objective_2D(problem,
								  initial_pop_storage["individuals"],
								  final_pop, 'Initial Population',
								  'Final Population',
								  len(final_pop_fitnesses[0]))
	'''
	return final_pop#, final_pop_fitnesses

def run_ga(random,problem, display=True, num_vars=0,
		   maximize=False, use_bounder=True, **kwargs) :
	""" run a GA on the given problem """

	#create dictionaries to store data about initial population, and lines
	initial_pop_storage = {}

	algorithm = EvolutionaryComputation(random)
	algorithm.terminator = terminators.generation_termination
	algorithm.replacer = replacers.generational_replacement
	algorithm.variator = [variators.uniform_crossover,
						  variators.gaussian_mutation]
	algorithm.selector = selectors.tournament_selection
	if display and problem.objectives == 2:
		# don't like inspyred's plot observer, so use our custom one
		algorithm.observer = [plot_utils.plotting_observer,
							  inspyred_utils.initial_pop_observer]
		animator = plot_utils.Animator(-20)
	else :
		algorithm.observer = inspyred_utils.initial_pop_observer
		animator = None

	kwargs["num_selected"]=kwargs["pop_size"]
	if use_bounder :
		kwargs["bounder"]=problem.bounder
	if "pop_init_range" in kwargs :
		kwargs["generator"]=inspyred_utils.generator
	else :
		kwargs["generator"]=problem.generator

	kwargs["problem"] = problem
	final_pop = algorithm.evolve(evaluator=
								 inspyred_utils.single_objective_evaluator,
						  maximize=problem.maximize,
						  initial_pop_storage=initial_pop_storage,
						  num_vars=num_vars, animator=animator,
						  **kwargs)

	best_guy = final_pop[0].candidate
	best_fitness = final_pop[0].fitness.fitness
	final_pop_fitnesses = asarray([guy.fitness for guy in final_pop])
	final_pop = asarray([guy.candidate for guy in final_pop])

	if animator is not None :
		animator.stop()

	if display :

		# Plot the parent and the offspring on the fitness landscape
		# (only for 1D or 2D functions)
		if num_vars == 1 :
			plot_utils.plot_results_multi_objective_1D(problem,
								  initial_pop_storage["individuals"],
								  initial_pop_storage["fitnesses"],
								  final_pop, final_pop_fitnesses,
								  'Initial Population', 'Final Population',
								  len(final_pop_fitnesses[0]))

		elif num_vars == 2 :
			plot_utils.plot_results_multi_objective_2D(problem,
								  initial_pop_storage["individuals"],
								  final_pop, 'Initial Population',
								  'Final Population',
								  len(final_pop_fitnesses[0]))


	return best_guy, best_fitness
