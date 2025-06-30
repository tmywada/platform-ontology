import ast
import yaml
import re
import networkx as nx
import json

# -------------------- Utility --------------------

def add_node_and_edge(G, parent_name, child_name, child_type, relation, extra_data=None):
    G.add_node(child_name, type=child_type)
    if extra_data:
        G.nodes[child_name].update(extra_data)
    G.add_edge(parent_name, child_name, relation=relation)

# -------------------- Python Parser --------------------

def parse_python_file(py_path):
    with open(py_path, "r") as f:
        source = f.read()
    tree = ast.parse(source)
    functions, classes, variables = [], [], []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append({
                "name": node.name,
                "args": [arg.arg for arg in node.args.args],
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno)
            })
        elif isinstance(node, ast.ClassDef):
            method_names = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            classes.append({
                "name": node.name,
                "methods": method_names,
                "start_line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno)
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    variables.append({
                        "name": target.id,
                        "line": node.lineno
                    })
    return {"functions": functions, "classes": classes, "variables": variables}

# -------------------- YAML Parser --------------------

def parse_yaml_file(yaml_path):
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {}
    return {key: type(value).__name__ for key, value in data.items()}

# -------------------- Proto Parser --------------------

def parse_proto_file(proto_path):
    with open(proto_path, "r") as f:
        content = f.read()
    messages = re.findall(r'message\s+(\w+)', content)
    services = re.findall(r'service\s+(\w+)', content)
    return {"messages": messages, "services": services}

# -------------------- Orchestrator Parser --------------------

def parse_orchestrator_file(file_path):
    with open(file_path, "r") as f:
        lines = f.readlines()
    calls = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return calls

# -------------------- Main Consolidation --------------------

def extract_all_metadata(py_path, yaml_path, proto_path, orch_path, output_json="metadata.json"):
    G = nx.DiGraph()

    # Python
    py_metadata = parse_python_file(py_path)
    G.add_node(py_path, type="python_script")
    for func in py_metadata["functions"]:
        add_node_and_edge(G, py_path, func["name"], "function", "defines_function", func)
    for cls in py_metadata["classes"]:
        add_node_and_edge(G, py_path, cls["name"], "class", "defines_class", cls)
        for method in cls["methods"]:
            add_node_and_edge(G, cls["name"], f"{cls['name']}.{method}", "method", "defines_method")
    for var in py_metadata["variables"]:
        add_node_and_edge(G, py_path, var["name"], "variable", "defines_variable", var)

    # YAML
    yaml_metadata = parse_yaml_file(yaml_path)
    G.add_node(yaml_path, type="yaml_file")
    for key, val_type in yaml_metadata.items():
        add_node_and_edge(G, yaml_path, key, "yaml_key", "defines_key", {"value_type": val_type})

    # Proto
    proto_metadata = parse_proto_file(proto_path)
    G.add_node(proto_path, type="proto_file")
    for msg in proto_metadata["messages"]:
        add_node_and_edge(G, proto_path, msg, "proto_message", "defines_message")
    for svc in proto_metadata["services"]:
        add_node_and_edge(G, proto_path, svc, "proto_service", "defines_service")

    # Orchestrator
    calls = parse_orchestrator_file(orch_path)
    G.add_node(orch_path, type="orchestrator")
    for call in calls:
        add_node_and_edge(G, orch_path, call, "called_script", "calls")

    # Export metadata
    nodes_list = [{"name": n, **d} for n, d in G.nodes(data=True)]
    edges_list = [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)]
    metadata = {"nodes": nodes_list, "edges": edges_list}

    with open(output_json, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata extracted and saved to {output_json}")

# -------------------- Example Usage --------------------

if __name__ == "__main__":
    extract_all_metadata("example.py", "example.yaml", "example.proto", "example.sh")
