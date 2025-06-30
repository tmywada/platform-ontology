import streamlit as st
import json
import networkx as nx
import tempfile
from pyvis.network import Network
from graphrag_module import create_node_embeddings, build_faiss_index, query_graphrag
import streamlit.components.v1 as components
from collections import Counter
import pandas as pd

# ---------------------- Helper functions ----------------------

def get_node_color(ntype, is_pii=False):
    color = "gray"
    if ntype == "proto_message":
        color = "orange"
    elif ntype == "yaml_key":
        color = "green"
    elif ntype == "orchestrator":
        color = "purple"
    elif ntype == "function":
        color = "lightblue"
    if is_pii:
        color = "red"
    return color

def build_pyvis_graph(subG, include_types, include_pii):
    net = Network(height="600px", width="100%", directed=True, notebook=False)
    for node, data in subG.nodes(data=True):
        ntype = data.get("type", "")
        if not include_types.get(ntype, True):
            continue
        label = f"{node}\n({ntype})"
        color = get_node_color(ntype, include_pii and data.get("pii", False))
        net.add_node(node, label=label, title=str(data), color=color)

    for source, target, data in subG.edges(data=True):
        if source not in net.node_ids or target not in net.node_ids:
            continue
        net.add_edge(source, target, label=data.get("relation", ""))

    return net

# ---------------------- Load graph ----------------------

with open("metadata.json", "r") as f:
    py_metadata = json.load(f)

G = nx.DiGraph()

for node in py_metadata["nodes"]:
    G.add_node(node["name"], **node)

for edge in py_metadata["edges"]:
    G.add_edge(edge["source"], edge["target"], relation=edge["relation"])

# Example extra nodes
G.add_node("Person", type="proto_message")
G.add_edge("compute", "Person", relation="uses_message")
G.add_node("database", type="yaml_key")
G.add_edge("compute", "database", relation="uses_config")
G.add_node("my_pipeline.sh", type="orchestrator")
G.add_edge("my_pipeline.sh", "example.py", relation="calls_script")

# Embeddings
node_list, embeddings = create_node_embeddings(G)
index = build_faiss_index(embeddings)

# ---------------------- UI ----------------------

st.title("GraphRAG Interactive Subgraph Explorer")

query_text = st.text_input("Enter your query", "What functions interact with person data?")

st.sidebar.header("Node type filters")
include_types = {
    "function": st.sidebar.checkbox("Include functions", value=True),
    "proto_message": st.sidebar.checkbox("Include proto messages", value=True),
    "yaml_key": st.sidebar.checkbox("Include YAML keys", value=True),
    "orchestrator": st.sidebar.checkbox("Include orchestrators", value=True),
}
include_pii = st.sidebar.checkbox("Highlight PII nodes", value=True)

if st.button("Generate Subgraph"):
    expanded_nodes = query_graphrag(G, query_text, node_list, embeddings, index, top_k=3)
    subG = G.subgraph(expanded_nodes).copy()

    type_counts = Counter(data.get("type", "unknown") for _, data in subG.nodes(data=True))
    pii_count = sum(1 for _, data in subG.nodes(data=True) if data.get("pii"))

    node_degrees = [(n, subG.degree(n)) for n in subG.nodes()]
    top_nodes = sorted(node_degrees, key=lambda x: x[1], reverse=True)[:5]

    st.subheader("📊 Aggregate Subgraph Summary")
    st.markdown(f"- **Total nodes:** {len(subG.nodes)}")
    st.markdown(f"- **Functions:** {type_counts.get('function', 0)}")
    st.markdown(f"- **Proto messages:** {type_counts.get('proto_message', 0)}")
    st.markdown(f"- **YAML keys:** {type_counts.get('yaml_key', 0)}")
    st.markdown(f"- **Orchestrators:** {type_counts.get('orchestrator', 0)}")
    st.markdown(f"- **PII nodes:** {pii_count}")
    st.markdown(f"- **Total edges:** {len(subG.edges)}")

    with st.expander("🔎 Drill-down: Top connected nodes"):
        for node_name, deg in top_nodes:
            data = subG.nodes[node_name]
            st.markdown(f"**{node_name}** — Degree: {deg}")
            st.json(data)

    with st.expander("🔎 Drill-down: Edges"):
        for source, target, data in subG.edges(data=True):
            st.markdown(f"**{source} → {target}** — Relation: {data.get('relation', '')}")

    all_node_names = list(subG.nodes())
    selected_node = st.selectbox("Select a node to view details and export", [""] + all_node_names)
    if selected_node:
        st.subheader(f"🗂️ Node Details: {selected_node}")
        node_data = subG.nodes[selected_node]
        st.json(node_data)

        export_format = st.radio("Export format", ("JSON", "CSV"))
        if st.button("Download Node Data"):
            if export_format == "JSON":
                json_str = json.dumps(node_data, indent=2)
                st.download_button("Download JSON", json_str, file_name=f"{selected_node}_node.json")
            else:
                df = pd.DataFrame(list(node_data.items()), columns=["Key", "Value"])
                csv_str = df.to_csv(index=False)
                st.download_button("Download CSV", csv_str, file_name=f"{selected_node}_node.csv")

    net = build_pyvis_graph(subG, include_types, include_pii)

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    net.save_graph(tmp_file.name)

    with open(tmp_file.name, "r", encoding="utf-8") as f:
        html_content = f.read()
    components.html(html_content, height=650, scrolling=True)

    st.success("✅ Subgraph generated successfully!")
