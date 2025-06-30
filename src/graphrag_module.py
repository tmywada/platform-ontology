from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import networkx as nx

def create_node_embeddings(G, model_name="all-MiniLM-L6-v2"):
    """
    Create embeddings for each node in the graph using a SentenceTransformer model.
    Returns: node list, embeddings array
    """
    model = SentenceTransformer(model_name)
    node_texts = []
    node_list = []

    for node, data in G.nodes(data=True):
        desc = f"{node} ({data.get('type', '')})"
        extra = data.get("defined_in", "") or data.get("value_repr", "")
        desc = desc + " " + extra
        node_texts.append(desc)
        node_list.append(node)

    embeddings = model.encode(node_texts, convert_to_numpy=True)
    return node_list, embeddings

def build_faiss_index(embeddings):
    """
    Builds a FAISS index for the given embeddings.
    """
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return index

def query_graphrag(G, query, node_list, embeddings, index, top_k=3, model_name="all-MiniLM-L6-v2"):
    """
    Query graph nodes via vector similarity and expand with graph traversal.
    """
    model = SentenceTransformer(model_name)
    query_emb = model.encode([query], convert_to_numpy=True)

    _, indices = index.search(query_emb, top_k)
    relevant_nodes = [node_list[i] for i in indices[0]]

    # Expand by graph traversal
    expanded_nodes = set(relevant_nodes)
    for node in relevant_nodes:
        expanded_nodes.update(nx.descendants(G, node))
        expanded_nodes.update(nx.ancestors(G, node))

    return expanded_nodes
