# backend/tests/test_routing_small.py
import pandas as pd
from backend.app.graph_loader import CampusGraph
from backend.app.routing import dijkstra_route

# tiny 3-node line graph: 1-2-3
nodes = pd.DataFrame([
{"node_id": 1, "lat": 0.0, "lon": 0.0},
{"node_id": 2, "lat": 0.0, "lon": 1.0},
{"node_id": 3, "lat": 0.0, "lon": 2.0},
])
edges = pd.DataFrame([
{"u":1,"v":2,"distance_m":100.0,"is_stairs":False,"is_covered_or_indoor":False,"surface_penalty":0.6},
{"u":2,"v":3,"distance_m":100.0,"is_stairs":False,"is_covered_or_indoor":True ,"surface_penalty":0.6},
])
meta = {"campus_key":"test"}
from scipy.spatial import cKDTree
import numpy as np

def test_routing_small():
	cg = CampusGraph("test", nodes, edges, meta, cKDTree(np.c_[nodes.lat, nodes.lon]), {1:0,2:1,3:2})
	path, debug, steps = dijkstra_route(cg, 1, 3, {"stairs":500,"outdoor":50,"surface":10}, False, True)
	assert path == [1,2,3]
	assert round(debug["total_distance_m"],1) == 200.0
	assert steps[0]["to_node"] == 2