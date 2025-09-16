import pandas as pd

edges = pd.read_parquet("/Users/saaranshpandey/Documents/PostMS_2025/misc/Nav/navigator/data/graphs/upenn.edges.parquet")

# See distinct surface values
print(edges["surface"].dropna().unique())

# Or count frequencies
print(edges["surface"].value_counts(dropna=False))

# Check distinct highway types too
print(edges["tags"].apply(lambda x: eval(x).get("highway")).value_counts())