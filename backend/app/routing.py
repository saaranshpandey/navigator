import heapq
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd

from .graph_loader import CampusGraph

# Cost model helpers

def edge_cost(row: pd.Series, lam: Dict[str, float], avoid_stairs: bool, prefer_indoor: bool) -> float:
    # Base distance
    cost = float(row["distance_m"]) # meters

    # Stairs
    if bool(row["is_stairs"]):
        if avoid_stairs:
            return float("inf") # hard block
        cost += lam.get("stairs", 500.0)

    # Outdoor penalty (prefer indoor/covered)
    if prefer_indoor:
        if not bool(row["is_covered_or_indoor"]):
            cost += lam.get("outdoor", 50.0)

    # Surface penalty
    cost += lam.get("surface", 10.0) * float(row.get("surface_penalty", 0.6))

    return cost

def build_adjacency(edges_df: pd.DataFrame) -> Dict[int, List[Tuple[int, int]]]:
# adjacency: u -> list of (row_index, v)
    adj: Dict[int, List[Tuple[int, int]]] = {}
    for i, r in edges_df.iterrows():
        u = int(r["u"]); v = int(r["v"]) # node ids
        adj.setdefault(u, []).append((i, v))
    
    return adj

def dijkstra_route(cg: CampusGraph, src: int, dst: int, lam: Dict[str, float], avoid_stairs: bool, prefer_indoor: bool, max_distance_m: Optional[float]=None) -> Tuple[List[int], Dict[str, float]]:
    edges = cg.edges_df
    adj = build_adjacency(edges)

    INF = float("inf")
    dist: Dict[int, float] = {}
    prev_edge_row: Dict[int, int] = {}

    pq: List[Tuple[float, int]] = []
    dist[src] = 0.0
    heapq.heappush(pq, (0.0, src))

    while pq:
        d, u = heapq.heappop(pq)
        if u == dst:
            break
        if d != dist.get(u, INF):
            continue
        for row_idx, v in adj.get(u, []):
            row = edges.iloc[row_idx]
            w = edge_cost(row, lam, avoid_stairs, prefer_indoor)
            if not np.isfinite(w):
                continue
            nd = d + w
            if max_distance_m is not None and nd > max_distance_m * 3: # generous cap (cost>distance)
                continue
            if nd < dist.get(v, INF):
                dist[v] = nd
                prev_edge_row[v] = row_idx
                heapq.heappush(pq, (nd, v))

    if dst not in dist:
        raise ValueError("No feasible route found with given preferences")
    
    # Reconstruct path of node_ids
    path_nodes: List[int] = [dst]
    cur = dst
    while cur != src:
        row_idx = prev_edge_row[cur]
        u = int(edges.iloc[row_idx]["u"]) # previous node
        path_nodes.append(u)
        cur = u

    path_nodes.reverse()

    # Compute diagnostics
    path_rows = []
    stairs_edges = 0
    covered_edges = 0
    total_dist = 0.0

    # Collect steps & stats
    steps = []

    for i in range(len(path_nodes)-1):
        u = path_nodes[i]; v = path_nodes[i+1]
        # find the specific edge row from u->v (choose smallest distance if multiedges)
        rows = cg.edges_df[(cg.edges_df["u"]==u) & (cg.edges_df["v"]==v)]
        row = rows.iloc[rows["distance_m"].argmin()]
        total_dist += float(row["distance_m"]) # actual distance, not penalized
        if bool(row["is_stairs"]):
            stairs_edges += 1
        if bool(row["is_covered_or_indoor"]):
            covered_edges += 1
        notes = []
        if bool(row["is_stairs"]):
            notes.append("stairs")
        if bool(row["is_covered_or_indoor"]):
            notes.append("indoor_or_covered")
        steps.append({
        "from_node": int(u),
        "to_node": int(v),
        "distance_m": float(row["distance_m"]),
        "notes": notes,
        })

    indoor_share = covered_edges / max(1, (len(path_nodes)-1))
    debug = {
        "total_distance_m": total_dist,
        "stairs_edges": stairs_edges,
        "indoor_share": indoor_share,
    }
    return path_nodes, debug, steps
