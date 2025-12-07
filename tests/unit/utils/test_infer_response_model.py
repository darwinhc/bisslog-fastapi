import sys
from dataclasses import dataclass as std_dataclass, is_dataclass
import pytest
from typing import Any, Union, List, Dict, get_origin, get_args

from pydantic import BaseModel
from starlette.responses import Response

from bisslog_fastapi.utils import infer_response_model


class UserModel(BaseModel):
    id: int
    name: str


class CustomResponse(Response):
    pass


def test_safe_type_hints_function_ok():
    def fn(x: int) -> str:
        return str(x)

    hints = infer_response_model._safe_type_hints(fn)
    assert hints["x"] is int
    assert hints["return"] is str


def test_safe_type_hints_fallback_on_error(monkeypatch):
    def bad_get_type_hints(_):
        raise TypeError("boom")

    monkeypatch.setattr(infer_response_model, "get_type_hints", bad_get_type_hints)

    def fn(x: int) -> str:
        return str(x)

    hints = infer_response_model._safe_type_hints(fn)
    assert hints == {}


def test_get_return_annotation_from_function():
    def fn() -> int:
        return 1

    assert infer_response_model._get_return_annotation(fn) is int


def test_get_return_annotation_from_callable_instance():
    class UseCase:
        def __call__(self) -> UserModel:
            return UserModel(id=1, name="x")

    uc = UseCase()
    assert infer_response_model._get_return_annotation(uc) is UserModel


def test_get_return_annotation_without_return_annotation():
    def fn(x: int):
        return x

    assert infer_response_model._get_return_annotation(fn) is None


def test_is_disallowed_return_none_and_any():
    assert infer_response_model._is_disallowed_return(None) is True
    assert infer_response_model._is_disallowed_return(Any) is True


def test_is_disallowed_return_response_subclass():
    assert infer_response_model._is_disallowed_return(CustomResponse) is True


def test_is_disallowed_return_union_with_none_any_or_response():
    t1 = Union[int, None]
    t2 = Union[int, Any]
    t3 = Union[int, CustomResponse]
    t4 = Union[int, str]

    assert infer_response_model._is_disallowed_return(t1) is True
    assert infer_response_model._is_disallowed_return(t2) is True
    assert infer_response_model._is_disallowed_return(t3) is True
    assert infer_response_model._is_disallowed_return(t4) is True


def test_is_disallowed_return_normal_type():
    assert infer_response_model._is_disallowed_return(int) is False
    assert infer_response_model._is_disallowed_return(UserModel) is False


def test_collection_returns_model_for_list_tuple_set_of_model():
    assert infer_response_model._collection_returns_model(List[UserModel]) is True
    if sys.version_info >= (3, 9):
        assert infer_response_model._collection_returns_model(list[UserModel]) is True
        assert infer_response_model._collection_returns_model(tuple[UserModel]) is True
        assert infer_response_model._collection_returns_model(set[UserModel]) is True


def test_collection_returns_model_for_non_model_inner_type():
    assert infer_response_model._collection_returns_model(List[int]) is False
    if sys.version_info >= (3, 9):
        assert infer_response_model._collection_returns_model(list[int]) is False


def test_collection_returns_model_for_dict_str_to_model():
    assert infer_response_model._collection_returns_model(Dict[str, UserModel]) is True
    if sys.version_info >= (3, 9):
        assert infer_response_model._collection_returns_model(dict[str, UserModel]) is True


def test_collection_returns_model_for_dict_non_str_key_or_value_not_model():
    assert infer_response_model._collection_returns_model(Dict[int, UserModel]) is False
    assert infer_response_model._collection_returns_model(Dict[str, int]) is False
    if sys.version_info >= (3, 9):
        assert infer_response_model._collection_returns_model(dict[int, UserModel]) is False
        assert infer_response_model._collection_returns_model(dict[str, int]) is False


@std_dataclass
class StdUser:
    id: int
    name: str


def test_normalize_dataclass_for_non_dataclass():
    result = infer_response_model._normalize_dataclass(UserModel)
    assert result is UserModel


def test_normalize_dataclass_for_stdlib_dataclass_creates_pydantic_dataclass():
    result = infer_response_model._normalize_dataclass(StdUser)

    assert is_dataclass(result)
    assert getattr(result, "__pydantic_validator__", None) is not None


def test_normalize_dataclass_for_already_pydantic_dataclass():
    PydanticUser = infer_response_model.dataclass(StdUser)

    result = infer_response_model._normalize_dataclass(PydanticUser)
    assert result is PydanticUser


def test_infer_response_model_with_basemodel_return():
    def fn() -> UserModel:
        return UserModel(id=1, name="x")

    assert infer_response_model.infer_response_model(fn) is UserModel


@pytest.mark.skipif(sys.version_info < (3, 9), reason="PEP 585 requires Python 3.9+")
def test_infer_response_model_with_list_of_basemodel():
    def fn() -> list[UserModel]:
        return []

    ret = infer_response_model.infer_response_model(fn)
    assert get_origin(ret) is list
    assert get_args(ret) == (UserModel,)


@pytest.mark.skipif(sys.version_info < (3, 9), reason="PEP 585 requires Python 3.9+")
def test_infer_response_model_with_dict_str_to_basemodel():
    def fn() -> dict[str, UserModel]:
        return {}

    ret = infer_response_model.infer_response_model(fn)
    assert get_origin(ret) is dict
    assert get_args(ret) == (str, UserModel)


def test_infer_response_model_with_stdlib_dataclass_return():
    @std_dataclass
    class DC:
        id: int

    def fn() -> DC:
        return DC(id=1)

    ret = infer_response_model.infer_response_model(fn)

    assert is_dataclass(ret)
    assert getattr(ret, "__pydantic_validator__", None) is not None


def test_infer_response_model_with_none_any_or_response_returns_none():
    def f1() -> None:
        return None

    def f2() -> Any:
        return 1

    def f3() -> CustomResponse:
        return CustomResponse()

    assert infer_response_model.infer_response_model(f1) is None
    assert infer_response_model.infer_response_model(f2) is None
    assert infer_response_model.infer_response_model(f3) is None


def test_infer_response_model_with_union_returns_none():
    def f1() -> Union[UserModel, None]:
        return UserModel(id=1, name="x")

    def f2() -> Union[UserModel, CustomResponse]:
        return UserModel(id=1, name="x")

    def f3() -> Union[int, str]:
        return 1

    assert infer_response_model.infer_response_model(f1) is None
    assert infer_response_model.infer_response_model(f2) is None
    assert infer_response_model.infer_response_model(f3) is None


def test_infer_response_model_without_return_annotation():
    def fn(x: int):
        return x

    assert infer_response_model.infer_response_model(fn) is None


def test_infer_response_model_with_callable_instance():
    class UseCase:
        def __call__(self) -> UserModel:
            return UserModel(id=1, name="x")

    uc = UseCase()
    assert infer_response_model.infer_response_model(uc) is UserModel


def test_infer_response_model_when_type_hints_fail(monkeypatch):
    def bad_get_type_hints(_):
        raise TypeError("boom")

    monkeypatch.setattr(infer_response_model, "get_type_hints", bad_get_type_hints)

    def fn() -> UserModel:
        return UserModel(id=1, name="x")

    assert infer_response_model.infer_response_model(fn) is None
