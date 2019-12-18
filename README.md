# Traffic-Junction-Tuner
Originally Alessandro Cacco & Andrea Ferigo Bio Inspired Artificial Intelligence project for AA 2018/19 Giovanni Iacca's course.
Later evolved in the Traffic Junction Tuner project, developed by Alessandro Cacco and tutored by Giovanni Iacca.
Evolve a road scenario and improve the traffic lights configurations by means of genetic algorithms, using as fitness function the evaluation of custom objective expression on simulation results. The simulation are run with synthetic traffic, generated multiple times with different traffic densities to mimic a realistic road behavior.

## TJTuner.py
This is the main tool, it manages the custom inspyred implementation of NSGA-II. It makes use of several libraries included in the repo.
It has many configuration options:
  - number of generations to evolve
  - objectives in RPN syntax (see paper for more information)
  - traffic rates, used for the generation of synthetic traffic (see paper for more information
  - launch, the command line name of the simulation program to use (either sumo or sumo-gui)
  - port for connecting to sumo via TraCI, if multicore is enabled then this indicates the starting port.
  - scenario, the scenario sumo should load (e.g. "trento" if scenario files are trento.***.xml)
  - autostart of the simulation, can be disabled e.g. for demos
  - duration of the simulation (*end* parameter)
  - step-delay for gui visualization, in order to be able to see the simulation in sumo-gui
  - debugging "prints", can be shown or hidden
  - simulation hang, which stops the program before it connects to the first individual's simulation (useful to debug a simulation via an external traci manual connection)
  - sumo and netconvert output (netconvert is a sumo tool to build the scenario)
  - EA parameters:
    - mutation rate
    - crossover rate
    - offspring size
    - population size
    - traffic lights timing boundaries
TJTuner.py --help should sum all these up.

## TJAnalyzer.py 
This is the analysis tool, it loads "population" and "results_storage" files from the specified folder (which should be a TJTuner.py result folder). 
It allows to:
  - plot the results of the genetic algorithm throughout generations, in form of
    - matrix plot
    - boxplot
    - parallel coordinates plot
  - print a nice table of all individuals of a specific generation
  - re-simulate a specific individual of a specific generation (without data-collecting) in sumo-gui (only in old versions have yet to be reimplemented for the latest)

## plotting_lib.py
Auxiliary plotting library for TJA

## TJSumoTools.py
This library allows both TJTuner and TJAnalyzer to instantiate sumo simulations with no repeating code, basically. It also allow buiilding traffic light programs and generating the map to simulate based on a given individual.

## experiments_plots
Folder containing all the plots of the experiments we run for the paper.

## Other stuff
  - Scenario files, for Trento and Milan
  - EA libraries (made by prof Giovanni Iacca)
  - original course project presentation slides
