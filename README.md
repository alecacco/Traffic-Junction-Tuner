# Traffic-Junction-Tuner
Alessandro Cacco & Andrea Ferigo Bio Inspired Artificial Intelligence project - AA 2018/19

## TJTuner.py
This is the main tool, it manages the custom inspyred implementation of NSGA-II. It makes use of several libraries included in the repo.
It has many configuration options:
  - number of generations to develop
  - launch, the command line name of the simulation program to use (either sumo or sumo-gui, ususally)
  - port for connecting to sumo via TraCI: must be the same as the one in *scenario*.sumo.cfg
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
This is the analysis tool, it loads "population" files from the specified folder (which should be a TJTuner.py result folder). 
It allows to:
  - plot the results of the genetic algorithm throughout generations.
  - print a nice table of all individuals of a specific generation
  - re-simulate a specific individual of a specific generation (without data-collecting) in sumo-gui

## TJSumoTools.py
This library allows both TJTuner and TJAnalyzer to instantiate sumo simulations with no repeating code, basically. It also allow buiilding traffic light programs and generating the map to simulate based on a given individual.

## Other stuff
  - Scenario files
  - example of (good) results
  - EA libraries (made by prof Giovanni Iacca)
  - other routes file for trento, can be configured in trento.sumo.cfg
  - routeRemover.py, a clean-up tools to remove routes from a *.rou.xml file, leaving only long routes from (and to) the map limit
  - a bad .gitignore
  - project presentation slides
