"""Get parameter type from function"""
import inspect

from typing import Any, Optional, get_type_hints


def get_param_type(callable_obj: Any, param_name: str) -> Optional[type]:
    """
    Returns the type annotation of a parameter in a callable, if present.

    Parameters
    ----------
    callable_obj : Any
        The callable (function, method, __call__, etc.) to inspect.
    param_name : str
        The name of the parameter whose type is requested.

    Returns
    -------
    Optional[type]
        The annotated type, or None if not annotated or missing.
    """
    sig = inspect.signature(callable_obj)
    p = sig.parameters.get(param_name)
    if p is None:
        return None
    try:
        hints = get_type_hints(callable_obj)
    except (NameError, TypeError, AttributeError, ImportError,
            ModuleNotFoundError, SyntaxError, ValueError):
        hints = {}
    ann = hints.get(param_name, p.annotation)
    if ann is inspect._empty:  # pylint: disable=protected-access
        return None
    return ann
