#!/usr/bin/env python3
import argparse, json, sys, time, math, pathlib
from dataclasses import dataclass
from typing import Dict, Any, Tuple

import networkx as nx
import osmnx as ox
from shapely.geometry import Point
from shapely.ops import transform as shp_transform
from pyproj import Transformer
import pandas as pd

ox.settings.use_cache = True
ox.settings.log_console = True

@dataclass
class Campus:
    key: str
    name: str
    lat: float
    lon: float
    radius_m: int

# Build a geodesic buffer (meters) around lat/lon → polygon in WGS84
def circle_polygon(lat: float, lon: float, radius_m: float, num_pts: int = 64):
    # project to local UTM for accurate meters buffer
    transformer_to = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    transformer_back = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    p_m = Point(*transformer_to.transform(lon, lat))
    poly_m = p_m.buffer(radius_m, resolution=num_pts)

    def back(x, y, z=None):
        lon2, lat2 = transformer_back.transform(x, y)
        return (lon2, lat2)

    poly_deg = shp_transform(lambda x, y, z=None: back(x, y), poly_m)
    return poly_deg

# Map OSM edge tags → our attributes
# Replace your surface penalty logic with this:
SURFACE_PENALTY = {
    "asphalt": 0.0, "paved": 0.0, "concrete": 0.0,
    "paving_stones": 0.5, "compacted": 0.6, "gravel": 1.0,
    "fine_gravel": 0.8, "ground": 1.2, "dirt": 1.3,
    "grass": 1.4, "sand": 1.6,
}
DEFAULT_SURFACE_PENALTY = 0.6  # <- was effectively 0.0 before

EDGE_KEEP_KEYS = [
                "highway", "surface", "indoor", "covered", "lit", "wheelchair", "step_count"
                ]

# Decide if edge is stairs
def is_stairs(tags: Dict[str, Any]) -> bool:
    hwy = tags.get("highway")
    if hwy == "steps":
        return True
    # Some maps may tag stairs via other flags; expand if needed
    return False

# Is edge indoor/covered
def is_covered_or_indoor(tags: Dict[str, Any]) -> bool:
    
    covered = str(tags.get("covered", "no")).lower()
    indoor  = str(tags.get("indoor", "no")).lower()
    arcade  = tags.get("highway") == "footway" and str(tags.get("arcade", "no")).lower() in {"yes","true","1"}
    tunnel  = str(tags.get("tunnel", "no")).lower() in {"yes","true","1"}
    return (covered in {"yes","true","1"}) or (indoor in {"yes","true","1"}) or arcade or tunnel

    return# str(tags.get("covered", "no")).lower() in {"yes", "true", "1"} or str(tags.get("indoor", "no")).lower() in {"yes", "true", "1"}

# Compute surface penalty scalar
def surface_penalty(tags: Dict[str, Any]) -> float:
    surf = tags.get("surface")
    return float(SURFACE_PENALTY.get(surf, 0.8)) # unknowns mildly penalized

# Extract a walkable MultiDiGraph from OSM, clipped to polygon
def build_osm_graph(poly, simplify: bool = True) -> nx.MultiDiGraph:
    # network_type='walk' grabs footways/paths/pedestrian
    G = ox.graph_from_polygon(poly, network_type="walk", simplify=simplify)
    # Edge lengths are already included in recent osmnx versions
    return G

# Convert to a clean DiGraph with minimal attributes we care about
def normalize_graph(G: nx.MultiDiGraph) -> Tuple[pd.DataFrame, pd.DataFrame]:
    nodes = []
    for nid, data in G.nodes(data=True):
        nodes.append({
        "node_id": nid,
        "lat": data.get("y"),
        "lon": data.get("x"),
        })
    nodes_df = pd.DataFrame(nodes)

    edges = []
    for u, v, k, data in G.edges(keys=True, data=True):
        tags = {k: data.get(k) for k in EDGE_KEEP_KEYS if k in data}
        edges.append({
        "u": u,
        "v": v,
        "key": k,
        "distance_m": float(data.get("length", 0.0)),
        "is_stairs": is_stairs(data),
        "is_covered_or_indoor": is_covered_or_indoor(data),
        "surface": data.get("surface"),
        "surface_penalty": surface_penalty(data),
        "tags": json.dumps(tags, ensure_ascii=False),
        })
    edges_df = pd.DataFrame(edges)
    return nodes_df, edges_df

# Persist artifacts
def save_artifacts(nodes_df: pd.DataFrame, edges_df: pd.DataFrame, meta: Dict[str, Any], out_prefix: pathlib.Path):
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    nodes_path = out_prefix.with_suffix(".nodes.parquet")
    edges_path = out_prefix.with_suffix(".edges.parquet")
    meta_path = out_prefix.with_suffix(".meta.json")

    nodes_df.to_parquet(nodes_path, index=False)
    edges_df.to_parquet(edges_path, index=False)
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    
def main():
    ap = argparse.ArgumentParser(description="Build campus walk graph from OSM")
    ap.add_argument("--campuses", required=True, help="path to campuses.json")
    ap.add_argument("--key", required=True, help="campus key (e.g., mit|upenn|uh)")
    ap.add_argument("--out", required=True, help="output prefix, e.g., data/graphs/mit")
    ap.add_argument("--radius_m", type=int, default=None, help="override radius in meters")
    args = ap.parse_args()

    campuses = json.load(open(args.campuses))
    if args.key not in campuses:
        print(f"Unknown campus key: {args.key}. Choices: {list(campuses.keys())}")
        sys.exit(2)

    c = campuses[args.key]
    radius = args.radius_m or c["radius_m"]

    print(f"Building graph for {c['name']} with radius {radius} m ...")
    poly = circle_polygon(c["lat"], c["lon"], radius)

    t0 = time.time()
    G = build_osm_graph(poly)
    nodes_df, edges_df = normalize_graph(G)
    dt = time.time() - t0

    meta = {
    "campus_key": args.key,
    "campus_name": c["name"],
    "center": {"lat": c["lat"], "lon": c["lon"]},
    "radius_m": radius,
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "counts": {"nodes": int(len(nodes_df)), "edges": int(len(edges_df))},
    "notes": {
    "source": "OpenStreetMap via OSMnx",
    "attribution": "© OpenStreetMap contributors",
    }
    }

    print(f"Nodes: {len(nodes_df):,}, Edges: {len(edges_df):,} (built in {dt:.1f}s)")
    out_prefix = pathlib.Path(args.out)
    save_artifacts(nodes_df, edges_df, meta, out_prefix)

if __name__ == "__main__":
    main()  

