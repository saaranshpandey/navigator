# backend/tests/test_routing_small.py
import numpy as np
import pandas as pd
import pytest
from scipy.spatial import cKDTree

from backend.app.graph_loader import CampusGraph
from backend.app.routing import dijkstra_route


def _graph(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> CampusGraph:
    meta = {"campus_key": "test"}
    coords = np.c_[nodes_df["lat"], nodes_df["lon"]]
    kdtree = cKDTree(coords)
    node_index = {int(row.node_id): idx for idx, row in nodes_df.reset_index(drop=True).iterrows()}
    return CampusGraph("test", nodes_df, edges_df, meta, kdtree, node_index)


def test_routing_small_line_graph():
    nodes = pd.DataFrame([
        {"node_id": 1, "lat": 0.0, "lon": 0.0},
        {"node_id": 2, "lat": 0.0, "lon": 1.0},
        {"node_id": 3, "lat": 0.0, "lon": 2.0},
    ])
    edges = pd.DataFrame([
        {"u": 1, "v": 2, "distance_m": 100.0, "is_stairs": False, "is_covered_or_indoor": False, "surface_penalty": 0.6},
        {"u": 2, "v": 3, "distance_m": 100.0, "is_stairs": False, "is_covered_or_indoor": True, "surface_penalty": 0.6},
    ])
    cg = _graph(nodes, edges)

    path, debug, steps = dijkstra_route(cg, 1, 3, {"stairs": 500, "outdoor": 50, "surface": 10}, False, True)

    assert path == [1, 2, 3]
    assert debug["total_distance_m"] == pytest.approx(200.0)
    assert steps[0]["to_node"] == 2


def test_prefers_lower_penalty_edge_when_parallel_edges_exist():
    nodes = pd.DataFrame([
        {"node_id": 1, "lat": 0.0, "lon": 0.0},
        {"node_id": 2, "lat": 0.0, "lon": 1.0},
    ])
    edges = pd.DataFrame([
        {"u": 1, "v": 2, "distance_m": 50.0, "is_stairs": True, "is_covered_or_indoor": False, "surface_penalty": 0.6},
        {"u": 1, "v": 2, "distance_m": 60.0, "is_stairs": False, "is_covered_or_indoor": True, "surface_penalty": 0.6},
    ])
    cg = _graph(nodes, edges)

    path, debug, steps = dijkstra_route(cg, 1, 2, {"stairs": 500, "outdoor": 50, "surface": 10}, False, True)

    assert path == [1, 2]
    assert debug["total_distance_m"] == pytest.approx(60.0)
    assert steps == [
        {
            "from_node": 1,
            "to_node": 2,
            "distance_m": pytest.approx(60.0),
            "notes": ["indoor_or_covered"],
        }
    ]


def test_avoids_stairs_when_requested():
    nodes = pd.DataFrame([
        {"node_id": 1, "lat": 0.0, "lon": 0.0},
        {"node_id": 2, "lat": 0.0, "lon": 1.0},
    ])
    edges = pd.DataFrame([
        {"u": 1, "v": 2, "distance_m": 40.0, "is_stairs": True, "is_covered_or_indoor": False, "surface_penalty": 0.6},
    ])
    cg = _graph(nodes, edges)

    with pytest.raises(ValueError):
        dijkstra_route(cg, 1, 2, {"stairs": 500, "outdoor": 50, "surface": 10}, True, False)


def test_distance_cap_applies_to_physical_distance_only():
    nodes = pd.DataFrame([
        {"node_id": 1, "lat": 0.0, "lon": 0.0},
        {"node_id": 2, "lat": 0.0, "lon": 1.0},
        {"node_id": 3, "lat": 0.0, "lon": 2.0},
    ])
    edges = pd.DataFrame([
        {"u": 1, "v": 2, "distance_m": 120.0, "is_stairs": False, "is_covered_or_indoor": False, "surface_penalty": 1.5},
        {"u": 2, "v": 3, "distance_m": 120.0, "is_stairs": False, "is_covered_or_indoor": False, "surface_penalty": 1.5},
    ])
    cg = _graph(nodes, edges)

    lam = {"stairs": 500, "outdoor": 50, "surface": 10}
    # Each edge has distance 120m, but the penalties push the cost well above the max.
    path, debug, _ = dijkstra_route(cg, 1, 3, lam, False, True, max_distance_m=300.0)
    assert path == [1, 2, 3]
    assert debug["total_distance_m"] == pytest.approx(240.0)

    with pytest.raises(ValueError):
        dijkstra_route(cg, 1, 3, lam, False, True, max_distance_m=200.0)
