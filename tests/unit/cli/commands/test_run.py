"""Unit tests for the CLI run command."""

import importlib
import sys
from unittest.mock import patch, MagicMock


def import_run_with_mocked_uvicorn():
    """Import run module and patch uvicorn module."""
    uvi_mock = MagicMock()
    with patch.dict(sys.modules, {"uvicorn": uvi_mock}):
        import bisslog_fastapi.cli.commands.run as run_module
        importlib.reload(run_module)
        return run_module, uvi_mock


def test_run_initializes_app_and_starts_server():
    """Test that run initializes BisslogFastAPI and calls uvicorn.run."""
    run, uvicorn_mock = import_run_with_mocked_uvicorn()

    with patch.object(run, "BisslogFastAPI") as mock_app_cls:
        mock_app_instance = MagicMock()
        mock_app_cls.return_value = mock_app_instance

        uvicorn_mock.run = mock_uvicorn_run = MagicMock()

        run.run(
            metadata_file="meta.yaml",
            use_cases_folder_path="src",
            infra_path="infra",
            host="127.0.0.1",
            port=9090,
            reload=True,
            workers=2,
            log_level="debug",
            secret_key="secret",
            jwt_secret_key="jwt_secret"
        )

        # Verify App Initialization
        mock_app_cls.assert_called_once_with(
            metadata_file="meta.yaml",
            use_cases_folder_path="src",
            infra_path="infra",
            encoding="utf-8",
            secret_key="secret",
            jwt_secret_key="jwt_secret"
        )

        # Verify Server Startup
        mock_uvicorn_run.assert_called_once_with(
            mock_app_instance,
            host="127.0.0.1",
            port=9090,
            reload=True,
            workers=2,
            log_level="debug"
        )


def test_run_defaults():
    """Test run command with default arguments."""
    run, uvicorn_mock = import_run_with_mocked_uvicorn()

    with patch.object(run, "BisslogFastAPI") as mock_app_cls:
        mock_app_instance = MagicMock()
        mock_app_cls.return_value = mock_app_instance

        uvicorn_mock.run = mock_uvicorn_run = MagicMock()
        run.run()

        mock_app_cls.assert_called_once()
        call_kwargs = mock_app_cls.call_args[1]
        assert call_kwargs["metadata_file"] is None
        assert call_kwargs["encoding"] == "utf-8"

        mock_uvicorn_run.assert_called_once()
        uvicorn_kwargs = mock_uvicorn_run.call_args[1]
        assert uvicorn_kwargs["host"] == "0.0.0.0"
        assert uvicorn_kwargs["port"] == 8000
