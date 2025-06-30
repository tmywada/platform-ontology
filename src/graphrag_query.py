import json
import networkx as nx
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

# Example extra nodes (proto, yaml, orchestrator) - minimal for demo
G.add_node("Person", type="proto_message")
G.add_edge("compute", "Person", relation="uses_message")
G.add_node("database", type="yaml_key")
G.add_edge("compute", "database", relation="uses_config")

# --- Create embeddings ---
node_list, embeddings = create_node_embeddings(G)

# Build FAISS index
index = build_faiss_index(embeddings)

# --- User query ---
query_text = "Which functions use person information or database configuration?"

# Retrieve relevant nodes
expanded_nodes = query_graphrag(G, query_text, node_list, embeddings, index, top_k=3)

print("🔎 Relevant nodes and expanded context:")
for node in expanded_nodes:
    data = G.nodes[node]
    print(f"- {node}: {data.get('type', '')}")

# Example: Use these nodes as context in an LLM prompt
context = "\n".join([f"{node}: {G.nodes[node].get('type', '')}" for node in expanded_nodes])
print("\n--- Context to send to LLM ---\n")
print(context)
