from pylab import *

from inspyred.ec.emo import Pareto
from numpy.random import RandomState

import functools

def choice_without_replacement(rng, n, size) :
    result = set()
    while len(result) < size :
        result.add(rng.randint(0, n))
    return result

class NumpyRandomWrapper(RandomState):
    def __init__(self, seed=None):
        super(NumpyRandomWrapper, self).__init__(seed)
        
    def sample(self, population, k):
        if isinstance(population, int) :
            population = range(population)           
        
        return asarray([population[i] for i in 
                        choice_without_replacement(self, len(population), k)])
        #return #self.choice(population, k, replace=False)
        
    def random(self):
        return self.random_sample()
    
    def gauss(self, mu, sigma):
        return self.normal(mu, sigma)
    
def initial_pop_observer(population, num_generations, num_evaluations, 
                         args):
    if num_generations == 0 :
        args["initial_pop_storage"]["individuals"] = asarray([guy.candidate 
                                                 for guy in population]) 
        args["initial_pop_storage"]["fitnesses"] = asarray([guy.fitness 
                                          for guy in population]) 
        
def generator(random, args):
    return asarray([random.uniform(args["pop_init_range"][0],
                                   args["pop_init_range"][1]) 
                    for _ in range(args["num_vars"])])

def generator_wrapper(func):
        @functools.wraps(func)
        def _generator(random, args):
            return asarray(func(random, args))
        return _generator

class CombinedObjectives(Pareto):
    def __init__(self, pareto, args):
        """ edit this function to change the way that multiple objectives
        are combined into a single objective
        
        """
        
        Pareto.__init__(self, pareto.values)
        if "fitness_weights" in args :
            weights = asarray(args["fitness_weights"])
        else : 
            weights = asarray([1 for _ in pareto.values])
            
        self.fitness = sum(asarray(pareto.values) * weights)
        
    def __lt__(self, other):
        return self.fitness < other.fitness
        
def single_objective_evaluator(candidates, args):
    problem = args["problem"]
    return [CombinedObjectives(fit,args) for fit in 
            problem.evaluator(candidates, args)]
