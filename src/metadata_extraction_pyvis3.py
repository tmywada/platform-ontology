import ast
import json
import os
import networkx as nx
from pathlib import Path

# ==============================================================================
# METADATA GENERATION SCRIPT
# ==============================================================================

class MetadataVisitor(ast.NodeVisitor):
    """
    An AST visitor that collects metadata about classes, functions, and assignments
    for a specific file.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.current_class = None
        self.current_function_meta = None
        self.imports_metadata = []
        self.classes_metadata = []
        self.functions_metadata = []
        self.assignments_metadata = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports_metadata.append({
                "file_path": self.file_path, "type": "import", "module": alias.name, 
                "alias": alias.asname, "start_line": node.lineno, 
                "end_line": getattr(node, 'end_lineno', node.lineno)
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ''
        for alias in node.names:
            self.imports_metadata.append({
                "file_path": self.file_path, "type": "from_import", "module": module, 
                "name": alias.name, "alias": alias.asname, "level": node.level, 
                "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', node.lineno)
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_info = {
            "file_path": self.file_path, "class_name": node.name, 
            "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', None),
            "bases": [self._get_expr_repr(base) for base in node.bases],
            "decorators": [self._get_expr_repr(d) for d in node.decorator_list], 
            "docstring": ast.get_docstring(node)
        }
        self.classes_metadata.append(class_info)
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        function_info = {
            "file_path": self.file_path, "function_name": node.name, 
            "class": self.current_class, "start_line": node.lineno,
            "end_line": getattr(node, 'end_lineno', None), 
            "docstring": ast.get_docstring(node),
            "decorators": [self._get_expr_repr(d) for d in node.decorator_list],
            "arguments": self._parse_function_args(node.args), 
            "calls": [], "variables_used": [], "returns": []
        }
        self.functions_metadata.append(function_info)
        prev_function_meta = self.current_function_meta
        self.current_function_meta = function_info
        self.generic_visit(node)
        self.current_function_meta = prev_function_meta

    def visit_Assign(self, node: ast.Assign):
        value_type, value_repr = self._get_value_info(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assignments_metadata.append({
                    "file_path": self.file_path,
                    "class": self.current_class,
                    "function": self.current_function_meta['function_name'] if self.current_function_meta else None,
                    "variable": target.id, "value_type": value_type, 
                    "value_representation": value_repr, "start_line": node.lineno, 
                    "end_line": getattr(node, 'end_lineno', None)
                })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if self.current_function_meta:
            self.current_function_meta["calls"].append({
                "called": self._get_called_func_name(node), 
                "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', None)
            })
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        if self.current_function_meta:
            self.current_function_meta["returns"].append({
                "return_expression": self._get_expr_repr(node.value), 
                "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', None)
            })
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if self.current_function_meta and isinstance(node.ctx, ast.Load):
            var_name = node.id
            if not any(d['variable'] == var_name for d in self.current_function_meta["variables_used"]):
                self.current_function_meta["variables_used"].append({
                    "variable": var_name, "start_line": node.lineno, 
                    "end_line": getattr(node, 'end_lineno', None)
                })

    def _parse_function_args(self, args_node: ast.arguments) -> list:
        arguments_list = []
        num_defaults = len(args_node.defaults)
        default_start_index = len(args_node.args) - num_defaults
        for i, arg in enumerate(args_node.args):
            arg_info = {"name": arg.arg, "default": None, "data_type": self._get_expr_repr(arg.annotation)}
            if i >= default_start_index:
                arg_info["default"] = self._get_expr_repr(args_node.defaults[i - default_start_index])
            arguments_list.append(arg_info)
        for i, arg in enumerate(args_node.kwonlyargs):
            arguments_list.append({
                "name": arg.arg, "default": self._get_expr_repr(args_node.kw_defaults[i]),
                "data_type": self._get_expr_repr(arg.annotation)
            })
        return arguments_list

    def _get_value_info(self, value: ast.AST) -> tuple[str, str]:
        if isinstance(value, ast.Constant): return "constant", repr(value.value)
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)): return type(value).__name__.lower(), f"{len(value.elts)} items"
        if isinstance(value, ast.Dict): return "dict", f"{len(value.keys)} keys"
        if isinstance(value, ast.Call): return "call", self._get_expr_repr(value)
        if isinstance(value, ast.Name): return "reference", value.id
        return "complex", ast.dump(value, annotate_fields=False)

    def _get_called_func_name(self, call_node: ast.Call) -> str:
        func = call_node.func
        if isinstance(func, ast.Name): return func.id
        if isinstance(func, ast.Attribute):
            parts = []
            current = func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name): parts.append(current.id)
            return ".".join(reversed(parts))
        return "complex_call"

    def _get_expr_repr(self, expr: ast.AST | None) -> str:
        if expr is None: return None
        if isinstance(expr, ast.Constant): return repr(expr.value)
        if isinstance(expr, ast.Name): return expr.id
        if isinstance(expr, ast.Attribute): return self._get_called_func_name(ast.Call(func=expr))
        if isinstance(expr, ast.Call): return f"{self._get_called_func_name(expr)}(...)"
        return ast.dump(expr, annotate_fields=False)

def generate_metadata_for_project(project_path: str) -> dict:
    """
    Generates combined metadata for all Python files in a project directory.
    """
    all_metadata = {"imports": [], "classes": [], "functions": [], "assignments": []}
    for file_path in Path(project_path).rglob('*.py'):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
            tree = ast.parse(source_code, filename=str(file_path))
            
            # Use relative path for cleaner IDs
            relative_path = str(file_path.relative_to(project_path))
            visitor = MetadataVisitor(file_path=relative_path)
            visitor.visit(tree)

            all_metadata["imports"].extend(visitor.imports_metadata)
            all_metadata["classes"].extend(visitor.classes_metadata)
            all_metadata["functions"].extend(visitor.functions_metadata)
            all_metadata["assignments"].extend(visitor.assignments_metadata)

        except Exception as e:
            print(f"Could not process file {file_path}: {e}")
            
    return all_metadata

# ==============================================================================
# NETWORKX GRAPH CREATION
# ==============================================================================

def get_unique_id(entity: dict) -> str:
    """Creates a unique ID for a code entity, e.g., 'file.py::ClassName'."""
    file_path = entity.get("file_path", "")
    name = entity.get("class_name") or entity.get("function_name")
    if entity.get("class") and name: # It's a method
        return f"{file_path}::{entity['class']}.{name}"
    return f"{file_path}::{name}"

def create_graph_from_metadata(metadata: dict) -> nx.DiGraph:
    """Builds a NetworkX DiGraph from the combined project metadata."""
    G = nx.DiGraph()
    
    # Create a lookup for defined names to their unique IDs
    defined_names = {}

    for cls in metadata.get("classes", []):
        uid = get_unique_id(cls)
        defined_names[cls["class_name"]] = uid
        G.add_node(uid, label=cls["class_name"], node_type="class", **cls)

    for func in metadata.get("functions", []):
        uid = get_unique_id(func)
        # Handle both standalone functions and methods
        simple_name = f"{func['class']}.{func['function_name']}" if func['class'] else func['function_name']
        defined_names[simple_name] = uid
        G.add_node(uid, label=simple_name, node_type="function", **func)

    # Process relationships
    for entity_list in metadata.values():
        for entity in entity_list:
            caller_uid = get_unique_id(entity)
            if not G.has_node(caller_uid):
                continue

            # Class inheritance
            if "bases" in entity:
                for base in entity["bases"]:
                    if base in defined_names:
                        G.add_edge(caller_uid, defined_names[base], edge_type="inherits")

            # Decorators
            if "decorators" in entity:
                for decorator in entity["decorators"]:
                    if decorator in defined_names:
                        G.add_edge(defined_names[decorator], caller_uid, edge_type="decorates")

            # Function calls
            if "calls" in entity:
                for call in entity["calls"]:
                    callee_name = call["called"]
                    if callee_name in defined_names:
                        G.add_edge(caller_uid, defined_names[callee_name], edge_type="calls")
                    else: # External or unresolved call
                        if not G.has_node(callee_name):
                            G.add_node(callee_name, label=callee_name, node_type="external")
                        G.add_edge(caller_uid, callee_name, edge_type="calls")
    return G

# ==============================================================================
# HTML VISUALIZATION WITH CLICKABLE DETAILS PANEL
# ==============================================================================

def create_html_visualization(graph: nx.DiGraph, output_path: str):
    """
    Generates a self-contained HTML file with a dynamic details panel.
    """
    nodes_data = []
    for node_id, data in graph.nodes(data=True):
        nodes_data.append({
            "id": node_id, 
            "label": data.get("label", node_id), 
            "color": {"background": "skyblue" if data.get("node_type") == "class" else "lightgreen" if data.get("node_type") == "function" else "plum" if data.get("node_type") == "decorator" else "lightcoral"},
            "shape": "circle",
            "title": f"Origin: {data.get('file_path', 'N/A')}<br>Type: {data.get('node_type', 'N/A')}",
            "details": data
        })

    edges_data = []
    for u, v, data in graph.edges(data=True):
        edge_type = data.get("edge_type", "")
        edges_data.append({
            "from": u, "to": v, "label": edge_type, "title": f"Type: {edge_type}", 
            "arrows": "to", "details": {"source": u, "target": v, "type": edge_type}
        })

    nodes_json = json.dumps(nodes_data, indent=2)
    edges_json = json.dumps(edges_data, indent=2)

    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Dependency Graph</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body, html {{ margin: 0; padding: 0; height: 100%; font-family: Arial, sans-serif; background-color: #222; color: white; }}
        #graph-container {{ width: 100%; height: 100%; position: absolute; top: 0; left: 0; z-index: 1; }}
        #details-panel {{
            position: absolute; bottom: 20px; right: 20px; width: 450px; max-height: 45%;
            background-color: rgba(40, 40, 40, 0.9); border: 1px solid #555; border-radius: 8px;
            z-index: 2; overflow-y: auto; display: none; /* Hidden by default */
        }}
        #details-panel h3 {{ margin: 0; padding: 10px; background-color: #333; border-bottom: 1px solid #555; }}
        #details-table {{ width: 100%; border-collapse: collapse; }}
        #details-table th, #details-table td {{ padding: 8px; text-align: left; vertical-align: top; border-bottom: 1px solid #444; }}
        #details-table th {{ width: 120px; font-weight: bold; color: #aaa; }}
    </style>
</head>
<body>
    <div id="graph-container"></div>
    <div id="details-panel"><h3 id="details-header">Details</h3><div id="details-content"></div></div>
    <script type="text/javascript">
        const nodesData = {nodes_json};
        const edgesData = {edges_json};
        const graphContainer = document.getElementById('graph-container');
        const detailsPanel = document.getElementById('details-panel');
        const detailsHeader = document.getElementById('details-header');
        const detailsContent = document.getElementById('details-content');
        const nodes = new vis.DataSet(nodesData);
        const edges = new vis.DataSet(edgesData);
        const options = {{
            nodes: {{
                shape: 'circle',
                size: 20, // Uniform node size for all nodes
                font: {{
                    vadjust: 30 // Vertically adjust label to be at the bottom
                }}
            }},
            interaction: {{ hover: true, navigationButtons: true }},
            physics: {{ solver: 'forceAtlas2Based' }},
            configure: {{ enabled: true, filter: 'physics', showButton: true }}
        }};
        const network = new vis.Network(graphContainer, {{ nodes: nodes, edges: edges }}, options);
        network.on("click", function (params) {{
            let details = null, type = '';
            if (params.nodes.length > 0) {{
                details = nodes.get(params.nodes[0]).details;
                type = 'Node';
            }} else if (params.edges.length > 0) {{
                details = edges.get(params.edges[0]).details;
                type = 'Edge';
            }}
            updateDetailsPanel(details, type);
        }});
        function updateDetailsPanel(details, type) {{
            if (!details) {{ detailsPanel.style.display = 'none'; return; }}
            detailsHeader.innerText = `${{type}} Details`;
            let contentHtml = '<table id="details-table">';
            for (const [key, value] of Object.entries(details)) {{
                if (value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length > 0)) {{
                    let displayValue = Array.isArray(value) ? value.join(', ') : String(value).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                    contentHtml += `<tr><th>${{key.replace(/_/g, ' ')}}</th><td>${{displayValue}}</td></tr>`;
                }}
            }}
            contentHtml += '</table>';
            detailsContent.innerHTML = contentHtml;
            detailsPanel.style.display = 'block';
        }}
    </script>
</body>
</html>
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"✅ Interactive HTML visualization saved to {output_path}")

# --- Main Execution ---
if __name__ == "__main__":
    # 1. Create a dummy project structure for demonstration
    project_dir = "generated_project"
    os.makedirs(project_dir, exist_ok=True)
    
    utils_code = """
def helper_function():
    '''A helper function in a separate utility file.'''
    print("Executing helper function.")
    return True
"""
    main_code = """
from utils import helper_function

class MainProcessor:
    '''The main class of the project.'''
    def __init__(self):
        self.data = None

    def run(self):
        '''Runs the main processing logic.'''
        print("Running processor.")
        self.data = helper_function()
        return self.data
"""
    with open(os.path.join(project_dir, "utils.py"), "w") as f: f.write(utils_code)
    with open(os.path.join(project_dir, "main.py"), "w") as f: f.write(main_code)
    print(f"✅ Sample project created in '{project_dir}/'")

    # 2. Generate metadata for the entire project
    metadata = generate_metadata_for_project(project_dir)
    metadata_file = os.path.join(project_dir, "metadata.json")
    with open(metadata_file, "w") as f: json.dump(metadata, f, indent=2)
    print(f"✅ Project metadata generated and saved to {metadata_file}")

    # 3. Create a graph from the metadata
    code_graph = create_graph_from_metadata(metadata)
    print(f"✅ NetworkX graph created with {code_graph.number_of_nodes()} nodes and {code_graph.number_of_edges()} edges.")

    # 4. Generate the interactive HTML visualization
    graph_file = os.path.join(project_dir, "dependency_graph.html")
    create_html_visualization(code_graph, graph_file)

