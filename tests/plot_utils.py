from pylab import *
from matplotlib.animation import FuncAnimation
from Queue import Queue
import sys
from inspyred_utils import CombinedObjectives

def plot_1D(axis, problem, x_limits) :
    dx = (x_limits[1] - x_limits[0])/200.0
    x = arange(x_limits[0], x_limits[1]+dx, dx)
    x = x.reshape(len(x),1)
    y = problem.evaluator(x, None)
    axis.plot(x,y,'-b')

def plot_2D(axis, problem, x_limits) :
    dx = (x_limits[1] - x_limits[0])/50.0
    x = arange(x_limits[0], x_limits[1]+dx, dx)
    z = asarray( [problem.evaluator([[i,j] for i in x], None) for j in x])
    return axis.contourf(x, x, z, 64, cmap=cm.hot_r)
    
def plot_results_1D(problem, individuals_1, fitnesses_1, 
                    individuals_2, fitnesses_2, title_1, title_2) :
    fig = figure()
    ax1 = fig.add_subplot(2,1,1)
    ax1.plot(individuals_1, fitnesses_1, '.b', markersize=7)
    lim = max(map(abs,ax1.get_xlim()))
    
    ax2 = fig.add_subplot(2,1,2)
    ax2.plot(individuals_2, fitnesses_2, '.b', markersize=7)
    lim = max([lim] + map(abs, ax2.get_xlim()))

    ax1.set_xlim(-lim, lim)
    ax2.set_xlim(-lim, lim)

    plot_1D(ax1, problem, [-lim, lim])
    plot_1D(ax2, problem, [-lim, lim])
    
    ax1.set_ylabel('Fitness')
    ax2.set_ylabel('Fitness')
    ax1.set_title(title_1)
    ax2.set_title(title_2)

def plot_results_2D(problem, individuals_1, individuals_2, 
                    title_1, title_2) :
    fig = figure()
    ax1 = fig.add_subplot(2,1,1, aspect='equal')
    ax1.plot(individuals_1[:,0], individuals_1[:,1], '.b', markersize=7)
    lim = max(map(abs,ax1.get_xlim()) + map(abs,ax1.get_ylim()))

    ax2 = fig.add_subplot(2,1,2, aspect='equal')
    ax2.plot(individuals_2[:,0], individuals_2[:,1], '.b', markersize=7)
    lim = max([lim] + 
              map(abs,ax2.get_xlim()) + 
              map(abs,ax2.get_ylim()))

    ax1.set_xlim(-lim, lim)
    ax1.set_ylim(-lim, lim)
    ax1.set_title(title_1) 
    ax1.locator_params(nbins=5)
    
    ax2.set_xlim(-lim, lim)
    ax2.set_ylim(-lim, lim)
    ax2.set_title(title_2)    
    ax2.set_xlabel('x0')
    ax2.set_ylabel('x1')
    ax2.locator_params(nbins=5)
    
    plot_2D(ax1, problem, [-lim, lim])
    c = plot_2D(ax2, problem, [-lim, lim])
    fig.subplots_adjust(right=0.8)
    cax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    colorbar_ = colorbar(c, cax=cax)
    colorbar_.ax.set_ylabel('Fitness')

class Animator(object):
    def __init__(self, min_fit=0, use_log_scale=False, **kwargs):
        #self.thread_lock = threading.Lock()
        self.queue = Queue()
        self.x_data, self.best_data, self.mean_data = [], [], []
        self.min_fit = min_fit
        #ion()
        self.fig = figure() 
        self.ax = self.fig.gca()
        self.ax.set_xlabel("Generation")
        self.ax.set_ylabel("Fitness value")
        if use_log_scale:
            self.ax.set_yscale('log')
        self.line, = self.ax.plot([], [], '.b')
        self.line2, = self.ax.plot([], [], '.k')
        self.title = self.ax.set_title("")
        legend([self.line, self.line2], ["Best fitness", "Mean fitness"])
        
        self.animation = FuncAnimation(self.fig, self.update, self.data_gen,
                                       blit=(sys.platform != "darwin"), 
                                       interval=10,repeat=False)
        draw()
        pause(0.00001)
    
    def stop(self):
        #self.queue.put(None)
        #draw()
        pause(0.00001)
     
    def data_gen(self):
        while True :
            if self.queue.empty() :
                yield None
            else :
                data = self.queue.get()
                if data is None :
                    return
                yield data 
           
    def update(self,data):
        if data is not None :      
            if len(data) is 2 :
                #scale figure
                (max_gens, mean_fit) = data
                self.ax.set_xlim(0, max_gens)
                self.ax.set_ylim(self.min_fit, mean_fit)
                self.ax.figure.canvas.draw()  
                pause(0.01)
            else :          
                (gen,best,mean) = data
                self.x_data.append(gen)
                self.best_data.append(best)
                self.mean_data.append(mean)         
                self.line.set_data(self.x_data, self.best_data)
                self.line2.set_data(self.x_data, self.mean_data) 
                self.title.set_text("Best: %4.4e, Mean: %4.4e" % (best, mean)) 

                if gen % 5 == 0 :
                    self.ax.relim()
                    self.ax.autoscale_view(False,True,True)
            
            self.ax.figure.canvas.draw()
            pause(0.00001)
    
        return (self.line, self.line2, self.title)
    
def plotting_observer(population, num_generations, num_evaluations, args):
    if isinstance(population[0].fitness, CombinedObjectives) :
        mean_fit = mean([guy.fitness.fitness for guy in population])
        best_fit = population[0].fitness.fitness
    else :
        mean_fit = mean([guy.fitness for guy in population])
        best_fit = population[0].fitness
    if num_generations == 0 :  
        # put in data to scale figure
        args["animator"].queue.put((args["max_generations"], mean_fit))    
    args["animator"].queue.put((num_generations,best_fit,mean_fit))
    draw()
    pause(0.0001)

"""
    multi-objective plotting utils
"""

def plot_multi_objective_1D(axis, problem, x_limits, objective) :
    dx = (x_limits[1] - x_limits[0])/200.0
    x = arange(x_limits[0], x_limits[1]+dx, dx)
    x = x.reshape(len(x),1)
    y = [f[objective] for f in problem.evaluator(x, None)]
    axis.plot(x,y,'-b')

def plot_multi_objective_2D(axis, problem, x_limits, objective) :
    dx = (x_limits[1] - x_limits[0])/50.0
    x = arange(x_limits[0], x_limits[1]+dx, dx)
    z = asarray( [problem.evaluator([[i,j] for i in x], None) 
                  for j in x])[:,:,objective]
                  
    return axis.contourf(x, x, z, 64, cmap=cm.hot_r)
    
def plot_results_multi_objective_1D(problem, individuals_1, fitnesses_1, 
                    individuals_2, fitnesses_2, title_1, title_2, 
                    num_objectives) :
    fig = figure()
    lim = None
    axes = []
    for objective in range(num_objectives) :
        ax1 = fig.add_subplot(num_objectives,2,2*objective+1)
        ax1.plot(individuals_1, [f[objective] for f in fitnesses_1], '.b', markersize=7)
        if lim is None :
            lim = max(map(abs,ax1.get_xlim()))
        else :
            lim = max([lim] + map(abs, ax1.get_xlim()))
    
        ax2 = fig.add_subplot(num_objectives,2,2*objective+2)
        ax2.plot(individuals_2, [f[objective] for f in fitnesses_2], '.b', markersize=7)
        lim = max([lim] + map(abs, ax2.get_xlim()))
        axes.append(ax1)
        axes.append(ax2)
        ax1.set_title(title_1)
        ax2.set_title(title_2)
        ax1.set_ylabel('Objective ' + str(objective + 1))
        ax2.set_ylabel('Objective ' + str(objective + 1))

    for i,ax in enumerate(axes):
        ax.set_xlim(-lim, lim)
        plot_multi_objective_1D(ax, problem, [-lim, lim], i/2)

def plot_results_multi_objective_2D(problem, individuals_1, individuals_2, 
                    title_1, title_2, num_objectives) :
    fig = figure()
    lim = None
    axes = []
    for objective in range(num_objectives) :
        ax1 = fig.add_subplot(num_objectives,2,2*objective+1, aspect='equal')
        ax1.plot(individuals_1[:,0], individuals_1[:,1], '.b', markersize=7)
        if lim is None :
            lim = max(map(abs,ax1.get_xlim()) + map(abs,ax1.get_ylim()))
        else :
            lim = max([lim] + 
                  map(abs,ax1.get_xlim()) + 
                  map(abs,ax1.get_ylim()))
    
        ax2 = fig.add_subplot(num_objectives,2,2*objective + 2, aspect='equal')
        ax2.plot(individuals_2[:,0], individuals_2[:,1], '.b', markersize=7)
        lim = max([lim] + 
                  map(abs,ax2.get_xlim()) + 
                  map(abs,ax2.get_ylim()))
        ax1.set_title(title_1)
        ax2.set_title(title_2)
        axes.append(ax1)
        axes.append(ax2)
    
    for i,ax in enumerate(axes):
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_xlabel('x0')
        ax.set_ylabel('x1')     
        ax.locator_params(nbins=5)
        objective = i/2
        c = plot_multi_objective_2D(ax, problem, [-lim, lim], objective)   
        if i % 2 == 0 :
            cax = fig.add_axes([0.85, (num_objectives - objective - 1) 
                                * (0.85/num_objectives) + 0.12, 
                                0.05, 0.6/num_objectives])
            colorbar_ = colorbar(c, cax=cax)
            colorbar_.ax.set_ylabel('Objective ' + str(objective + 1))
            
    fig.subplots_adjust(right=0.8)

class MultiObjectiveAnimator(object):
    def __init__(self, objective_1, objective_2, constraint_function=None):
        self.queue = Queue()
        #ion()
        self.fig = figure() 
        self.ax = self.fig.gca()
        self.ax.set_xlabel(objective_1)
        self.ax.set_ylabel(objective_2)
        self.dominated_line, = self.ax.plot([], [], '.k')
        self.non_dominated_line, = self.ax.plot([], [], '.r', markersize=10)
        if constraint_function is not None :
            self.violator_line, = self.ax.plot([], [], '.', color="gray")
        self.title = self.ax.set_title("Population")
        
        self.constraint_function = constraint_function
        
        self.animation = FuncAnimation(self.fig, self.update, self.data_gen,
                                       blit=(sys.platform != "darwin"),
                                       interval=10,repeat=False)
        draw()
        pause(0.00001)
    
    def stop(self):
        #self.queue.put(None)
        #draw()
        pause(0.00001)
     
    def data_gen(self):
        while True :
            if self.queue.empty() :
                yield None
            else :
                data = self.queue.get()
                if data is None :
                    return
                yield data 
           
    def update(self,data):
        if data is not None :   
            (gen, population) = data   
            self.title = self.ax.set_title("Population -- Generation " + 
                                           str(gen))
            non_dominated_x, non_dominated_y = [], []
            dominated_x, dominated_y = [], []
            violator_x, violator_y = [],[]
            
            for p in population :
                if (self.constraint_function is not None and
                        self.constraint_function(p.candidate) > 0) :                    
                    violator_x.append(p.fitness[0])
                    violator_y.append(p.fitness[1])
                else : 
                
                    dominated = False
                    for q in population:
                        if p < q :
                            dominated = True
                            break
                    if not dominated:
                        non_dominated_x.append(p.fitness[0])
                        non_dominated_y.append(p.fitness[1])
                    else :
                        dominated_x.append(p.fitness[0])
                        dominated_y.append(p.fitness[1])
            
            self.dominated_line.set_data(dominated_x,dominated_y)
            self.non_dominated_line.set_data(non_dominated_x,non_dominated_y)
            if self.constraint_function is not None :
                self.violator_line.set_data(violator_x, violator_y) 
           
            if gen % 5 == 0 :
                self.ax.relim()
                self.ax.autoscale_view(False,True,True)
            
            self.ax.figure.canvas.draw()
            pause(0.00001)
        
        if self.constraint_function is not None :               
            return (self.dominated_line, self.non_dominated_line, 
                    self.violator_line, self.title)
        
        return (self.dominated_line, self.non_dominated_line, self.title)

def multi_objective_plotting_observer(population, num_generations, 
                                     num_evaluations, args):
    args["animator"].queue.put((num_generations,population))
    draw()
    pause(0.0001)
