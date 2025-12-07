"""
Unit tests for the ``type_to_str_and_imports`` utility.

These tests validate the conversion of different kinds of Python type
annotations into string representations and the associated import map.
"""

import sys
import typing as t
import pytest
from typing import List, Dict, Set

from bisslog_fastapi.utils.type_to_str_and_imports import type_to_str_and_imports


def test_none_returns_any_and_typing_any_import():
    """Test that None annotation results in Any type and typing.Any import."""
    type_str, imports = type_to_str_and_imports(None)

    assert type_str == "Any"
    assert imports == {"typing": {"Any"}}


def test_builtin_type_int_has_no_imports():
    """Test that built-in type int requires no additional imports."""
    type_str, imports = type_to_str_and_imports(int)

    assert type_str == "int"
    assert imports == {}


def test_builtin_type_str_has_no_imports():
    """Test that built-in type str requires no additional imports."""
    type_str, imports = type_to_str_and_imports(str)

    assert type_str == "str"
    assert imports == {}


def test_typing_any_from_typing_module():
    """Test that typing.Any is converted to string Any with proper import."""
    type_str, imports = type_to_str_and_imports(t.Any)

    # str(typing.Any) -> "typing.Any" -> "Any"
    assert type_str == "Any"
    assert imports == {"typing": {"Any"}}


def test_typing_generic_list_int_from_typing():
    """Test that typing.List[int] is handled via typing module branch."""
    annotation = t.List[int]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "List[int]"
    assert "typing" in imports
    assert "List" in imports["typing"]
    # Built-in types should not appear in typing imports
    assert "int" not in imports["typing"]


def test_typing_generic_dict_str_int():
    """Test that typing.Dict[str, int] is converted correctly."""
    annotation = t.Dict[str, int]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "Dict[str, int]"
    assert imports == {"typing": {"Dict"}}


def test_typing_optional_str():
    """Test that typing.Optional[str] is converted correctly."""
    annotation = t.Optional[str]

    type_str, imports = type_to_str_and_imports(annotation)

    # str(Optional[str]) -> "Union[str, None]" or "Optional[str]"
    # Python runtime typically flattens Optional[T] to Union[T, None]
    assert type_str == "Union[str, None]"
    assert "typing" in imports
    assert "Union" in imports["typing"]


@pytest.mark.skipif(sys.version_info < (3, 9), reason="PEP 585 requires Python 3.9+")
def test_pep585_list_int_normalized_to_typing_list():
    """Test that list[int] (PEP 585) is normalized to List[int] with typing import."""
    annotation = list[int]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "List[int]"
    assert imports == {"typing": {"List"}}


def test_list_int_normalized_to_typing_list():
    """Test that List[int]"""
    annotation = List[int]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "List[int]"
    assert imports == {"typing": {"List"}}


@pytest.mark.skipif(sys.version_info < (3, 9), reason="PEP 585 requires Python 3.9+")
def test_pep585_dict_str_int_normalized_to_typing_dict():
    """Test that dict[str, int] (PEP 585) is normalized to Dict[str, int]."""
    annotation = dict[str, int]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "Dict[str, int]"
    assert imports == {"typing": {"Dict"}}


def test_dict_str_int_to_typing_dict():
    """Test that Dict[str, int]."""
    annotation = Dict[str, int]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "Dict[str, int]"
    assert imports == {"typing": {"Dict"}}


@pytest.mark.skipif(sys.version_info < (3, 9), reason="PEP 585 requires Python 3.9+")
def test_pep585_set_str_normalized_to_typing_set():
    """Test that set[str] (PEP 585) is normalized to Set[str]."""
    annotation = set[str]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "Set[str]"
    assert imports == {"typing": {"Set"}}


def test_set_str():
    """Test that Set[str]."""
    annotation = Set[str]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "Set[str]"
    assert imports == {"typing": {"Set"}}


@pytest.mark.skipif(sys.version_info < (3, 9), reason="PEP 585 requires Python 3.9+")
def test_nested_pep585_generics_and_user_defined_class():
    """Test nested generics and user-defined types with import merging.    The annotation list[dict[str, Foo]] should be normalized to
    List[Dict[str, Foo]] and produce imports for typing.List, typing.Dict,
    and the module where Foo is defined.
    """

    class Foo:
        """Dummy class for testing user-defined type imports."""

        def __init__(self) -> None:
            pass

    annotation = list[dict[str, Foo]]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "List[Dict[str, Foo]]"

    assert "typing" in imports
    assert "List" in imports["typing"]
    assert "Dict" in imports["typing"]

    foo_module = Foo.__module__
    assert foo_module in imports
    assert "Foo" in imports[foo_module]


def test_nested_generics_and_user_defined_class():
    """Test nested generics and user-defined types with import merging."""

    class Foo:
        """Dummy class for testing user-defined type imports."""

        def __init__(self) -> None:
            pass

    annotation = List[Dict[str, Foo]]

    type_str, imports = type_to_str_and_imports(annotation)

    assert type_str == "List[Dict[str, Foo]]"

    assert "typing" in imports
    assert "List" in imports["typing"]
    assert "Dict" in imports["typing"]

    foo_module = Foo.__module__
    assert foo_module in imports
    assert "Foo" in imports[foo_module]


def test_user_defined_class_import():
    """Test that a user-defined class is imported from its module."""

    class MyModel:
        """Dummy model class for testing."""

        def __init__(self) -> None:
            pass

    type_str, imports = type_to_str_and_imports(MyModel)

    assert type_str == "MyModel"

    mod = MyModel.__module__
    assert imports == {mod: {"MyModel"}}


def test_fallback_to_any_for_non_type_object():
    """Test that a non-type object falls back to Any with typing.Any import."""
    obj = object()

    type_str, imports = type_to_str_and_imports(obj)

    assert type_str == "Any"
    assert imports == {"typing": {"Any"}}
