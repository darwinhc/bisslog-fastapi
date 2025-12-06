"""Infer a FastAPI response_model from a use case return annotation."""
from dataclasses import is_dataclass
from typing import Optional, get_type_hints, Any, get_origin, get_args, Union

from pydantic import BaseModel
from pydantic.dataclasses import dataclass
from starlette.responses import Response


def _safe_type_hints(target) -> dict:
    """Return type hints for a target or an empty dict if they can't be resolved."""
    try:
        return get_type_hints(target)
    except (
        NameError, TypeError, AttributeError, ImportError,
        ModuleNotFoundError, SyntaxError, ValueError,
    ):
        return {}


def _get_return_annotation(fn) -> Optional[type]:
    """Try to obtain the return annotation from a function or its __call__."""
    hints = _safe_type_hints(fn)
    if not hints and hasattr(fn, "__call__"):
        hints = _safe_type_hints(fn.__call__)
    return hints.get("return")


def _is_disallowed_return(ret: type) -> bool:
    """
    Return True if this annotation should NOT produce a response_model.

    Disallow:
    - None / Any
    - Response subclasses
    - Unions (Any, None, Response, etc.)
    """
    if ret is None or ret is Any:
        return True

    if isinstance(ret, type) and issubclass(ret, Response):
        return True

    origin = get_origin(ret)
    args = get_args(ret)

    if origin is Union:
        for arg in args:
            if arg is Any or arg is type(None):
                return True
            if isinstance(arg, type) and issubclass(arg, Response):
                return True
        return True

    return False


def _collection_returns_model(ret: type) -> bool:
    """
    Return True if ret is a list/tuple/set/dict whose inner type is a BaseModel.
    """
    origin = get_origin(ret)
    args = get_args(ret)

    if origin in (list, tuple, set):
        inner = args[0] if args else Any
        return isinstance(inner, type) and issubclass(inner, BaseModel)

    if origin is dict:
        key_type, value_type = (args + (Any, Any))[:2]
        if key_type is not str:
            return False
        return isinstance(value_type, type) and issubclass(value_type, BaseModel)

    return False


def _normalize_dataclass(ret: type) -> type:
    """
    If ret is an stdlib-dataclass, convert it to a pydantic dataclass
    (only if not already converted).
    """
    if not is_dataclass(ret):
        return ret
    if getattr(ret, "__pydantic_validator__", None) is not None:
        return ret
    return dataclass(ret)


def infer_response_model(fn) -> Optional[type]:
    """
    Return a FastAPI-compatible response_model from the use case return annotation.
    If invalid or ambiguous, return None, so FastAPI won't try to generate a schema.
    """
    ret = _get_return_annotation(fn)
    if ret is None or _is_disallowed_return(ret):
        return None

    origin = get_origin(ret)

    result: Optional[type] = None

    if isinstance(ret, type) and issubclass(ret, BaseModel):
        result = ret
    elif _collection_returns_model(ret):
        result = ret
    elif origin is None and is_dataclass(ret):
        result = _normalize_dataclass(ret)

    return result
