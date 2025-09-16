#!/usr/bin/env python3
import argparse, json, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--prefix", required=True, help="e.g., data/graphs/mit")
args = ap.parse_args()

nodes = pd.read_parquet(args.prefix + ".nodes.parquet")
edges = pd.read_parquet(args.prefix + ".edges.parquet")
meta = json.load(open(args.prefix + ".meta.json"))

print("Meta:", json.dumps(meta, indent=2))
print("Nodes sample:", nodes.head())
print("Edges sample:", edges.head())

# Basic checks
assert nodes["lat"].between(-90, 90).all()
assert nodes["lon"].between(-180, 180).all()
assert (edges["distance_m"] >= 0).all()

stairs_share = edges["is_stairs"].mean()
covered_share = edges["is_covered_or_indoor"].mean()
print(f"Stairs share: {stairs_share:.3f}, Covered/Indoor share: {covered_share:.3f}")
print("OK")