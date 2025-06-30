import ast
import json

metadata = {"nodes": [], "edges": []}

with open("./data/raw/sample.py", "r") as f:
    tree = ast.parse(f.read(), filename="sample.py")

class MetadataVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_class = None
        self.current_function = None

    def visit_ClassDef(self, node):
        metadata["nodes"].append({
            "name": node.name,
            "type": "class",
            "defined_in": "example.py",
            "line_number": node.lineno,
            "end_line_number": node.end_lineno
        })
        metadata["edges"].append({
            "source": "example.py",
            "target": node.name,
            "relation": "defines"
        })
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        args_list = []
        num_args = len(node.args.args)
        num_defaults = len(node.args.defaults)
        default_start = num_args - num_defaults

        for i, arg in enumerate(node.args.args):
            arg_name = arg.arg
            arg_info = {"name": arg_name}

            if i >= default_start:
                default_index = i - default_start
                default_value = node.args.defaults[default_index]
                if isinstance(default_value, ast.Constant):
                    arg_info["default"] = repr(default_value.value)
                else:
                    arg_info["default"] = ast.dump(default_value, annotate_fields=False)
            else:
                arg_info["default"] = None

            if arg.annotation:
                arg_info["annotation"] = ast.dump(arg.annotation, annotate_fields=False)
            else:
                arg_info["annotation"] = None

            args_list.append(arg_info)

        func_data = {
            "name": node.name,
            "type": "function",
            "defined_in": self.current_class if self.current_class else "example.py",
            "line_number": node.lineno,
            "end_line_number": node.end_lineno,
            "arguments": args_list,
            "calls": [],
            "returns": []
        }
        metadata["nodes"].append(func_data)

        if self.current_class:
            metadata["edges"].append({
                "source": self.current_class,
                "target": node.name,
                "relation": "contains_method"
            })
        else:
            metadata["edges"].append({
                "source": "example.py",
                "target": node.name,
                "relation": "defines"
            })

        prev_function = self.current_function
        self.current_function = node.name

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    called_name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    called_name = child.func.attr
                else:
                    called_name = "unknown"

                func_data["calls"].append(called_name)
                metadata["edges"].append({
                    "source": node.name,
                    "target": called_name,
                    "relation": "calls"
                })

            elif isinstance(child, ast.Return):
                func_data["returns"].append(self._get_expr_repr(child.value))

            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                var_name = child.id
                scope = self.current_function or self.current_class or "example.py"
                metadata["edges"].append({
                    "source": var_name,
                    "target": scope,
                    "relation": "used_in",
                    "line_number": child.lineno
                })

        self.generic_visit(node)
        self.current_function = prev_function

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id

                if isinstance(node.value, ast.Constant):
                    value_type = "constant"
                    value_repr = repr(node.value.value)
                elif isinstance(node.value, ast.List):
                    value_type = "list"
                    value_repr = "[...]"
                elif isinstance(node.value, ast.Dict):
                    value_type = "dict"
                    value_repr = "{...}"
                elif isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        value_type = "instance_or_call"
                        value_repr = f"{node.value.func.id}(...)"
                    elif isinstance(node.value.func, ast.Attribute):
                        value_type = "method_call"
                        value_repr = f"{node.value.func.attr}(...)"
                    else:
                        value_type = "call"
                        value_repr = "call(...)"
                elif isinstance(node.value, ast.Name):
                    value_type = "reference"
                    value_repr = node.value.id
                else:
                    value_type = "complex"
                    value_repr = ast.dump(node.value, annotate_fields=False)

                scope = self.current_function or self.current_class or "example.py"

                var_data = {
                    "name": var_name,
                    "type": "variable",
                    "value_type": value_type,
                    "value_repr": value_repr,
                    "defined_in": scope,
                    "line_number": node.lineno,
                    "end_line_number": getattr(node, "end_lineno", node.lineno)
                }

                metadata["nodes"].append(var_data)

                metadata["edges"].append({
                    "source": scope,
                    "target": var_name,
                    "relation": "defines_variable"
                })

        self.generic_visit(node)

    def _get_expr_repr(self, value):
        if value is None:
            return "None"
        elif isinstance(value, ast.Constant):
            return repr(value.value)
        elif isinstance(value, ast.Name):
            return value.id
        elif isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return f"{value.func.id}(...)"
            elif isinstance(value.func, ast.Attribute):
                return f"{value.func.attr}(...)"
            else:
                return "complex_call(...)"
        else:
            return ast.dump(value, annotate_fields=False)

visitor = MetadataVisitor()
visitor.visit(tree)

with open("metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
