import ast

class MetadataVisitor(ast.NodeVisitor):
    """
    A class that visits an AST and extracts structured metadata about the code.
    This version adds explicit 'type' keys and handles nested function context.
    """
    def __init__(self):
        self.current_class = None
        self.current_function_context = None
        self.imports = []
        self.classes = []
        self.functions = []
        self.assignments = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append({
                "type": "import", 
                "module": alias.name, 
                "alias": alias.asname, 
                "start_line": node.lineno, 
                "end_line": getattr(node, 'end_lineno', node.lineno)
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ''
        for alias in node.names:
            self.imports.append({
                "type": "from_import", 
                "module": module, 
                "name": alias.name, 
                "alias": alias.asname,
                "level": node.level, 
                "start_line": node.lineno,
                "end_line": getattr(node, 'end_lineno', node.lineno)
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_info = {
            "type": "class",
            "class_name": node.name, 
            "start_line": node.lineno,
            "end_line": getattr(node, 'end_lineno', None),
            "bases": [self._get_expr_repr(base) for base in node.bases],
            "decorators": [self._get_expr_repr(d) for d in node.decorator_list], 
            "docstring": ast.get_docstring(node)
        }
        self.classes.append(class_info)
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        parent_func_name = self.current_function_context['function_name'] if self.current_function_context else None
        function_info = {
            "type": "function",
            "function_name": node.name, 
            "class": self.current_class,
            "parent_function": parent_func_name,
            "start_line": node.lineno,
            "end_line": getattr(node, 'end_lineno', None), 
            "docstring": ast.get_docstring(node),
            "decorators": [self._get_expr_repr(d) for d in node.decorator_list],
            "arguments": self._parse_function_args(node.args), 
            "calls": [],
            "variables_used": [],
            "returns": []
        }
        self.functions.append(function_info)
        prev_function_context = self.current_function_context
        self.current_function_context = function_info
        self.generic_visit(node)
        self.current_function_context = prev_function_context

    def visit_Assign(self, node: ast.Assign):
        value_type, value_repr = self._get_value_info(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.assignments.append({
                    "type": "assignment",
                    "class": self.current_class,
                    "function": self.current_function_context['function_name'] if self.current_function_context else None,
                    "variable": target.id, 
                    "value_type": value_type, 
                    "value_representation": value_repr,
                    "start_line": node.lineno, 
                    "end_line": getattr(node, 'end_lineno', None)
                })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if self.current_function_context:
            self.current_function_context["calls"].append({
                "called": self._get_called_func_name(node), 
                "start_line": node.lineno,
                "end_line": getattr(node, 'end_lineno', None)
            })
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return):
        if self.current_function_context:
            self.current_function_context["returns"].append({
                "return_expression": self._get_expr_repr(node.value), 
                "start_line": node.lineno,
                "end_line": getattr(node, 'end_lineno', None)
            })
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if self.current_function_context and isinstance(node.ctx, ast.Load):
            var_name = node.id
            if not any(d['variable'] == var_name for d in self.current_function_context["variables_used"]):
                self.current_function_context["variables_used"].append({
                    "variable": var_name,
                    "start_line": node.lineno, 
                    "end_line": getattr(node, 'end_lineno', None)
                })

    def _parse_function_args(self, args_node: ast.arguments) -> list:
        arguments_list = []
        num_defaults = len(args_node.defaults)
        default_start_index = len(args_node.args) - num_defaults
        for i, arg in enumerate(args_node.args):
            arg_info = {
                "name": arg.arg,
                "default": None,
                "data_type": self._get_expr_repr(arg.annotation)
            }
            if i >= default_start_index:
                arg_info["default"] = self._get_expr_repr(args_node.defaults[i - default_start_index])
            arguments_list.append(arg_info)
        for i, arg in enumerate(args_node.kwonlyargs):
            arguments_list.append({
                "name": arg.arg,
                "default": self._get_expr_repr(args_node.kw_defaults[i]),
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


def generate_metadata(source_code: str) -> dict:
    tree = ast.parse(source_code)
    visitor = MetadataVisitor()
    visitor.visit(tree)
    return {
        "imports": visitor.imports,
        "classes": visitor.classes,
        "functions": visitor.functions,
        "assignments": visitor.assignments
    }


if __name__ == "__main__":
    file_path = './tests/data/sample.py'
    with open(file_path, 'r') as f:
        source_code = f.read()
    metadata = generate_metadata(source_code)
    print(metadata)
    