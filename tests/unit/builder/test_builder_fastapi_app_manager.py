"""
Unit tests for the BuilderFastAPIAppManager class.

This module exercises core behaviors such as Bisslog setup resolution,
use case callable resolution, path parameter extraction, and the top-level
__call__ orchestration semantics.
"""

import sys
from types import ModuleType, SimpleNamespace

import pytest
from bisslog_schema.schema import TriggerInfo, UseCaseInfo, ServiceInfo, \
    TriggerWebsocket
from bisslog_schema.service_metadata_with_code import ServiceInfoWithCode
from bisslog_schema.use_case_code_inspector.use_case_code_metadata import (
    UseCaseCodeInfoClass, UseCaseCodeInfoObject,
)

from bisslog_fastapi.builder import builder_fastapi_app_manager
from bisslog_fastapi.builder.static_python_construct_data import StaticPythonConstructData
from bisslog_fastapi.builder.strategies.trigger_http_processor import TriggerHttpProcessor
from bisslog_fastapi.builder.strategies.trigger_ws_processor import TriggerWebsocketProcessor


@pytest.fixture
def builder():
    """
    Provide a BuilderFastAPIAppManager with a recording eager_importer.
    """
    calls = {"last": None}

    def eager_importer(path: str) -> None:
        calls["last"] = path

    builder_instance = builder_fastapi_app_manager.BuilderFastAPIAppManager(
        eager_importer=eager_importer,
        trigger_http_processor=TriggerHttpProcessor(),
        trigger_ws_processor=TriggerWebsocketProcessor(),
    )
    builder_instance._eager_calls = calls  # test-only hook
    return builder_instance


# ---------------------------------------------------------------------------
# Tests for _extract_path_param_names_from_path
# ---------------------------------------------------------------------------

def test_extract_path_param_names_basic(builder):
    """
    Test that typical path parameters are extracted correctly.
    """
    path = "/company/data/{schema}/{uid}"
    trigger_http_processor = TriggerHttpProcessor()

    result = trigger_http_processor._extract_path_param_names_from_path(path)

    assert result == ("schema", "uid")


def test_extract_path_param_names_without_params(builder):
    """
    Test that a path without parameters returns an empty tuple.
    """
    path = "/health"
    trigger_http_processor = TriggerHttpProcessor()

    result = trigger_http_processor._extract_path_param_names_from_path(path)

    assert result == ()


def test_extract_path_param_names_empty_string(builder):
    """
    Test that an empty path string returns an empty tuple.
    """
    trigger_http_processor = TriggerHttpProcessor()
    result = trigger_http_processor._extract_path_param_names_from_path("")

    assert result == ()


def test_get_bisslog_setup_returns_none_when_no_setup_metadata(builder, monkeypatch):
    """
    Test that _get_bisslog_setup returns None when there is no setup metadata.
    """
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "get_setup_metadata",
        lambda: None,
    )

    result = builder._get_bisslog_setup("infra/path")

    assert builder._eager_calls["last"] == "infra/path"
    assert result is None


def test_get_bisslog_setup_with_setup_function_nparams_0(builder, monkeypatch):
    """
    Test that setup_function with zero params generates init_app() code.
    """
    setup_function = SimpleNamespace(
        module="my_app.setup",
        function_name="init_app",
        n_params=0,
    )
    setup_metadata = SimpleNamespace(
        setup_function=setup_function,
        runtime={},
    )
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "get_setup_metadata",
        lambda: setup_metadata,
    )

    result = builder._get_bisslog_setup("infra/path")

    assert isinstance(result, StaticPythonConstructData)
    assert result.importing == {"my_app.setup": {"init_app"}}
    assert result.build == "init_app()"


def test_get_bisslog_setup_with_setup_function_nparams_1(builder, monkeypatch):
    """
    Test that setup_function with one param generates init_app(\"fastapi\") code.
    """
    setup_function = SimpleNamespace(
        module="my_app.setup",
        function_name="init_app",
        n_params=1,
    )
    setup_metadata = SimpleNamespace(
        setup_function=setup_function,
        runtime={},
    )
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "get_setup_metadata",
        lambda: setup_metadata,
    )

    result = builder._get_bisslog_setup("infra/path")

    assert isinstance(result, StaticPythonConstructData)
    assert result.importing == {"my_app.setup": {"init_app"}}
    assert result.build == 'init_app("fastapi")'


def test_get_bisslog_setup_with_setup_function_n_params_gt_1(builder, monkeypatch):
    """
    Test that setup_function with more than one param.
    """
    setup_function = SimpleNamespace(
        module="my_app.setup",
        function_name="init_app",
        n_params=2,
    )
    setup_metadata = SimpleNamespace(
        setup_function=setup_function,
        runtime={},
    )
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "get_setup_metadata",
        lambda: setup_metadata,
    )

    result = builder._get_bisslog_setup("infra/path")

    assert isinstance(result, StaticPythonConstructData)
    assert result.importing == {"my_app.setup": {"init_app"}}
    assert (
        result.build
        == 'init_app("fastapi")  # TODO: change this, one or more parameters are missing'
    )


def test_get_bisslog_setup_with_runtime_fastapi_custom(builder, monkeypatch):
    """
    Test that custom runtime[\"fastapi\"] setup is used when present.
    """
    custom_runtime_setup = SimpleNamespace(
        module="my_runtime.setup",
        function_name="custom_fastapi_setup",
    )
    setup_metadata = SimpleNamespace(
        setup_function=None,
        runtime={"fastapi": custom_runtime_setup},
    )
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "get_setup_metadata",
        lambda: setup_metadata,
    )

    result = builder._get_bisslog_setup("infra/path")

    assert isinstance(result, StaticPythonConstructData)
    assert result.importing == {"my_runtime.setup": {"custom_fastapi_setup"}}
    assert result.build == "custom_fastapi_setup()"


def _install_dummy_uc_module():
    """
    Create a temporary dummy module in sys.modules with callable content.
    """
    module_name = "dummy_uc_module"
    mod = ModuleType(module_name)

    class MyUC:
        def __call__(self, **kwargs):
            return kwargs

    def my_uc_func(**kwargs):
        return kwargs

    mod.MyUC = MyUC
    mod.my_uc_func = my_uc_func
    mod.not_callable = 123

    sys.modules[module_name] = mod
    return module_name, MyUC, my_uc_func


def _make_uc_class_info(name: str, module: str, class_name: str) -> UseCaseCodeInfoClass:
    """
    Create a UseCaseCodeInfoClass instance bypassing its __init__.
    """
    uc_info = UseCaseCodeInfoClass(
        name=name, module=module, class_name=class_name, is_coroutine=False, docs="something",
    )
    return uc_info


def _make_uc_object_info(name: str, module: str, var_name: str) -> UseCaseCodeInfoObject:
    """
    Create a UseCaseCodeInfoObject instance bypassing its __init__.
    """
    uc_info = UseCaseCodeInfoObject(
        name=name, module=module, var_name=var_name, is_coroutine=False, docs="something",
    )
    return uc_info


def test_resolve_uc_callable_for_class():
    """
    Test that _resolve_uc_callable correctly handles UseCaseCodeInfoClass.
    """
    module_name, MyUC, _ = _install_dummy_uc_module()

    uc_info = _make_uc_class_info(
        name="my_use_case",
        module=module_name,
        class_name="MyUC",
    )

    uc_var_name, py_callable, importing, build = (
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info
        )
    )

    assert uc_var_name == "my_use_case_uc"
    assert isinstance(py_callable, MyUC)
    assert callable(py_callable)
    assert importing == {module_name: {"MyUC"}}
    assert build == "my_use_case_uc = MyUC()"


def test_resolve_uc_callable_for_class_missing_module_or_class_name():
    """
    Test that _resolve_uc_callable raises ValueError when class info is incomplete.
    """
    # Missing module
    uc_info_missing_module = _make_uc_class_info(
        name="my_use_case",
        module="",
        class_name="MyUC",
    )
    with pytest.raises(ValueError):
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info_missing_module
        )

    # Missing class_name
    uc_info_missing_class = _make_uc_class_info(
        name="my_use_case",
        module="dummy_uc_module",
        class_name="",
    )
    with pytest.raises(ValueError):
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info_missing_class
        )


def test_resolve_uc_callable_for_object():
    """
    Test that _resolve_uc_callable correctly handles UseCaseCodeInfoObject.
    """
    module_name, _, my_uc_func = _install_dummy_uc_module()

    uc_info = _make_uc_object_info(
        name="my_use_case",
        module=module_name,
        var_name="my_uc_func",
    )

    uc_var_name, py_callable, importing, build = (
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info
        )
    )

    assert uc_var_name == "my_uc_func"
    assert py_callable is my_uc_func
    assert importing == {module_name: {"my_uc_func"}}
    assert build is None


def test_resolve_uc_callable_for_object_missing_module_or_var_name():
    """
    Test that _resolve_uc_callable raises ValueError when object info is incomplete.
    """
    module_name, _, _ = _install_dummy_uc_module()

    uc_info_missing_module = _make_uc_object_info(
        name="my_use_case",
        module="",
        var_name="my_uc_func",
    )
    with pytest.raises(ValueError):
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info_missing_module
        )

    uc_info_missing_var = _make_uc_object_info(
        name="my_use_case",
        module=module_name,
        var_name="",
    )
    with pytest.raises(ValueError):
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info_missing_var
        )


def test_resolve_uc_callable_for_object_not_callable():
    """
    Test that _resolve_uc_callable rejects non-callable resolved objects.
    """
    module_name, _, _ = _install_dummy_uc_module()

    uc_info = _make_uc_object_info(
        name="my_use_case",
        module=module_name,
        var_name="not_callable",
    )

    with pytest.raises(ValueError) as exc_info:
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info
        )

    assert "is not callable" in str(exc_info.value)


def test_resolve_uc_callable_unsupported_type():
    """
    Test that _resolve_uc_callable rejects unsupported info types.
    """

    class OtherType:
        def __init__(self):
            self.name = "x"

    uc_info = OtherType()

    with pytest.raises(ValueError) as exc_info:
        builder_fastapi_app_manager.BuilderFastAPIAppManager._resolve_uc_callable(
            uc_info
        )
    assert "Unsupported UseCaseCodeInfo type" in str(exc_info.value)


def test_call_without_triggers_generates_basic_fastapi_app(monkeypatch):
    """
    Test that __call__ produces base FastAPI bootstrap code when no triggers exist.
    """
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "get_setup_metadata",
        lambda: None,
    )

    service_info = SimpleNamespace(
        name="My Service",
        description="Service description",
        use_cases={},
    )
    full_service_metadata = SimpleNamespace(
        declared_metadata=service_info,
        discovered_use_cases={},
    )
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "read_full_service_metadata",
        lambda metadata_file, use_cases_folder_path, encoding: full_service_metadata,
    )

    builder_instance = builder_fastapi_app_manager.BuilderFastAPIAppManager(
        eager_importer=lambda _: None,
        trigger_http_processor=TriggerHttpProcessor(),
        trigger_ws_processor=TriggerWebsocketProcessor(),
    )

    result = builder_instance()

    assert """app = FastAPI(title="My Service", description="Service description")""" in result
    assert "def _all_query_params(request: Request) -> Dict[str, Any]:" in result
    assert "def _all_headers(request: Request) -> Dict[str, str]:" in result


def test_call_with_http_trigger_propagates_not_implemented(monkeypatch):
    """
    Test that __call__ propagates NotImplementedError when HTTP triggers exist.
    """

    trigger_http = TriggerInfo(options=TriggerWebsocket(),
                               keyname="uc_name_identifier", type="websocket")
    use_case_info = UseCaseInfo(
        name="UC name",
        description="UC description",
        triggers=[trigger_http],
    )

    def fake_resolve_uc_callable(self, use_case_code_info):
        """
        Fake implementation of _resolve_uc_callable used for this test.
        """
        return "uc_var", (lambda **kwargs: None), {}, None

    monkeypatch.setattr(
        builder_fastapi_app_manager.BuilderFastAPIAppManager,
        "_resolve_uc_callable",
        fake_resolve_uc_callable,
    )

    service_info = ServiceInfo(
        name="My Service",
        description="Service description",
        use_cases={"uc_key": use_case_info},
    )
    full_service_metadata = ServiceInfoWithCode(
        declared_metadata=service_info,
        discovered_use_cases={"uc_key": UseCaseCodeInfoObject(
            name="uc_key", module="module", var_name="var_name",
            is_coroutine=False, docs="something")},
    )
    monkeypatch.setattr(
        builder_fastapi_app_manager,
        "read_full_service_metadata",
        lambda metadata_file, use_cases_folder_path, encoding: full_service_metadata,
    )

    builder_instance = builder_fastapi_app_manager.BuilderFastAPIAppManager(
        eager_importer=lambda _: None,
        trigger_http_processor=TriggerHttpProcessor(),
        trigger_ws_processor=TriggerWebsocketProcessor(),
    )

    with pytest.raises(NotImplementedError):
        builder_instance()
