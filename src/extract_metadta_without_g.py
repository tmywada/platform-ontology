import ast
import json

with open("./data/raw/sample.py", "r") as f:
    tree = ast.parse(f.read(), filename="sample.py")

class MetadataVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_class = None
        self.current_function = None
        self.classes_metadata = []
        self.functions_metadata = []
        self.assignments_metadata = []

    def visit_ClassDef(self, node):
        class_info = {
            "class_name": node.name,
            "line": node.lineno,
            "bases": [ast.dump(base, annotate_fields=False) for base in node.bases]
        }

        self.classes_metadata.append(class_info)

        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node):
        args_list = []
        calls_list = []
        vars_used_list = []
        returns_list = []

        num_args = len(node.args.args)
        num_defaults = len(node.args.defaults)
        default_start = num_args - num_defaults

        for i, arg in enumerate(node.args.args):
            arg_info = self._parse_arg_info(arg, i, default_start, node.args.defaults)
            args_list.append(arg_info)

        prev_function = self.current_function
        self.current_function = node.name

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called_func_name = self._get_called_func_name(child)
                calls_list.append({
                    "function": self.current_function,
                    "called": called_func_name,
                    "line": child.lineno
                })

            elif isinstance(child, ast.Return):
                return_repr = self._get_expr_repr(child.value)
                returns_list.append({
                    "function": self.current_function,
                    "return_expr": return_repr,
                    "line": child.lineno
                })

            elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                var_name = child.id
                vars_used_list.append({
                    "function": self.current_function,
                    "variable": var_name,
                    "line": child.lineno
                })

        self.functions_metadata.append({
            "function_name": self.current_function,
            "class": self.current_class,
            "line": node.lineno,
            "args": args_list,
            "calls": calls_list,
            "variables_used": vars_used_list,
            "returns": returns_list
        })

        self.generic_visit(node)
        self.current_function = prev_function

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                value_type, value_repr = self._get_value_info(node.value)

                self.assignments_metadata.append({
                    "class": self.current_class,
                    "function": self.current_function,
                    "variable": var_name,
                    "value_type": value_type,
                    "value_repr": value_repr,
                    "line": node.lineno
                })

        self.generic_visit(node)

    def _parse_arg_info(self, arg, index, default_start, defaults):
        """Parse a function argument's name, default value, and annotation."""
        arg_name = arg.arg
        arg_info = {"name": arg_name}

        if index >= default_start:
            default_index = index - default_start
            default_value = defaults[default_index]
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

        return arg_info

    def _get_value_info(self, value):
        """Get type and string representation of an assigned value."""
        if isinstance(value, ast.Constant):
            return "constant", repr(value.value)
        elif isinstance(value, ast.List):
            return "list", "[...]"
        elif isinstance(value, ast.Dict):
            return "dict", "{...}"
        elif isinstance(value, ast.Call):
            if isinstance(value.func, ast.Name):
                return "instance_or_call", f"{value.func.id}(...)"
            elif isinstance(value.func, ast.Attribute):
                return "method_call", f"{value.func.attr}(...)"
            else:
                return "call", "call(...)"
        elif isinstance(value, ast.Name):
            return "reference", value.id
        else:
            return "complex", ast.dump(value, annotate_fields=False)

    def _get_called_func_name(self, call_node):
        """Get function or method name from a call node."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        else:
            return ast.dump(call_node.func, annotate_fields=False)

    def _get_expr_repr(self, value):
        """Get a simplified string representation of an expression."""
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

# Create and run visitor
visitor = MetadataVisitor()
visitor.visit(tree)

# Prepare and export metadata
output = {
    "classes": visitor.classes_metadata,
    "functions": visitor.functions_metadata,
    "assignments": visitor.assignments_metadata
}

with open("metadata.json", "w") as f:
    json.dump(output, f, indent=2)