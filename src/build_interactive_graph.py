import json
import networkx as nx
from pyvis.network import Network
import proto_parser as pp
import yaml_parser as yp
import pii_observer as po

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
G.add_edge("compute", "Person", relation="uses_message")
G.add_edge("compute", "database", relation="uses_config")

# --- Mark PII nodes ---
po.mark_pii_nodes(G)

# Build Pyvis network
net = Network(height="800px", width="100%", directed=True, notebook=False)

for node, data in G.nodes(data=True):
    label = f"{node}\n({data.get('type', '')})"
    color = "lightblue"
    if data.get("pii"):
        color = "red"
        pii_info = ", ".join(data.get("pii_entities", []))
        tooltip = f"PII Detected: {pii_info}" if pii_info else "PII Detected"
    else:
        pii_info = ""
        tooltip = str(data)

    if data.get("type") == "proto_message":
        color = "orange"
    elif data.get("type") == "yaml_key":
        color = "green"
    elif data.get("type") == "orchestrator":
        color = "purple"

    net.add_node(node, label=label, title=tooltip, color=color)

for source, target, data in G.edges(data=True):
    net.add_edge(source, target, label=data.get("relation", ""))

net.show("unified_graph_pii_tooltips.html")
print("Interactive HTML graph with PII tooltips saved as unified_graph_pii_tooltips.html")
