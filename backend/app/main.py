# backend/app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Dict

from .schemas import RouteRequest, RouteResponse, RouteTotals
from .graph_loader import load_campus, CampusGraph
from .routing import dijkstra_route

app = FastAPI(title="Navigator API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data/graphs")
_cache: Dict[str, CampusGraph] = {}

def get_campus(campus_key: str) -> CampusGraph:
    if campus_key in _cache:
        return _cache[campus_key]
    prefix = DATA_DIR / campus_key
    nodes_ok = (prefix.with_suffix(".nodes.parquet")).exists()
    edges_ok = (prefix.with_suffix(".edges.parquet")).exists()
    if not (nodes_ok and edges_ok):
        raise HTTPException(status_code=404, detail=f"Campus graph not found for key '{campus_key}'")
    cg = load_campus(str(prefix), campus_key)
    _cache[campus_key] = cg
    return cg

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest):
    cg = get_campus(req.campus_key)
    try:
        src = cg.nearest_node(req.source.lat, req.source.lon)
        dst = cg.nearest_node(req.target.lat, req.target.lon)
        path_nodes, debug, steps = dijkstra_route(
            cg,
            src=src,
            dst=dst,
            lam={
                "stairs": req.prefs.lambda_.stairs,
                "outdoor": req.prefs.lambda_.outdoor,
                "surface": req.prefs.lambda_.surface,
            },
            avoid_stairs=req.prefs.avoid_stairs,
            prefer_indoor=req.prefs.prefer_indoor,
            max_distance_m=req.prefs.max_distance_m,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    nodes = cg.nodes_df.set_index("node_id")
    coords = [[float(nodes.loc[int(nid)]["lon"]), float(nodes.loc[int(nid)]["lat"])] for nid in path_nodes]

    totals = RouteTotals(
        distance_m=debug["total_distance_m"],
        stairs_edges=debug["stairs_edges"],
        indoor_share=debug["indoor_share"],
    )

    return {
        "route": {"type": "LineString", "coordinates": coords},
        "steps": steps,
        "totals": totals.dict(),
        "meta": {"campus": req.campus_key, **cg.meta},
    }
