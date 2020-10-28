import TJSumoTools as TJS
import pandas as pd
import sys, os
import argparse
import pickle
import xml.etree.ElementTree as ET
import random
import numpy as np
import copy

parser = argparse.ArgumentParser(description="TJO - scenario runner")
parser.add_argument("-s","--scenario",type=str, help="Scenario file to reproduce", required=True)
parser.add_argument("-f","--folder",type=str, help="Folder where temporary route files and output files can be stored", required=True)
parser.add_argument("-r","--repetitions",type=int, help="Number of routegen seed repetitions", required=True)
parser.add_argument("-rs","--seed-repetitions",type=int, help="Number of sim seed repetitions", required=True)
parser.add_argument("-j","--jobs",type=int, help="Number of jobs", required=True)
parser.add_argument("-o","--output",type=str, help="Output file name, located in $folder ", required=True)
parser.add_argument("-e","--end",type=int, help="Sumo end time, default 3600", default = 3600)
parser.add_argument("-rf","--route-frequencies",type=str, help="Route genration frequency, default is \"2\"", default = "2")
parser.add_argument("-d","--data-to-collect",type=str, help="Data to collect from simulations, default is \"MMarrived HHaccidents MMteleported\"", default = "arrived accidents teleported")
parser.add_argument("-em","--emission-models",type=str, help="Comma separated emission models with percentage", default = "PC_G_EU6:46.3,PC_D_EU6:44.4,zero:9.2")

args = parser.parse_args()

'''
SCENARIO = sys.argv[1]          #trento for basescenario, simfolder/specificindividualscenario for specific individual
FOLDER = sys.argv[2]            #"BASE"
REPETITIONS = int(sys.argv[3])  #20
JOBS = int(sys.argv[4])         #20
OUTPUT = sys.argv[5]            #FOLDER + "/basescenario.csv"
'''

EMISSION_MODEL_BASE = "HBEFA3"
SCENARIO = args.scenario
FOLDER = args.folder
REPETITIONS = args.repetitions
SIM_REPETITIONS = args.seed_repetitions
JOBS = args.jobs
OUTPUT = args.output
SUMOEND = args.end
ROUTEFREQS = args.route_frequencies.split(" ")
EM_MODELS = dict((emitem.split(":") for emitem in args.emission_models.split(",")))
TOCOLLECT = [o[2:] for o in args.data_to_collect.split(" ")]

def get_max_speed_limit(scenario):
    edgefile = ET.parse(scenario+".edg.xml").getroot()
    speeds = [
        float(edge.get("speed"))
        for edge in edgefile 
        if (
            edge.tag=="edge" and                        # exclude roundabouts and other types of edges
            edge.get("type").split(".")[0]=="highway"   # exclude railways, which are edges but speed is much higher
        )
    ]
    return max(speeds)

#def normalize_fitness(fit,traffic_rate,rou):
def normalize_fitness(fit,traffic_rate,rou,emissions):

    fitness = fit.copy()
    speednorm_coeff = 2.0
    teleport_coeff = 10.0

    normalize = lambda value,minv,maxv : float(value-minv)/float(maxv-minv)
    getroutes = lambda rou,tr:sum([
        len(list(ET.parse(
            FOLDER+"/"+\
            "runrep_route"+str(rou)+\
            "_traffic"+str(tr)+\
            "_emc"+str(em)+\
            ".rou.xml").getroot())) 
        for em in emissions])

    for k in fitness.keys():
        previous = fitness[k]*1
        maxv = -42
        if k=="accidents" or k=="arrived":
            maxv = getroutes(rou,ROUTEFREQS[traffic_rate])
            fitness[k] = normalize(fitness[k],0,maxv)
        elif k=="avg_speed":
            maxv = speednorm_coeff*get_max_speed_limit(SCENARIO)
            fitness[k] = normalize(fitness[k],0,maxv)
        elif k=="teleported":
            maxv = teleport_coeff*getroutes(rou,ROUTEFREQS[traffic_rate])
            fitness[k] = normalize(fitness[k],0,maxv)
        else:
            print("Can't normalize %s"%(k))
    return fitness


try:
    if not os.path.exists(SCENARIO+".net.xml"):
        raise Exception("Invalid scenario")
except:
    print("Invalid scenario. Inexistent .net.xml file")
else:
    if not os.path.isdir(FOLDER):
        os.mkdir(FOLDER)

    sim_todo = []
    routes_todo = []
    for tr in ROUTEFREQS:
        for em,em_perc in EM_MODELS.items():
            routegen = {
                "sumoScenario":SCENARIO,
                "prefix":"route"+em,
                "emissionClass" : EMISSION_MODEL_BASE+"/"+em,
                "sumoEnd":SUMOEND,
                "repetitionRate":float(tr)/(float(em_perc)/100),
                "output":FOLDER + "/runrep_route" #useless  #indeed
            }

            for i in range(REPETITIONS):
                routegen["output"] = FOLDER + "/runrep_route" + str(i) + "_traffic" + str(tr)+"_emc"+str(em) 
                #TJS.generate_route(routegen)
                routes_todo.append(copy.deepcopy(routegen))

        for i in range(REPETITIONS):
            for j in range(SIM_REPETITIONS):
                sim_todo.append({
                    "launch":"sumo",
                    "sumoScenario":SCENARIO,
                    "sumoRoutes" : [
                            FOLDER + "/runrep_route" + str(i) + "_traffic" + str(tr)+"_emc"+str(em) 
                            for em in EM_MODELS.keys()
                        ],
                    "sumoStepSize":1,
                    "sumoPort":28910,
                    "sumoAutoStart":True,
                    "sumoEnd":SUMOEND,
                    "sumoDelay":0,
                    "dataCollection":True,
                    "sumoOutput": False,
                    "sumoSeed":str(random.randint(0,99999)),
                    "objectives": TOCOLLECT
                })

    TJS.generate_routes(routes_todo,JOBS)
    results = TJS.execute_scenarios(sim_todo,JOBS,28910)
    grouped_results = {}
    normalized_results = {}
    seedproc_results = {}

    subset = len(results)/len(ROUTEFREQS)
    for tr_i in range(len(ROUTEFREQS)):
        grouped_results[ROUTEFREQS[tr_i]] = results[subset*tr_i:subset*(tr_i+1)]
        normalized_results[ROUTEFREQS[tr_i]] = [
            normalize_fitness(
                results[subset*tr_i:subset*(tr_i+1)][r_i],
                tr_i,
                r_i/SIM_REPETITIONS,
                EM_MODELS.keys()
            ) for r_i in range(len(results[subset*tr_i:subset*(tr_i+1)]))
        ]

        seedproc_tr = []
        for rep_i in range(REPETITIONS):
            seedproc_elem = {}
            for cobj in args.data_to_collect.split(" "):
                high = np.max 
                low = np.min
                method_repetitions = \
                    high if cobj[1]=="H" else\
                    low if cobj[1]=="L" else\
                    np.var if cobj[1]=="V" else\
                    np.mean #if cobj[1]=="M"
                
                seedproc_elem[cobj[2:]] = method_repetitions([
                    normalized_results[ROUTEFREQS[tr_i]][j][cobj[2:]]
                    for j in range(SIM_REPETITIONS*rep_i,SIM_REPETITIONS*(rep_i+1))
                ])
            seedproc_tr.append(seedproc_elem)

        seedproc_results[ROUTEFREQS[tr_i]] = seedproc_tr


    """df = pd.DataFrame(
            [res.values() for res in results],
            ["rep"+str(i) for i in range(REPETITIONS)],
            results[0].keys()
    )

    df.to_csv(OUTPUT+".csv")
    """
    pickle_save1 = open(OUTPUT+".pkl", 'wb')
    pickle_save2 = open(OUTPUT+"_norm.pkl", 'wb')
    pickle_save3 = open(OUTPUT+"_norm_seedproc.pkl", 'wb')
    pickle.dump(grouped_results, pickle_save1)
    pickle.dump(normalized_results, pickle_save2)
    pickle.dump(seedproc_results, pickle_save3)
    pickle_save1.close()
    pickle_save2.close()
    pickle_save3.close()
