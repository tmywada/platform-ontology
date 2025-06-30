import json
import networkx as nx
import matplotlib.pyplot as plt
import proto_parser as pp
import yaml_parser as yp

# Load Python metadata
with open("metadata.json", "r") as f:
    py_metadata = json.load(f)

G = nx.DiGraph()

# Add Python nodes and edges
for node in py_metadata["nodes"]:
    G.add_node(node["name"], **node)

for edge in py_metadata["edges"]:
    G.add_edge(edge["source"], edge["target"], relation=edge["relation"])

# --- Add proto metadata ---
proto_metadata = pp.parse_proto_file("example.proto")
pp.add_proto_to_graph(G, proto_metadata, proto_file_name="example.proto")

# --- Add YAML metadata ---
yaml_metadata = yp.parse_yaml_file("example.yaml")
yp.add_yaml_to_graph(G, yaml_metadata, yaml_file_name="example.yaml")

# --- Add orchestrator (bash) example ---
G.add_node("my_pipeline.sh", type="orchestrator", file_type="bash")
G.add_edge("my_pipeline.sh", "example.py", relation="calls_script")

# --- Example cross-reference edges ---
# Suppose 'compute' function uses 'Person' proto message
G.add_edge("compute", "Person", relation="uses_message")

# Suppose 'compute' function uses 'database' YAML key
G.add_edge("compute", "database", relation="uses_config")

# Visualize unified graph
pos = nx.spring_layout(G, seed=42)
edge_labels = nx.get_edge_attributes(G, "relation")

nx.draw(G, pos, with_labels=True, node_size=2000, node_color="lightblue", font_size=8)
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="red")
plt.show()
