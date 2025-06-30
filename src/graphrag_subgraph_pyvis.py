import json
import networkx as nx
from pyvis.network import Network
from graphrag_module import create_node_embeddings, build_faiss_index, query_graphrag

# Load Python metadata
with open("metadata.json", "r") as f:
    py_metadata = json.load(f)

G = nx.DiGraph()

# Add Python nodes and edges
for node in py_metadata["nodes"]:
    G.add_node(node["name"], **node)

for edge in py_metadata["edges"]:
    G.add_edge(edge["source"], edge["target"], relation=edge["relation"])

# Example extra nodes (proto, yaml, orchestrator)
G.add_node("Person", type="proto_message")
G.add_edge("compute", "Person", relation="uses_message")
G.add_node("database", type="yaml_key")
G.add_edge("compute", "database", relation="uses_config")
G.add_node("my_pipeline.sh", type="orchestrator")
G.add_edge("my_pipeline.sh", "example.py", relation="calls_script")

# Create embeddings
node_list, embeddings = create_node_embeddings(G)

# Build FAISS index
index = build_faiss_index(embeddings)

# User query
query_text = "What functions interact with person data and database config?"

expanded_nodes = query_graphrag(G, query_text, node_list, embeddings, index, top_k=3)

# Build subgraph
subG = G.subgraph(expanded_nodes).copy()

# Create Pyvis network
net = Network(height="800px", width="100%", directed=True, notebook=False)

for node, data in subG.nodes(data=True):
    label = f"{node}\n({data.get('type', '')})"
    color = "gray"
    if data.get("type") == "proto_message":
        color = "orange"
    elif data.get("type") == "yaml_key":
        color = "green"
    elif data.get("type") == "orchestrator":
        color = "purple"
    elif data.get("type") == "function":
        color = "lightblue"
    elif data.get("pii"):
        color = "red"
    net.add_node(node, label=label, title=str(data), color=color)

for source, target, data in subG.edges(data=True):
    net.add_edge(source, target, label=data.get("relation", ""))

net.show("subgraph_interactive.html")
print("✅ Interactive subgraph visualization saved as subgraph_interactive.html")
