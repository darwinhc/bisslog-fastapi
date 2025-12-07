"""
Unit tests for InitFastApiApp class.
"""
from unittest.mock import Mock, patch

import pytest
from bisslog_schema.schema import UseCaseInfo, ServiceInfo, TriggerInfo
from bisslog_schema.schema.triggers.trigger_http import TriggerHttp
from fastapi import FastAPI

from bisslog_fastapi.runner.init_fastapi_app import InitFastApiApp


@pytest.fixture
def mock_resolver_http():
    return Mock()


@pytest.fixture
def mock_resolver_ws():
    return Mock()


@pytest.fixture
def mock_force_import():
    return Mock()


@pytest.fixture
def init_app(mock_resolver_http, mock_resolver_ws, mock_force_import):
    return InitFastApiApp(
        resolver_http=mock_resolver_http,
        resolver_ws=mock_resolver_ws,
        force_import=mock_force_import
    )


def test_init_app_call_creates_new_app_if_none_provided(init_app, mock_force_import):
    """Test that __call__ creates a new FastAPI app if one is not provided."""

    # Mock return values for read_service_info_with_code
    with patch("bisslog_fastapi.runner.init_fastapi_app.read_service_info_with_code") as mock_read, \
            patch("bisslog_fastapi.runner.init_fastapi_app.run_setup") as mock_run_setup:
        service_info = ServiceInfo(name="TestService", description="Test Description", use_cases={})
        mock_read.return_value.declared_metadata = service_info
        mock_read.return_value.discovered_use_cases = {}

        app = init_app(metadata_file="meta.json")

        assert isinstance(app, FastAPI)
        assert app.title == "TestService"
        assert app.description == ""
        assert app.summary == "Test Description"

        # Verify force_import was called
        mock_force_import.assert_called_once()
        # Verify run_setup was called
        mock_run_setup.assert_called_with("fastapi")


def test_init_app_call_uses_existing_app(init_app):
    """Test that __call__ uses the provided FastAPI app instance."""

    existing_app = FastAPI(title="Existing")

    with patch("bisslog_fastapi.runner.init_fastapi_app.read_service_info_with_code") as mock_read, \
            patch("bisslog_fastapi.runner.init_fastapi_app.run_setup"):
        service_info = ServiceInfo(name="Ignored", description="Ignored", use_cases={})
        mock_read.return_value.declared_metadata = service_info
        mock_read.return_value.discovered_use_cases = {}

        app = init_app(app=existing_app)

        assert app is existing_app
        assert app.title == "Existing"


def test_init_app_registers_http_triggers(init_app, mock_resolver_http):
    """Test that HTTP triggers represent calls to the HTTP processor."""

    # Setup data
    trigger_opt = TriggerHttp(path="/test", method="GET")
    trigger = TriggerInfo(type="http", keyname="t1", options=trigger_opt)

    use_case_info = UseCaseInfo(name="UC1", description="Desc", triggers=[trigger])

    service_info = ServiceInfo(name="S", description="D", use_cases={"uc1": use_case_info})
    use_case_func = lambda: "result"

    with patch("bisslog_fastapi.runner.init_fastapi_app.read_service_info_with_code") as mock_read, \
            patch("bisslog_fastapi.runner.init_fastapi_app.run_setup"):
        mock_read.return_value.declared_metadata = service_info
        mock_read.return_value.discovered_use_cases = {"uc1": use_case_func}

        app = init_app()

        # Check that http resolver was called
        mock_resolver_http.assert_called_once()
        args, kwargs = mock_resolver_http.call_args

        # args: (app, use_case_info, trigger, use_case_callable)
        assert args[0] is app
        assert args[1] == use_case_info
        # The 3rd arg is trigger_info. In the call: self._http_processor(..., trigger, ...)
        # so check if mocked call received the right object
        assert args[2] == trigger
        assert args[3] == use_case_func


def test_init_app_ignores_unknown_triggers(init_app, mock_resolver_http):
    """Test that non-HTTP triggers (and non-WS if logic dictates) are not passed to http resolver."""

    # Trigger with some other type or just not TriggerHttp
    # Based on code: if isinstance(trigger.options, TriggerHttp)

    # Let's make a trigger that is NOT TriggerHttp
    class OtherOptions:
        pass

    trigger = TriggerInfo(type="other", keyname="t2", options=OtherOptions())
    use_case_info = UseCaseInfo(name="UC2", description="Desc", triggers=[trigger])

    service_info = ServiceInfo(name="S", description="D", use_cases={"uc2": use_case_info})

    with patch("bisslog_fastapi.runner.init_fastapi_app.read_service_info_with_code") as mock_read, \
            patch("bisslog_fastapi.runner.init_fastapi_app.run_setup"):
        mock_read.return_value.declared_metadata = service_info
        mock_read.return_value.discovered_use_cases = {"uc2": lambda: None}

        init_app()

        mock_resolver_http.assert_not_called()
