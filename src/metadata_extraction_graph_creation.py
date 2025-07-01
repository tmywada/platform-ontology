import ast
import json
import os
import networkx as nx
import matplotlib.pyplot as plt

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
                    "class": self.current_class,
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

    Args:
        metadata: The dictionary generated by the MetadataVisitor.

    Returns:
        A NetworkX DiGraph representing the code structure.
    """
    G = nx.DiGraph()

    # --- Step 1: Add nodes for all entities ---

    # Add nodes for classes
    for cls in metadata.get("classes", []):
        G.add_node(cls["class_name"], node_type="class", **cls)

    # Add nodes for functions and methods
    for func in metadata.get("functions", []):
        # Create a unique name for methods, e.g., "MyClass.my_method"
        node_name = f"{func['class']}.{func['function_name']}" if func["class"] else func["function_name"]
        G.add_node(node_name, node_type="function", **func)

    # --- Step 2: Add edges for relationships ---

    # Add edges for class inheritance
    for cls in metadata.get("classes", []):
        for base in cls.get("bases", []):
            if G.has_node(base): # Only add edge if the base class is in the graph
                G.add_edge(cls["class_name"], base, edge_type="inherits")

    # Add edges for function calls, decorators, etc.
    for func in metadata.get("functions", []):
        caller_node = f"{func['class']}.{func['function_name']}" if func["class"] else func["function_name"]
        
        # Add edges for decorators
        for decorator in func.get("decorators", []):
            G.add_edge(decorator, caller_node, edge_type="decorates")
        
        # Add edges for function calls
        for call in func.get("calls", []):
            callee_node = call["called"]
            # Simple name resolution: if it's a method call on self, prepend class name
            if callee_node.startswith("self.") and func["class"]:
                callee_node = f"{func['class']}{callee_node[4:]}"
            
            # Add node for callee if it doesn't exist (e.g., built-in 'print')
            if not G.has_node(callee_node):
                G.add_node(callee_node, node_type="external_or_builtin")
            
            G.add_edge(caller_node, callee_node, edge_type="calls")

    return G

def draw_graph(graph: nx.DiGraph, output_path: str):
    """
    Draws the graph using matplotlib and saves it to a file.
    """
    plt.figure(figsize=(18, 18))
    
    # Use a layout that spreads nodes out
    pos = nx.spring_layout(graph, k=0.9, iterations=50)

    # Color nodes by their type
    node_colors = []
    for node in graph.nodes(data=True):
        node_type = node[1].get("node_type", "external_or_builtin")
        if node_type == "class":
            node_colors.append("skyblue")
        elif node_type == "function":
            node_colors.append("lightgreen")
        else:
            node_colors.append("lightcoral")

    nx.draw(graph, pos, with_labels=True, node_size=3000, node_color=node_colors, 
            font_size=10, font_weight="bold", arrowsize=20)
    
    # Draw edge labels
    edge_labels = nx.get_edge_attributes(graph, 'edge_type')
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_color='red')

    plt.title("Code Dependency Graph", size=20)
    plt.savefig(output_path)
    plt.close()
    print(f"✅ Graph visualization saved to {output_path}")


# --- Main Execution ---
if __name__ == "__main__":
    # Create a dummy file for demonstration purposes
    dummy_code = """
import os
import sys as system
from collections import Counter

def my_class_decorator(cls):
    return cls
    
def my_func_decorator(func):
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
    proc = MyDataProcessor("local")
    data = proc.load_data(50)
    return x + y + len(data)
"""
    # Setup paths
    output_dir = "generated_output"
    os.makedirs(output_dir, exist_ok=True)
    file_to_analyze = os.path.join(output_dir, "sample_for_graph.py")
    metadata_file = os.path.join(output_dir, "metadata_for_graph.json")
    graph_file = os.path.join(output_dir, "dependency_graph.png")

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

        # 3. Draw the graph and save it as an image
        try:
            draw_graph(code_graph, graph_file)
        except ImportError:
            print("\n⚠️  Could not generate graph image. Please install matplotlib:")
            print("   pip install matplotlib")
        except Exception as e:
            print(f"\nAn error occurred during graph drawing: {e}")

