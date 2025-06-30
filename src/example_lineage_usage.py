import json
import networkx as nx
import lineage_helpers as lh

# Load metadata
with open("metadata.json", "r") as f:
    metadata = json.load(f)

G = nx.DiGraph()

for node in metadata["nodes"]:
    G.add_node(node["name"], **node)

for edge in metadata["edges"]:
    G.add_edge(edge["source"], edge["target"], relation=edge["relation"])

# Add lineage edges
lh.add_lineage_edges(G)

# Show all "transforms_to" edges
transform_edges = lh.get_transforms_to_edges(G)
print("Transforms_to edges:")
for e in transform_edges:
    print(e)

# Example: Trace lineage paths from 'y'
start_var = "y"
paths = lh.get_lineage_paths(G, start_var)
print(f"Lineage paths starting from '{start_var}':")
for path in paths:
    print(" -> ".join(path))
