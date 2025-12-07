"""Tests for get_params_type."""
from bisslog_fastapi.utils.get_param_type import get_param_type


def test_get_params_type():
    """Test get_params_type."""

    def fn(a: int, b: str):
        pass

    assert get_param_type(fn, "a") == int
    assert get_param_type(fn, "b") == str
    assert get_param_type(fn, "c") is None

    class A:
        def __call__(self, some: int, some_str: str = "abc"):
            pass

    assert get_param_type(A(), "some") == int
    assert get_param_type(A(), "other") is None
    assert get_param_type(A(), "some_str") == str


def test_get_params_type_empty_params():
    """Test get_params_type with empty params."""

    def fn():
        pass
    assert get_param_type(fn, "a") is None

    class A:
        def __call__(self):
            pass
    assert get_param_type(A(), "a") is None
    assert get_param_type(lambda: None, "a") is None
