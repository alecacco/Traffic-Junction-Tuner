import TJSumoTools as TJS
import pandas as pd
import sys, os
import argparse
import pickle
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description="TJO - scenario runner")
parser.add_argument("-s","--scenario",type=str, help="Scenario file to reproduce", required=True)
parser.add_argument("-f","--folder",type=str, help="Folder where temporary route files and output files can be stored", required=True)
parser.add_argument("-r","--repetitions",type=int, help="Number of repetitions", required=True)
parser.add_argument("-j","--jobs",type=int, help="Number of jobs", required=True)
parser.add_argument("-o","--output",type=str, help="Output file name, located in $folder ", required=True)
parser.add_argument("-e","--end",type=int, help="Sumo end time, default 3600", default = 3600)
parser.add_argument("-rf","--route-frequencies",type=str, help="Route genration frequency, default is \"2\"", default = "2")
parser.add_argument("-d","--data-to-collect",type=str, help="Data to collect from simulations, default is \"arrived accidents teleported\"", default = "arrived accidents teleported")

args = parser.parse_args()

'''
SCENARIO = sys.argv[1]          #trento for basescenario, simfolder/specificindividualscenario for specific individual
FOLDER = sys.argv[2]            #"BASE"
REPETITIONS = int(sys.argv[3])  #20
JOBS = int(sys.argv[4])         #20
OUTPUT = sys.argv[5]            #FOLDER + "/basescenario.csv"
'''

SCENARIO = args.scenario
FOLDER = args.folder
REPETITIONS = args.repetitions
JOBS = args.jobs
OUTPUT = args.output
SUMOEND = args.end
ROUTEFREQS = args.route_frequencies.split(" ")
TOCOLLECT = args.data_to_collect.split(" ")

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

def normalize_fitness(fit,traffic_rate,rou):

    fitness = fit.copy()
    speednorm_coeff = 2.0
    teleport_coeff = 10.0

    normalize = lambda value,minv,maxv : float(value-minv)/float(maxv-minv)
    getroutes = lambda rou,tr:len(list(ET.parse(
        FOLDER+"/"+\
        "runrep_route"+str(rou)+\
        "_traffic"+str(tr)+\
        ".rou.xml"
        ).getroot()))

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
            dprint("Can't normalize %s"%(k))
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
    for tr in ROUTEFREQS:
        routegen = {
            "sumoScenario":SCENARIO,
            "prefix":"route",
            "sumoEnd":SUMOEND,
            "repetitionRate":tr,
            "output":FOLDER + "/runrep_route" #useless  #indeed
        }

        for i in range(REPETITIONS):
            routegen["output"] = FOLDER + "/runrep_route" + str(i) + "_traffic" + str(tr)
            TJS.generate_route(routegen)

        for i in range(REPETITIONS):
            sim_todo.append({
                "launch":"sumo",
                "sumoScenario":SCENARIO,
                "sumoRoutes": FOLDER + "/runrep_route" + str(i) + "_traffic" + str(tr),
                "sumoStepSize":1,
                "sumoPort":27910,
                "sumoAutoStart":True,
                "sumoEnd":3600,
                "sumoDelay":0,
                "dataCollection":True,
                "sumoOutput": False,
                "sumoSeed":42,
                "objectives": TOCOLLECT
            })

    results = TJS.execute_scenarios(sim_todo,JOBS,27910)
    grouped_results = {}
    normalized_results = {}

    subset = len(results)/len(ROUTEFREQS)
    for tr_i in range(len(ROUTEFREQS)):
        grouped_results[ROUTEFREQS[tr_i]] = results[subset*tr_i:subset*(tr_i+1)]
        normalized_results[ROUTEFREQS[tr_i]] = [
            normalize_fitness(
                results[subset*tr_i:subset*(tr_i+1)][r_i],
                tr_i,
                r_i
            ) for r_i in range(len(results[subset*tr_i:subset*(tr_i+1)]))
        ]

    """df = pd.DataFrame(
            [res.values() for res in results],
            ["rep"+str(i) for i in range(REPETITIONS)],
            results[0].keys()
    )

    df.to_csv(OUTPUT+".csv")
    """
    pickle_save1 = open(OUTPUT+".pkl", 'wb')
    pickle_save2 = open(OUTPUT+"_norm.pkl", 'wb')
    pickle.dump(grouped_results, pickle_save1)
    pickle.dump(normalized_results, pickle_save2)
    pickle_save1.close()
    pickle_save2.close()