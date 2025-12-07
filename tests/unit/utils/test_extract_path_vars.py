"""Tests for extract_path_vars function."""

from bisslog_fastapi.utils.extract_path_vars import extract_path_vars


def test_extract_single_var():
    """Test extracting a single path variable."""
    assert extract_path_vars("/items/{item_id}") == ["item_id"]


def test_extract_multiple_vars():
    """Test extracting multiple path variables."""
    assert extract_path_vars("/users/{user_id}/orders/{order_id}") == ["user_id", "order_id"]


def test_extract_vars_with_underscore():
    """Test extracting variables containing underscores."""
    assert extract_path_vars("/files/{file_name}/versions/{version_id}") == ["file_name", "version_id"]


def test_extract_no_vars():
    """Test returning empty list when no variables exist."""
    assert extract_path_vars("/static/assets") == []


def test_extract_empty_path():
    """Test handling empty or None path."""
    assert extract_path_vars("") == []
    assert extract_path_vars(None) == []


def test_extract_ignores_invalid_identifiers():
    """Test ignoring invalid variable names."""
    # Invalid: starts with number, contains hyphen, etc.
    assert extract_path_vars("/x/{1bad}/y/{also-bad}/z") == []
