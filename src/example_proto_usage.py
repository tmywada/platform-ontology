import networkx as nx
import proto_parser as pp

# Create example graph
G = nx.DiGraph()

# Example: parse proto file
proto_metadata = pp.parse_proto_file("example.proto")

# Add to graph
pp.add_proto_to_graph(G, proto_metadata, proto_file_name="example.proto")

# Print results
print("Messages found:", proto_metadata["messages"])
print("Services found:", proto_metadata["services"])

print("Graph nodes:", G.nodes(data=True))
print("Graph edges:", list(G.edges(data=True)))
