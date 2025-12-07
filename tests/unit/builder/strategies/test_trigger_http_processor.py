"""
Unit tests for TriggerHttpProcessor.
"""
from typing import Any, Dict
from unittest.mock import patch

import pytest
from bisslog_schema.schema import TriggerHttp
from bisslog_schema.use_case_code_inspector.use_case_code_metadata import UseCaseCodeInfo

from bisslog_fastapi.builder.strategies.trigger_http_processor import TriggerHttpProcessor


@pytest.fixture
def processor():
    return TriggerHttpProcessor()


def test_extract_path_param_names_from_path(processor):
    """Test extraction of path parameters from a URL path."""
    assert processor._extract_path_param_names_from_path("/users/{uid}") == ("uid",)
    assert processor._extract_path_param_names_from_path("/company/{org_id}/data/{schema}") == (
        "org_id", "schema")
    assert processor._extract_path_param_names_from_path("/static/path") == ()
    assert processor._extract_path_param_names_from_path(None) == ()


def test_process_simple_get_no_mapper(processor):
    """Test processing a simple GET request with path parameters and no mapper."""

    # Setup
    trigger = TriggerHttp(path="/users/{uid}", method="GET")
    uc_info = UseCaseCodeInfo(name="my_uc", docs="docs", module="mod", is_coroutine=False)

    def my_use_case(uid: str) -> Dict[str, Any]:
        return {"uid": uid}

    # Act
    result = processor(
        use_case_key="get_user",
        uc_var_name="uc_obj",
        uc_info=uc_info,
        trigger_info=trigger,
        callable_obj=my_use_case,
        identifier=1,
        use_case_description="Get user by ID"
    )

    # Assert
    assert "fastapi" in result.importing
    assert "Path" in result.importing["fastapi"]

    code = result.body
    assert '@app.get("/users/{uid}", description="Get user by ID")' in code
    assert "def get_user_handler_1(uid: str = Path(...)" in code
    assert "body: Dict[str, Any] = Body(default={})" in code
    assert '_kwargs["uid"] = uid' in code
    assert "result = uc_obj(**_kwargs)" in code


def test_process_async_post_with_body_mapping(processor):
    """Test processing an async POST request with body mapping."""

    # Setup
    trigger = TriggerHttp(
        path="/items",
        method="POST",
        mapper={"body": "params"}
    )
    uc_info = UseCaseCodeInfo(name="my_uc", docs="docs", module="mod", is_coroutine=True)

    class ItemModel:
        name: str

    async def create_item(params: ItemModel) -> int:
        return 1

    # Act
    result = processor(
        use_case_key="create_item",
        uc_var_name="uc_obj",
        uc_info=uc_info,
        trigger_info=trigger,
        callable_obj=create_item,
        identifier=2
    )

    # Assert
    assert "fastapi" in result.importing
    assert "Body" in result.importing["fastapi"]

    code = result.body
    assert '@app.post("/items")' in code
    assert "async def create_item_handler_2(" in code
    # Check body param
    assert "params: ItemModel = Body(...)" in code

    # Check mapping
    assert '_kwargs["params"] = params' in code
    assert "result = await uc_obj(**_kwargs)" in code


def test_process_complex_mapping(processor):
    """Test processing with mapping from various sources (path, query, header)."""

    # Setup
    trigger = TriggerHttp(
        path="/data/{did}",
        method="PUT",
        mapper={
            "path_query.did": "doc_id",
            "params.version": "v",
            "headers.auth": "token"
        }
    )
    uc_info = UseCaseCodeInfo(name="my_uc", docs="docs", module="mod", is_coroutine=False)

    def update_doc(doc_id: str, v: int, token: str) -> None:
        pass

    # Act
    result = processor(
        use_case_key="update_doc",
        uc_var_name="uc_inst",
        uc_info=uc_info,
        trigger_info=trigger,
        callable_obj=update_doc,
        identifier=3
    )

    # Assert
    code = result.body

    # Path param mapped
    assert "did: str = Path(...)" in code
    assert '_kwargs["doc_id"] = did' in code

    # Query param mapped
    assert "version: int = Query(None, alias='version')" in code
    assert '_kwargs["v"] = version' in code

    # Header param mapped
    assert "auth: str = Header(..., alias='auth')" in code
    assert '_kwargs["token"] = auth' in code


class MyResponse:
    pass


MyResponse.__module__ = "my.custom.module"


def test_infer_response_model_import(processor):
    """Test that return type annotation is correctly processed and imported."""

    def my_func() -> MyResponse:
        return MyResponse()

    trigger = TriggerHttp(path="/foo", method="GET")
    uc_info = UseCaseCodeInfo(name="my_uc", docs="docs", module="mod", is_coroutine=False)

    with patch(
            "bisslog_fastapi.builder.strategies.trigger_http_processor.infer_response_model") as mock_infer:
        mock_infer.return_value = MyResponse

        result = processor(
            use_case_key="uc",
            uc_var_name="uc",
            uc_info=uc_info,
            trigger_info=trigger,
            callable_obj=my_func,
            identifier=4
        )

    # Check imports
    mod = MyResponse.__module__
    assert mod in result.importing
    assert "MyResponse" in result.importing[mod]

    # Check return annotation in sig
    assert ") -> MyResponse:" in result.body


def test_process_bulk_mapping_and_fallbacks(processor):
    """Test bulk mapping of headers/params and type annotation fallbacks."""
    
    # Setup
    trigger = TriggerHttp(
        path="/bulk", 
        method="GET",
        mapper={
            "params": "q_dict",    # params -> q_dict (Dict[str, Any])
            "headers": "h_dict"    # headers -> h_dict (Dict[str, str])
        }
    )
    uc_info = UseCaseCodeInfo(name="uc_bulk", docs="docs", module="mod", is_coroutine=False)
    
    # Use case with NO annotations to test fallbacks
    def bulk_uc(q_dict, h_dict):
        pass
        
    # Act
    result = processor(
        use_case_key="bulk_uc",
        uc_var_name="uc",
        uc_info=uc_info,
        trigger_info=trigger,
        callable_obj=bulk_uc,
        identifier=5
    )
    
    code = result.body
    
    # Check Imports
    assert "typing" in result.importing
    assert "Dict" in result.importing["typing"]
    assert "Any" in result.importing["typing"]
    
    # Check Signature
    # q_dict fallback: Dict[str, Any]
    assert "q_dict: Dict[str, Any] = Depends(_all_query_params)" in code
    # h_dict fallback: Dict[str, str]
    assert "h_dict: Dict[str, str] = Depends(_all_headers)" in code
    
    # Check Mapping logic
    assert '_kwargs["q_dict"] = q_dict' in code
    assert '_kwargs["h_dict"] = h_dict' in code


def test_process_metadata_injection(processor):
    """Test that name and description are injected into the route decorator."""
    
    trigger = TriggerHttp(path="/meta", method="POST")
    uc_info = UseCaseCodeInfo(name="meta_uc", docs="docs", module="mod", is_coroutine=False)
    
    def meta_uc(): pass
    
    result = processor(
        use_case_key="meta_uc",
        uc_var_name="uc",
        uc_info=uc_info,
        trigger_info=trigger,
        callable_obj=meta_uc,
        identifier=6,
        use_case_name="My Custom Name",
        use_case_description="My Custom Description"
    )
    
    code = result.body
    # Check decorator args
    assert 'name="My Custom Name"' in code
    assert 'description="My Custom Description"' in code
    assert '@app.post("/meta"' in code
