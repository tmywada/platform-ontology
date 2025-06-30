import networkx as nx

def get_lineage_paths(G, start_var):
    """
    Recursively find all lineage paths from a given variable node to return values or outputs.
    """
    paths = []
    for target in G.successors(start_var):
        relation = G.edges[start_var, target].get("relation")
        if relation == "transforms_to":
            sub_paths = get_lineage_paths(G, target)
            if sub_paths:
                for p in sub_paths:
                    paths.append([start_var] + p)
            else:
                paths.append([start_var, target])
    return paths or [[start_var]]

def add_lineage_edges(G):
    """
    Add edges showing variable derivations (transforms_to) within each function.
    """
    for func in [n for n, d in G.nodes(data=True) if d.get("type") == "function"]:
        vars_in_func = [
            n for n, d in G.nodes(data=True)
            if d.get("type") == "variable" and d.get("defined_in") == func
        ]
        sorted_vars = sorted(vars_in_func, key=lambda v: G.nodes[v].get("line_number", 0))
        for i in range(len(sorted_vars) - 1):
            G.add_edge(sorted_vars[i], sorted_vars[i + 1], relation="transforms_to")

def get_transforms_to_edges(G):
    """
    Get all edges with relation 'transforms_to'.
    """
    return [
        (src, tgt) for src, tgt, d in G.edges(data=True)
        if d.get("relation") == "transforms_to"
    ]
