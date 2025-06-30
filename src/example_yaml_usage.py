import networkx as nx
import yaml_parser as yp

# Create example graph
G = nx.DiGraph()

# Parse YAML file
yaml_metadata = yp.parse_yaml_file("example.yaml")

# Add to graph
yp.add_yaml_to_graph(G, yaml_metadata, yaml_file_name="example.yaml")

# Print results
print("YAML keys found:", yaml_metadata)
print("Graph nodes:", G.nodes(data=True))
print("Graph edges:", list(G.edges(data=True)))
