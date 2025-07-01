import ast
import json
import os
import networkx as nx
from pyvis.network import Network

# ==============================================================================
# METADATA GENERATION SCRIPT (from the Canvas)
# This part is included to make the example fully runnable.
# In a real project, you might import this from another file.
# ==============================================================================

def generate_metadata(file_path: str) -> dict:
    """
    Parses a Python file and extracts metadata about its classes, functions,
    and assignments using the ast module.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: The file at {file_path} was not found.")
        return {}
    except Exception as e:
        print(f"Error reading file: {e}")
        return {}

    try:
        tree = ast.parse(source_code, filename=file_path)
    except SyntaxError as e:
        print(f"Error parsing the Python file: {e}")
        return {}

    visitor = MetadataVisitor()
    visitor.visit(tree)

    return {
        "imports": visitor.imports_metadata,
        "classes": visitor.classes_metadata,
        "functions": visitor.functions_metadata,
        "assignments": visitor.assignments_metadata
    }

class MetadataVisitor(ast.NodeVisitor):
    """
    An AST visitor that collects metadata about classes, functions, and assignments.
    """
    def __init__(self):
        self.current_class = None
        self.current_function_meta = None
        self.imports_metadata = []
        self.classes_metadata = []
        self.functions_metadata = []
        self.assignments_metadata = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports_metadata.append({
                "type": "import", "module": alias.name, "alias": alias.asname,
                "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', node.lineno)
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ''
        for alias in node.names:
            self.imports_metadata.append({
                "type": "from_import", "module": module, "name": alias.name, "alias": alias.asname,
                "level": node.level, "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', node.lineno)
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_info = {
            "class_name": node.name, "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', None),
            "bases": [self._get_expr_repr(base) for base in node.bases],
            "decorators": [self._get_expr_repr(d) for d in node.decorator_list], "docstring": ast.get_docstring(node)
        }
        self.classes_metadata.append(class_info)
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        function_info = {
            "function_name": node.name, "class": self.current_class, "start_line": node.lineno,
            "end_line": getattr(node, 'end_lineno', None), "docstring": ast.get_docstring(node),
            "decorators": [self._get_expr_repr(d) for d in node.decorator_list],
            "arguments": self._parse_function_args(node.args), "calls": [], "variables_used": [], "returns": []
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
                    "class": self.current_function_meta['function_name'] if self.current_function_meta else None,
                    "function": self.current_function_meta['function_name'] if self.current_function_meta else None,
                    "variable": target.id, "value_type": value_type, "value_representation": value_repr,
                    "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', None)
                })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if self.current_function_meta:
            self.current_function_meta["calls"].append({
                "called": self._get_called_func_name(node), "start_line": node.lineno,
                "end_line": getattr(node, 'end_lineno', None)
            })
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        if self.current_function_meta:
            self.current_function_meta["returns"].append({
                "return_expression": self._get_expr_repr(node.value), "start_line": node.lineno,
                "end_line": getattr(node, 'end_lineno', None)
            })
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if self.current_function_meta and isinstance(node.ctx, ast.Load):
            var_name = node.id
            if not any(d['variable'] == var_name for d in self.current_function_meta["variables_used"]):
                self.current_function_meta["variables_used"].append({
                    "variable": var_name, "start_line": node.lineno, "end_line": getattr(node, 'end_lineno', None)
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

# ==============================================================================
# NETWORKX GRAPH CREATION
# ==============================================================================

def create_graph_from_metadata(metadata: dict) -> nx.DiGraph:
    """
    Builds a NetworkX DiGraph from the metadata dictionary.
    """
    G = nx.DiGraph()
    
    # Add nodes for classes
    for cls in metadata.get("classes", []):
        G.add_node(cls["class_name"], node_type="class", **cls)

    # Add nodes for functions and methods
    for func in metadata.get("functions", []):
        node_name = f"{func['class']}.{func['function_name']}" if func["class"] else func["function_name"]
        G.add_node(node_name, node_type="function", **func)

    # Add edges for class inheritance
    for cls in metadata.get("classes", []):
        for base in cls.get("bases", []):
            if G.has_node(base):
                G.add_edge(cls["class_name"], base, edge_type="inherits")

    # Add edges for function calls, decorators, etc.
    for func in metadata.get("functions", []):
        caller_node = f"{func['class']}.{func['function_name']}" if func["class"] else func["function_name"]
        
        for decorator in func.get("decorators", []):
            if not G.has_node(decorator):
                 G.add_node(decorator, node_type="decorator")
            G.add_edge(decorator, caller_node, edge_type="decorates")
        
        for call in func.get("calls", []):
            callee_node = call["called"]
            if callee_node.startswith("self.") and func["class"]:
                callee_node = f"{func['class']}{callee_node[4:]}"
            
            if not G.has_node(callee_node):
                G.add_node(callee_node, node_type="external_or_builtin")
            
            G.add_edge(caller_node, callee_node, edge_type="calls")

    return G

# ==============================================================================
# PYVIS VISUALIZATION
# ==============================================================================

def create_pyvis_visualization(graph: nx.DiGraph, output_path: str):
    """
    Creates an interactive HTML graph visualization using pyvis.
    Node tooltips show detailed metadata on hover.
    """
    net = Network(height="800px", width="100%", bgcolor="#222222", font_color="white", notebook=False, directed=True)

    # Add nodes with detailed tooltips
    for node_id, node_data in graph.nodes(data=True):
        node_type = node_data.get("node_type", "external_or_builtin")
        
        # --- Build the hover tooltip (title) using HTML ---
        title_html = f"<b>{node_id}</b><br>--------------------<br><b>Type:</b> {node_type}"
        if node_type == "class":
            title_html += f"<br><b>Lines:</b> {node_data.get('start_line')} - {node_data.get('end_line')}"
            if node_data.get('bases'): title_html += f"<br><b>Inherits:</b> {', '.join(node_data['bases'])}"
            if node_data.get('decorators'): title_html += f"<br><b>Decorators:</b> {', '.join(node_data['decorators'])}"
            if node_data.get('docstring'): title_html += f"<br><br><i>{node_data['docstring']}</i>"
        
        elif node_type == "function":
            title_html += f"<br><b>Lines:</b> {node_data.get('start_line')} - {node_data.get('end_line')}"
            if node_data.get('decorators'): title_html += f"<br><b>Decorators:</b> {', '.join(node_data['decorators'])}"
            if node_data.get('arguments'):
                args_str = ', '.join([f"{arg['name']}" for arg in node_data['arguments']])
                title_html += f"<br><b>Arguments:</b> {args_str}"
            if node_data.get('docstring'): title_html += f"<br><br><i>{node_data['docstring']}</i>"

        # --- Set node color based on type ---
        color = "lightcoral" # Default for external/builtin
        if node_type == "class": color = "skyblue"
        elif node_type == "function": color = "lightgreen"
        elif node_type == "decorator": color = "plum"

        net.add_node(node_id, label=node_id, title=title_html, color=color)

    # Add edges with tooltips
    for source, target, data in graph.edges(data=True):
        edge_type = data.get('edge_type', '')
        net.add_edge(source, target, title=edge_type)

    net.show_buttons(filter_=['physics'])
    net.save_graph(output_path)
    print(f"✅ Interactive graph visualization saved to {output_path}")


# --- Main Execution ---
if __name__ == "__main__":
    # Create a dummy file for demonstration purposes
    dummy_code = """
import os
import sys as system
from collections import Counter

def my_class_decorator(cls):
    '''A decorator for classes.'''
    return cls
    
def my_func_decorator(func):
    '''A decorator for functions.'''
    return func

@my_class_decorator
class MyDataProcessor:
    \"\"\"A sample class to process data.\"\"\"
    VERSION = "1.0"

    def __init__(self, data_source: str):
        self.source = data_source
        self.data = None

    @staticmethod
    def load_data(limit: int = 100):
        \"\"\"Loads data up to a certain limit.\"\"\"
        print("Starting data load")
        return [i for i in range(limit)]

@my_func_decorator
def standalone_func(x, y=5):
    '''A standalone function.'''
    proc = MyDataProcessor("local")
    data = proc.load_data(50)
    return x + y + len(data)
"""
    # Setup paths
    output_dir = "generated_output"
    os.makedirs(output_dir, exist_ok=True)
    file_to_analyze = os.path.join(output_dir, "sample_for_graph.py")
    metadata_file = os.path.join(output_dir, "metadata_for_graph.json")
    graph_file = os.path.join(output_dir, "dependency_graph.html") # Changed to .html

    # Write the sample code to a file
    with open(file_to_analyze, "w", encoding="utf-8") as f:
        f.write(dummy_code)

    # 1. Generate metadata from the source file
    metadata = generate_metadata(file_to_analyze)
    if metadata:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        print(f"✅ Metadata generated and saved to {metadata_file}")

        # 2. Create a graph from the metadata
        code_graph = create_graph_from_metadata(metadata)
        print(f"✅ NetworkX graph created with {code_graph.number_of_nodes()} nodes and {code_graph.number_of_edges()} edges.")

        # 3. Draw the graph and save it as an interactive HTML file
        try:
            create_pyvis_visualization(code_graph, graph_file)
        except ImportError:
            print("\n⚠️  Could not generate graph image. Please install pyvis:")
            print("   pip install pyvis")
        except Exception as e:
            print(f"\nAn error occurred during graph drawing: {e}")

