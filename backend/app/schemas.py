from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class LatLon(BaseModel):
    lat: float
    lon: float

class LambdaWeights(BaseModel):
    stairs: float = 500.0
    outdoor: float = 50.0
    surface: float = 10.0

class Prefs(BaseModel):
    avoid_stairs: bool = False
    prefer_indoor: bool = False
    max_distance_m: Optional[float] = None
    lambda_: LambdaWeights = Field(default_factory=LambdaWeights, alias="lambda")

class RouteRequest(BaseModel):
    campus_key: str
    source: LatLon
    target: LatLon
    prefs: Prefs

class Step(BaseModel):
    from_node: int
    to_node: int
    distance_m: float
    notes: List[str] = []

class RouteTotals(BaseModel):
    distance_m: float
    stairs_edges: int
    indoor_share: float

class RouteResponse(BaseModel):
    route: Dict
    steps: List[Step]
    totals: RouteTotals
    meta: Dict