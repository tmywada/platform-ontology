import re

def parse_proto_file(proto_path):
    """
    Parse a .proto file and extract messages and services.
    Returns a dict with keys 'messages' and 'services'.
    """
    messages, services = [], []
    with open(proto_path, "r") as f:
        content = f.read()
    messages = re.findall(r'message\s+(\w+)', content)
    services = re.findall(r'service\s+(\w+)', content)
    return {"messages": messages, "services": services}

def add_proto_to_graph(G, proto_metadata, proto_file_name="example.proto"):
    """
    Add proto messages and services to graph G.
    """
    G.add_node(proto_file_name, type="proto_file")
    for msg in proto_metadata.get("messages", []):
        G.add_node(msg, type="proto_message")
        G.add_edge(proto_file_name, msg, relation="defines_message")
    for svc in proto_metadata.get("services", []):
        G.add_node(svc, type="proto_service")
        G.add_edge(proto_file_name, svc, relation="defines_service")
