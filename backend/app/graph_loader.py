# backend/app/graph_loader.py
import json
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any
try:
    from scipy.spatial import cKDTree  # fast path
except Exception:  # fallback if SciPy wheels not present on py3.13
    cKDTree = None
    from sklearn.neighbors import KDTree as SKKDTree  # type: ignore

@dataclass
class CampusGraph:
    key: str
    nodes_df: pd.DataFrame
    edges_df: pd.DataFrame
    meta: Dict[str, Any]
    # store either cKDTree or sklearn KDTree in one attribute
    kdtree: Any
    node_index: Dict[int, int]  # node_id -> row index in nodes_df

    def nearest_node(self, lat: float, lon: float) -> int:
        if cKDTree is not None and isinstance(self.kdtree, cKDTree):
            dist, idx = self.kdtree.query([lat, lon], k=1)
            return int(self.nodes_df.iloc[idx]["node_id"])
        # sklearn KDTree expects [lat, lon] and returns (dist, ind)
        dist, ind = self.kdtree.query([[lat, lon]], k=1)
        idx = int(ind[0][0])
        return int(self.nodes_df.iloc[idx]["node_id"])

def load_campus(prefix: str, key: str) -> CampusGraph:
    nodes = pd.read_parquet(prefix + ".nodes.parquet")
    edges = pd.read_parquet(prefix + ".edges.parquet")
    meta = json.load(open(prefix + ".meta.json"))

    # KDTree on (lat, lon)
    pts = np.c_[nodes["lat"].to_numpy(), nodes["lon"].to_numpy()]
    if cKDTree is not None:
        kdtree = cKDTree(pts)
    else:
        kdtree = SKKDTree(pts, leaf_size=40)

    node_index = {int(nid): i for i, nid in enumerate(nodes["node_id"].astype(int).to_numpy())}
    return CampusGraph(key=key, nodes_df=nodes, edges_df=edges, meta=meta, kdtree=kdtree, node_index=node_index)
