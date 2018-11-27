#!/usr/bin/env python

import xml.etree.ElementTree as ET
import sys, os

#custom exception for parameter errors and invalid files
class IllegalArgumentError(Exception):
        def __init__(self,message):
            print("\n\n*********************************************************************")
            print("USAGE: .\\routeRemover.py routefile accepted_edge1 accepted_edge2 ...")
            if message!="":
                print("Invalid file "+ message)
            print("*********************************************************************\n\n")

#must have some parameter
if len(sys.argv)<2:
    raise IllegalArgumentError("")
#second argument should be an existing file
elif sys.argv[1] not in os.listdir('.'):
    raise IllegalArgumentError(sys.argv[1])

#source routes file
routefile = sys.argv[1]

#allowed edges are all the rest of the arguments
allowed = sys.argv[2:]

#invalid xml file management
try:
    t = ET.parse(routefile)
except ET.ParseError:
    print("Invalid route file!")
    raise IllegalArgumentError(routefile)

r = t.getroot()
vehicles = list(r)

edges_to_keep = 0
edges_to_remove = 0

for v in vehicles:
    route = list(v)[0]
    if route.get("edges").split()[0] not in allowed: # or route.get("edges")[-1] not in allowed:
        r.remove(v)
        edges_to_remove+=1
    else:
        edges_to_keep+=1

#unique filename management
i = 0
while ("ref"+str(i)+"_"+ routefile in os.listdir(".")):
        i += 1

t.write("ref"+str(i)+"_"+routefile)

print("keep/remove ratio: "+str(edges_to_keep)+"/"+str(edges_to_remove))

