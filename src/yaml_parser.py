import yaml

def parse_yaml_file(yaml_path):
    """
    Parse a YAML file and extract top-level keys.
    Returns a dict with keys and their value types.
    """
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        return {}
    return {key: type(value).__name__ for key, value in data.items()}

def add_yaml_to_graph(G, yaml_metadata, yaml_file_name="config.yaml"):
    """
    Add YAML keys to graph G.
    """
    G.add_node(yaml_file_name, type="yaml_file")
    for key, val_type in yaml_metadata.items():
        G.add_node(key, type="yaml_key", value_type=val_type)
        G.add_edge(yaml_file_name, key, relation="defines_key")
