import hashlib
import networkx as nx
from pyvis.network import Network
import os
import json

def generate_string_for_uid(entity: dict, file_path: str, delimiter: str = "||") -> str:
    """ Python repo specific version of the UID generator."""
    entity_type = entity.get("type")
    # --- Start with the base file path.
    id_parts = [file_path]

    # For imports, the structure is simpler and doesn't use parent scopes.
    # Handle these first as a special case.
    if entity_type in ("import", "from_import"):
        module = entity.get("module", "")
        name = entity.get("name", "")  # Specific to 'from_import'
        id_parts.extend(["import", module])
        if name:
            id_parts.append(name)
        
        return delimiter.join(filter(None, id_parts))
        

    # --- For all other types, build the ID from hierarchical parts ---
    # --- Add parent scopes.
    if entity.get("class"):
        id_parts.append(entity["class"])
    
    if entity.get("parent_function"):
        id_parts.append(entity["parent_function"])

    # --- Add the specific entity identifier based on its type.
    if entity_type == "class":
        id_parts.append(entity['class_name'])
        
    elif entity_type == "function":
        id_parts.append(entity['function_name'])
        
    elif entity_type == "assignment":
        # Add the immediate function scope if it's not already a parent.
        if entity.get("function") and entity.get("function") not in id_parts:
             id_parts.append(entity["function"])
        
        variable = entity.get("variable", "unknown_var")
        line = entity.get("start_line", 0)
        id_parts.append(f"{variable}@{line}")
        
    else:  # Fallback for any unhandled or unknown types.
        id_parts.append("unknown")
        id_parts.append(entity.get('name', 'entity'))

    # --- Join all parts into the final UID string.
    return delimiter.join(id_parts)


def get_unique_id(id_string: str) -> str:
    return hashlib.sha1(id_string.encode('utf-8')).hexdigest()


def create_graph_from_metadata(metadata_collection: dict, project_root: str) -> nx.DiGraph:
    """
    Builds a comprehensive NetworkX DiGraph from project metadata, including
    folder/file structure and all code entities.
    """
    G = nx.DiGraph()
    # defined_names maps a simple name (like 'MyClass') to its unique hashed ID
    defined_names = {}

    # --- Pass 1: Create all structural (folder, file) and code entity nodes ---
    print("--- Graph Creation: Pass 1 (Creating All Nodes) ---")
    
    # Add the root project folder node
    abs_project_root = os.path.abspath(project_root)
    G.add_node(abs_project_root, label=os.path.basename(abs_project_root), node_type='folder')

    for file_path, metadata in metadata_collection.items():
        # Create nodes for directories and the file itself
        abs_file_path = os.path.abspath(file_path)
        parent_dir_path = os.path.dirname(abs_file_path)
        
        # Ensure all parent directories exist as nodes
        current_path = abs_project_root
        path_parts = os.path.relpath(parent_dir_path, os.path.dirname(abs_project_root)).split(os.sep)
        for part in path_parts:
            if part == ".": continue
            next_path = os.path.join(current_path, part)
            if not G.has_node(next_path):
                G.add_node(next_path, label=part, node_type='folder')
                G.add_edge(current_path, next_path, type='contains')
            current_path = next_path
        
        # Add file node
        G.add_node(abs_file_path, label=os.path.basename(abs_file_path), node_type='file')
        G.add_edge(parent_dir_path, abs_file_path, type='contains')

        # Create nodes for all code entities within the file
        all_entities = (metadata.get("imports", []) + metadata.get("classes", []) + 
                        metadata.get("functions", []) + metadata.get("assignments", []))
        
        for entity in all_entities:
            uid_string = generate_string_for_uid(entity, file_path)
            uid = get_unique_id(uid_string)
            
            # Determine label and parent for containment edge
            label = "entity"
            parent_uid = abs_file_path # Default parent is the file
            
            entity_type = entity.get("type")
            if entity_type == 'class':
                label = entity['class_name']
                defined_names[label] = uid
            elif entity_type == 'function':
                label = entity['function_name']
                # Methods are contained by classes, nested functions by functions
                if entity.get('class'):
                    parent_uid = defined_names.get(entity['class'])
                elif entity.get('parent_function'):
                    # This requires a more complex lookup not implemented here for simplicity,
                    # falls back to file containment.
                    pass
                defined_names[label] = uid
            elif entity_type == 'assignment':
                label = entity['variable']
            elif 'module' in entity:
                label = entity.get('module') + (f".{entity.get('name')}" if entity.get('name') else "")

            G.add_node(uid, label=label, **entity)
            if parent_uid and G.has_node(parent_uid):
                 G.add_edge(parent_uid, uid, type='contains')

    # --- Pass 2: Create all dependency edges (calls, inheritance, etc.) ---
    print("--- Graph Creation: Pass 2 (Creating Dependency Edges) ---")
    for file_path, metadata in metadata_collection.items():
        all_code_entities = metadata.get("classes", []) + metadata.get("functions", [])
        
        for entity in all_code_entities:
            source_uid_string = generate_string_for_uid(entity, file_path)
            source_uid = get_unique_id(source_uid_string)

            # Edge: Inheritance
            if "bases" in entity:
                for base in entity.get("bases", []):
                    if base in defined_names:
                        target_uid = defined_names[base]
                        G.add_edge(source_uid, target_uid, type="inherits")

            # Edge: Decorators
            if "decorators" in entity:
                for decorator in entity.get("decorators", []):
                    if decorator in defined_names:
                        target_uid = defined_names[decorator]
                        G.add_edge(target_uid, source_uid, type="decorates")

            # Edge: Function Calls
            if "calls" in entity:
                for call in entity.get("calls", []):
                    callee_name = call["called"]
                    if callee_name in defined_names:
                        target_uid = defined_names[callee_name]
                        G.add_edge(source_uid, target_uid, type="calls")
                    else:
                        if not G.has_node(callee_name):
                            G.add_node(callee_name, label=callee_name, node_type="external")
                        G.add_edge(source_uid, callee_name, type="calls")

            # Edge: Variable Usage (simplified)
            if "variables_used" in entity:
                # This part is complex as it requires scope resolution.
                # A full implementation would trace variables back to their assignment UID.
                # For now, this remains a potential enhancement.
                pass

    return G


# def visualize_graph_with_pyvis(graph: nx.DiGraph, output_filename: str):
#     """
#     Creates an interactive HTML visualization of the code graph using pyvis.
#     Nodes are colored based on their type (class, function, or external).

#     :param graph: The NetworkX DiGraph to visualize.
#     :param output_filename: The path to save the resulting HTML file.
#     """
#     print(f"--- Creating HTML Visualization ({output_filename}) ---")
#     net = Network(height="100vh", width="100%", bgcolor="#222222", font_color="white", directed=True)

#     # Set physics options for a better layout
#     net.set_options("""
#     var options = {
#       "physics": {
#         "forceAtlas2Based": {
#           "gravitationalConstant": -50,
#           "centralGravity": 0.01,
#           "springLength": 230,
#           "springConstant": 0.08,
#           "avoidOverlap": 0.5
#         },
#         "minVelocity": 0.75,
#         "solver": "forceAtlas2Based"
#       }
#     }
#     """)

#     # Add nodes to the pyvis network, styling them based on their type
#     for node, data in graph.nodes(data=True):
#         node_type = data.get('node_type', 'unknown')
#         color = "#C2EAFC"  # Default
#         if node_type == "class":
#             color = "#29B6F6"  # Blue
#         elif node_type == "function":
#             color = "#9CCC65"  # Green
#         elif node_type == "external":
#             color = "#FFA726"  # Orange

#         title = f"UID: {node}<br>"
#         title += "<br>".join(f"{key}: {value}" for key, value in data.items())

#         net.add_node(node, label=data.get('label', node), color=color, title=title)
        
#     # Add edges
#     for source, target, data in graph.edges(data=True):
#         edge_type = data.get('type', '')
#         net.add_edge(source, target, title=edge_type)
        
#     try:
#         net.save_graph(output_filename)
#         print(f"✅ Interactive graph saved to: {os.path.abspath(output_filename)}")
#     except Exception as e:
#         print(f"❗️ Could not save graph: {e}")


def create_html_visualization(graph: nx.DiGraph, output_path: str):
    """
    Generates an interactive HTML visualization using pyvis.
    """
    print(f"--- Creating Pyvis HTML Visualization: {output_path} ---")
    net = Network(height="100vh", width="100%", bgcolor="#222222", font_color="white", directed=True)
    net.set_options("""
    var options = {
      "physics": { "forceAtlas2Based": { "avoidOverlap": 0.5 } },
      "layout": { "hierarchical": { "enabled": false } }
    }
    """)

    for node_id, data in graph.nodes(data=True):
        node_type = data.get('type', data.get('node_type', 'unknown'))
        color, shape = "#C2EAFC", "dot"  # Default
        
        if node_type == "folder": color, shape = "#FFCA28", "database" # Yellow
        elif node_type == "file": color, shape = "#42A5F5", "box" # Blue
        elif node_type == "class": color, shape = "#66BB6A", "square" # Green
        elif node_type == "function": color, shape = "#9CCC65", "dot" # Light Green
        elif node_type == "assignment": color, shape = "#BDBDBD", "diamond" # Grey
        elif node_type.startswith("import"): color, shape = "#EF5350", "triangle" # Red
        elif node_type == "external": color, shape = "#FFA726", "triangleDown" # Orange

        title_html = f"<b>ID:</b> {node_id}<br><hr>"
        for key, value in data.items():
            if key not in ['label', 'id']:
                 title_html += f"<b>{key.replace('_', ' ').title()}:</b> {value}<br>"
        
        net.add_node(node_id, label=data.get("label", node_id), color=color, shape=shape, title=title_html)
        
    for u, v, data in graph.edges(data=True):
        edge_type = data.get('type', '')
        color = {"contains": "#444444", "calls": "#FFFFFF", "inherits": "#66BB6A", "decorates": "#FFA726"}.get(edge_type, "#9E9E9E")
        net.add_edge(u, v, title=edge_type, label=edge_type if edge_type != 'contains' else '', color=color)
        
    try:
        net.save_graph(output_path)
        print(f"✅ Interactive HTML visualization saved to {os.path.abspath(output_path)}")
    except Exception as e:
        print(f"❗️ Could not save pyvis graph: {e}")










# def create_html_visualization(graph: nx.DiGraph, output_path: str):
#     """
#     Generates an interactive, self-contained HTML visualization of the code graph
#     using the pyvis library. Nodes are styled based on their type, and hovering
#     reveals detailed metadata.

#     :param graph: The NetworkX DiGraph to visualize.
#     :param output_path: The path to save the resulting HTML file.
#     """
#     print(f"--- Creating Pyvis HTML Visualization: {output_path} ---")

#     # 1. Initialize the pyvis network with a dark theme
#     net = Network(
#         height="100vh", 
#         width="100%", 
#         bgcolor="#222222", 
#         font_color="white", 
#         directed=True
#     )

#     # 2. Set physics options for a better, more stable layout
#     net.set_options("""
#     var options = {
#       "physics": {
#         "forceAtlas2Based": {
#           "gravitationalConstant": -50,
#           "centralGravity": 0.01,
#           "springLength": 230,
#           "springConstant": 0.08,
#           "avoidOverlap": 0.5
#         },
#         "minVelocity": 0.75,
#         "solver": "forceAtlas2Based"
#       }
#     }
#     """)

#     # 3. Add nodes to the pyvis network, styling them based on their type
#     for node_id, data in graph.nodes(data=True):
#         node_type = data.get('node_type', 'unknown')
        
#         # Determine color and shape based on the node type
#         color = "#C2EAFC"  # Default color
#         shape = "dot"
#         if node_type == "class":
#             color = "#29B6F6"  # Blue
#             shape = "square"
#         elif node_type == "function":
#             color = "#9CCC65"  # Green
#             shape = "dot"
#         elif node_type == "external":
#             color = "#FFA726"  # Orange
#             shape = "triangle"

#         # Create a rich HTML title for the hover tooltip
#         # This will display all metadata associated with the node
#         title_html = f"<b>UID:</b> {node_id}<br>"
#         title_html += "<hr style='margin: 5px 0; border-color: #555;'>"
#         for key, value in data.items():
#             # Exclude redundant or overly long fields from the tooltip
#             if key not in ['label', 'id']:
#                  title_html += f"<b>{key.replace('_', ' ').title()}:</b> {value}<br>"
        
#         net.add_node(
#             node_id, 
#             label=data.get("label", node_id), 
#             color=color, 
#             shape=shape,
#             title=title_html
#         )
        
#     # 4. Add edges to the pyvis network
#     for u, v, data in graph.edges(data=True):
#         edge_type = data.get("type", "")
#         net.add_edge(u, v, title=edge_type, label=edge_type)
        
#     # 5. Save the graph to the specified HTML file
#     try:
#         net.save_graph(output_path)
#         print(f"✅ Interactive HTML visualization saved to {os.path.abspath(output_path)}")
#     except Exception as e:
#         print(f"❗️ Could not save pyvis graph: {e}")




# def create_graph_from_metadata(metadata: dict) -> nx.DiGraph:
#     """Builds a NetworkX DiGraph from the combined project metadata."""
#     G = nx.DiGraph()
    
#     # Create a lookup for defined names to their unique IDs
#     defined_names = {}

#     for cls in metadata.get("classes", []):
#         uid = get_unique_id(cls)
#         defined_names[cls["class_name"]] = uid
#         G.add_node(uid, label=cls["class_name"], node_type="class", **cls)

#     for func in metadata.get("functions", []):
#         uid = get_unique_id(func)
#         # Handle both standalone functions and methods
#         simple_name = f"{func['class']}.{func['function_name']}" if func['class'] else func['function_name']
#         defined_names[simple_name] = uid
#         G.add_node(uid, label=simple_name, node_type="function", **func)

#     # Process relationships
#     for entity_list in metadata.values():
#         for entity in entity_list:
#             caller_uid = get_unique_id(entity)
#             if not G.has_node(caller_uid):
#                 continue

#             # Class inheritance
#             if "bases" in entity:
#                 for base in entity["bases"]:
#                     if base in defined_names:
#                         G.add_edge(caller_uid, defined_names[base], edge_type="inherits")

#             # Decorators
#             if "decorators" in entity:
#                 for decorator in entity["decorators"]:
#                     if decorator in defined_names:
#                         G.add_edge(defined_names[decorator], caller_uid, edge_type="decorates")

#             # Function calls
#             if "calls" in entity:
#                 for call in entity["calls"]:
#                     callee_name = call["called"]
#                     if callee_name in defined_names:
#                         G.add_edge(caller_uid, defined_names[callee_name], edge_type="calls")
#                     else: # External or unresolved call
#                         if not G.has_node(callee_name):
#                             G.add_node(callee_name, label=callee_name, node_type="external")
#                         G.add_edge(caller_uid, callee_name, edge_type="calls")
#     return G




# # ==============================================================================
# # HTML VISUALIZATION WITH CLICKABLE DETAILS PANEL
# # ==============================================================================

# def create_html_visualization(graph: nx.DiGraph, output_path: str):
#     """
#     Generates a self-contained HTML file with a dynamic details panel.
#     """
#     nodes_data = []
#     for node_id, data in graph.nodes(data=True):
#         nodes_data.append({
#             "id": node_id, 
#             "label": data.get("label", node_id), 
#             "color": {"background": "skyblue" if data.get("node_type") == "class" else "lightgreen" if data.get("node_type") == "function" else "plum" if data.get("node_type") == "decorator" else "lightcoral"},
#             "shape": "circle",
#             "title": f"Origin: {data.get('file_path', 'N/A')}<br>Type: {data.get('node_type', 'N/A')}",
#             "details": data
#         })

#     edges_data = []
#     for u, v, data in graph.edges(data=True):
#         edge_type = data.get("edge_type", "")
#         edges_data.append({
#             "from": u, "to": v, "label": edge_type, "title": f"Type: {edge_type}", 
#             "arrows": "to", "details": {"source": u, "target": v, "type": edge_type}
#         })

#     nodes_json = json.dumps(nodes_data, indent=2)
#     edges_json = json.dumps(edges_data, indent=2)

#     html_template = f"""
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Code Dependency Graph</title>
#     <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
#     <style>
#         body, html {{ margin: 0; padding: 0; height: 100%; font-family: Arial, sans-serif; background-color: #222; color: white; }}
#         #graph-container {{ width: 100%; height: 100%; position: absolute; top: 0; left: 0; z-index: 1; }}
#         #details-panel {{
#             position: absolute; bottom: 20px; right: 20px; width: 450px; max-height: 45%;
#             background-color: rgba(40, 40, 40, 0.9); border: 1px solid #555; border-radius: 8px;
#             z-index: 2; overflow-y: auto; display: none; /* Hidden by default */
#         }}
#         #details-panel h3 {{ margin: 0; padding: 10px; background-color: #333; border-bottom: 1px solid #555; }}
#         #details-table {{ width: 100%; border-collapse: collapse; }}
#         #details-table th, #details-table td {{ padding: 8px; text-align: left; vertical-align: top; border-bottom: 1px solid #444; }}
#         #details-table th {{ width: 120px; font-weight: bold; color: #aaa; }}
#     </style>
# </head>
# <body>
#     <div id="graph-container"></div>
#     <div id="details-panel"><h3 id="details-header">Details</h3><div id="details-content"></div></div>
#     <script type="text/javascript">
#         const nodesData = {nodes_json};
#         const edgesData = {edges_json};
#         const graphContainer = document.getElementById('graph-container');
#         const detailsPanel = document.getElementById('details-panel');
#         const detailsHeader = document.getElementById('details-header');
#         const detailsContent = document.getElementById('details-content');
#         const nodes = new vis.DataSet(nodesData);
#         const edges = new vis.DataSet(edgesData);
#         const options = {{
#             nodes: {{
#                 shape: 'circle',
#                 size: 20, // Uniform node size for all nodes
#                 font: {{
#                     vadjust: 30 // Vertically adjust label to be at the bottom
#                 }}
#             }},
#             interaction: {{ hover: true, navigationButtons: true }},
#             physics: {{ solver: 'forceAtlas2Based' }},
#             configure: {{ enabled: true, filter: 'physics', showButton: true }}
#         }};
#         const network = new vis.Network(graphContainer, {{ nodes: nodes, edges: edges }}, options);
#         network.on("click", function (params) {{
#             let details = null, type = '';
#             if (params.nodes.length > 0) {{
#                 details = nodes.get(params.nodes[0]).details;
#                 type = 'Node';
#             }} else if (params.edges.length > 0) {{
#                 details = edges.get(params.edges[0]).details;
#                 type = 'Edge';
#             }}
#             updateDetailsPanel(details, type);
#         }});
#         function updateDetailsPanel(details, type) {{
#             if (!details) {{ detailsPanel.style.display = 'none'; return; }}
#             detailsHeader.innerText = `${{type}} Details`;
#             let contentHtml = '<table id="details-table">';
#             for (const [key, value] of Object.entries(details)) {{
#                 if (value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length > 0)) {{
#                     let displayValue = Array.isArray(value) ? value.join(', ') : String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
#                     contentHtml += `<tr><th>${{key.replace(/_/g, ' ')}}</th><td>${{displayValue}}</td></tr>`;
#                 }}
#             }}
#             contentHtml += '</table>';
#             detailsContent.innerHTML = contentHtml;
#             detailsPanel.style.display = 'block';
#         }}
#     </script>
# </body>
# </html>
#     """
#     with open(output_path, "w", encoding="utf-8") as f:
#         f.write(html_template)
#     print(f"✅ Interactive HTML visualization saved to {output_path}")

# # --- Main Execution ---
# if __name__ == "__main__":
#     # 1. Create a dummy project structure for demonstration
#     project_dir = "generated_project"
#     os.makedirs(project_dir, exist_ok=True)
    
#     utils_code = """
# def helper_function():
#     '''A helper function in a separate utility file.'''
#     print("Executing helper function.")
#     return True
# """
#     main_code = """
# from utils import helper_function

# class MainProcessor:
#     '''The main class of the project.'''
#     def __init__(self):
#         self.data = None

#     def run(self):
#         '''Runs the main processing logic.'''
#         print("Running processor.")
#         self.data = helper_function()
#         return self.data
# """
#     with open(os.path.join(project_dir, "utils.py"), "w") as f: f.write(utils_code)
#     with open(os.path.join(project_dir, "main.py"), "w") as f: f.write(main_code)
#     print(f"✅ Sample project created in '{project_dir}/'")

#     # 2. Generate metadata for the entire project
#     metadata = generate_metadata_for_project(project_dir)
#     metadata_file = os.path.join(project_dir, "metadata.json")
#     with open(metadata_file, "w") as f: json.dump(metadata, f, indent=2)
#     print(f"✅ Project metadata generated and saved to {metadata_file}")

#     # 3. Create a graph from the metadata
#     code_graph = create_graph_from_metadata(metadata)
#     print(f"✅ NetworkX graph created with {code_graph.number_of_nodes()} nodes and {code_graph.number_of_edges()} edges.")

#     # 4. Generate the interactive HTML visualization
#     graph_file = os.path.join(project_dir, "dependency_graph.html")
#     create_html_visualization(code_graph, graph_file)

