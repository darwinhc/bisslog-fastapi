"""Type to string and imports."""

import re
from typing import Any


def type_to_str_and_imports(annotation: Any) -> tuple[str, dict[str, set[str]]]:
    """
    Converts a type annotation object into a string suitable for source code
    and a mapping of modules to symbols that must be imported.

    Handles:
    - Builtins (str, int, bool, ...)
    - typing generics (List[int], Dict[str, Any], Optional[Foo], ...)
    - User-defined classes from other modules.

    Parameters
    ----------
    annotation : Any
        The annotation object.

    Returns
    -------
    Tuple[str, Dict[str, Set[str]]]
        - The type as a Python-syntax string.
        - A dict of imports (module -> set(symbols)).
    """
    imports: dict[str, set[str]] = {}

    if annotation is None:
        return "Any", {"typing": {"Any"}}

    module = getattr(annotation, "__module__", None)
    name = getattr(annotation, "__name__", None)

    if module == "builtins" and name is not None:
        return name, imports

    if module == "typing":
        s = str(annotation)
        s_clean = s.replace("typing.", "")
        tokens = set(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\b", s_clean))
        if tokens:
            imports["typing"] = tokens
        return s_clean, imports

    origin = getattr(annotation, "__origin__", None)
    if origin is not None:
        origin_name = getattr(origin, "__name__", None) or str(origin)
        args = getattr(annotation, "__args__", ())
        args_str_parts = []
        for arg in args:
            arg_str, extra_imp = type_to_str_and_imports(arg)
            for mod, names in extra_imp.items():
                imports.setdefault(mod, set()).update(names)
            args_str_parts.append(arg_str)

        if origin is list:
            imports.setdefault("typing", set()).add("List")
            return f"List[{', '.join(args_str_parts)}]", imports
        if origin is dict:
            imports.setdefault("typing", set()).add("Dict")
            return f"Dict[{', '.join(args_str_parts)}]", imports
        if origin is set:
            imports.setdefault("typing", set()).add("Set")
            return f"Set[{', '.join(args_str_parts)}]", imports

        imports.setdefault("typing", set()).add(origin_name)
        return f"{origin_name}[{', '.join(args_str_parts)}]", imports

    if module and name:
        imports[module] = {name}
        return name, imports

    return "Any", {"typing": {"Any"}}
