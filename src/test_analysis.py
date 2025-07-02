import os
import json
import networkx as nx

# --- Import the necessary functions from your existing scripts ---
# Ensure that extract_metadata_python.py and generate_graph.py are in the same
# directory or accessible via PYTHONPATH.
from extract_metadata_python import generate_metadata
from generate_graph import create_graph_from_metadata

# ==============================================================================
# LINEAGE ANALYSIS FUNCTIONS
# ==============================================================================

def find_node_by_label(graph: nx.DiGraph, node_label: str) -> str | None:
    """
    Finds the first node in the graph that matches a given label.

    :param graph: The NetworkX DiGraph to search within.
    :param node_label: The 'label' of the node to find (e.g., a function name).
    :return: The unique ID of the found node, or None if not found.
    """
    for node, data in graph.nodes(data=True):
        if data.get('label') == node_label:
            return node
    print(f"Warning: Node with label '{node_label}' not found.")
    return None

def get_structural_lineage(graph: nx.DiGraph, node_id: str) -> list[str]:
    """
    Traces the structural lineage of a node up to the root folder.
    This shows where a code object is defined.

    :param graph: The NetworkX DiGraph.
    :param node_id: The starting node's unique ID.
    :return: A list of labels representing the path from the node to the root.
    """
    if not graph.has_node(node_id):
        return [f"Node '{node_id}' not in graph."]
    
    path = []
    current_node = node_id
    
    # Traverse backwards along 'contains' edges
    while current_node:
        path.append(graph.nodes[current_node].get('label', current_node))
        
        # Find the predecessor connected by a 'contains' edge
        predecessors = graph.predecessors(current_node)
        parent_node = None
        for p_node in predecessors:
            if graph.get_edge_data(p_node, current_node).get('type') == 'contains':
                parent_node = p_node
                break
        current_node = parent_node
        
    return list(reversed(path))

def get_downstream_dependencies(graph: nx.DiGraph, node_id: str) -> dict:
    """
    Finds all nodes that the given node directly depends on (outgoing edges).

    :param graph: The NetworkX DiGraph.
    :param node_id: The starting node's unique ID.
    :return: A dictionary categorizing dependencies by type (calls, inherits, etc.).
    """
    if not graph.has_node(node_id):
        return {"error": f"Node '{node_id}' not in graph."}
        
    dependencies = {}
    for successor in graph.successors(node_id):
        edge_data = graph.get_edge_data(node_id, successor)
        edge_type = edge_data.get('type')
        if edge_type != 'contains': # Exclude structural lineage
            if edge_type not in dependencies:
                dependencies[edge_type] = []
            
            successor_label = graph.nodes[successor].get('label', successor)
            dependencies[edge_type].append(successor_label)
            
    return dependencies

def get_upstream_dependencies(graph: nx.DiGraph, node_id: str) -> dict:
    """
    Finds all nodes that directly depend on the given node (incoming edges).

    :param graph: The NetworkX DiGraph.
    :param node_id: The starting node's unique ID.
    :return: A dictionary categorizing dependencies by type.
    """
    if not graph.has_node(node_id):
        return {"error": f"Node '{node_id}' not in graph."}

    dependencies = {}
    for predecessor in graph.predecessors(node_id):
        edge_data = graph.get_edge_data(predecessor, node_id)
        edge_type = edge_data.get('type')
        if edge_type != 'contains': # Exclude structural lineage
            if edge_type not in dependencies:
                dependencies[edge_type] = []
            
            predecessor_label = graph.nodes[predecessor].get('label', predecessor)
            dependencies[edge_type].append(predecessor_label)
            
    return dependencies

# ==============================================================================
# DEMONSTRATION
# ==============================================================================

def process_project_directory(directory_path: str) -> dict:
    """Helper function to scan a directory and generate metadata."""
    project_metadata = {}
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        source_code = f.read()
                    metadata = generate_metadata(source_code)
                    project_metadata[file_path] = metadata
                except Exception as e:
                    print(f"Could not process file {file_path}: {e}")
    return project_metadata


if __name__ == "__main__":
    # --- 1. Setup: Generate the graph (same as in main.py) ---
    target_project_dir = '.'  # Analyze the current directory
    print(f"--- Analyzing project in: {os.path.abspath(target_project_dir)} ---")
    
    metadata_collection = process_project_directory(target_project_dir)
    code_graph = create_graph_from_metadata(metadata_collection, target_project_dir)

    print(f"\n--- Graph created with {code_graph.number_of_nodes()} nodes and {code_graph.number_of_edges()} edges. ---")

    # --- 2. Analysis: Choose a target and find its lineage ---
    
    # CHANGE THIS to the label of the function, class, or variable you want to trace
    target_label = "create_graph_from_metadata" 
    
    print(f"\n--- Analyzing lineage for node: '{target_label}' ---")
    
    target_node_id = find_node_by_label(code_graph, target_label)

    if target_node_id:
        # A) Structural Lineage (Where is it?)
        structure = get_structural_lineage(code_graph, target_node_id)
        print("\n[1] Structural Lineage (Where it is defined):")
        print(" -> ".join(structure))
        
        # B) Downstream Dependencies (What does it use?)
        downstream = get_downstream_dependencies(code_graph, target_node_id)
        print("\n[2] Downstream Dependencies (What this object uses):")
        if downstream:
            for dep_type, items in downstream.items():
                print(f"  - {dep_type.upper()}: {', '.join(items)}")
        else:
            print("  - None")

        # C) Upstream Dependencies (What uses it?)
        upstream = get_upstream_dependencies(code_graph, target_node_id)
        print("\n[3] Upstream Dependencies (What uses this object):")
        if upstream:
            for dep_type, items in upstream.items():
                print(f"  - {dep_type.upper()}: {', '.join(items)}")
        else:
            print("  - None")

