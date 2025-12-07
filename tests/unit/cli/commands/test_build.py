"""
Unit tests for the CLI build command.
"""
import importlib
import sys
from unittest.mock import patch, mock_open, MagicMock


def import_build_with_mocked_uvicorn():
    """Import build module and patch uvicorn module."""
    uvi_mock = MagicMock()
    with patch.dict(sys.modules, {"uvicorn": uvi_mock}):
        from bisslog_fastapi.cli.commands import build
        importlib.reload(build)
        return build


def test_build_generates_code_and_writes_to_file():
    """Test that build command calls builder and writes output to file."""
    build = import_build_with_mocked_uvicorn()
    mock_code = "app = FastAPI()"

    with patch.object(build, "bisslog_fastapi_builder", return_value=mock_code) as mock_builder, \
            patch("builtins.open", mock_open()) as mock_file:
        build.build_boiler_plate_fastapi(
            metadata_file="meta.yaml",
            use_cases_folder_path="src",
            infra_path="infra",
            target_filename="output.py"
        )

        # Verify Builder Call
        mock_builder.assert_called_once_with(
            metadata_file="meta.yaml",
            use_cases_folder_path="src",
            infra_path="infra",
            encoding="utf-8"
        )

        # Verify File Open
        mock_file.assert_called_once_with("output.py", "w", encoding="utf-8")

        # ✅ Handle correcto cuando se usa "with open(...) as f:"
        handle = mock_file.return_value.__enter__.return_value
        handle.write.assert_called_once_with(mock_code)


def test_build_defaults():
    """Test build command with default arguments."""
    build = import_build_with_mocked_uvicorn()

    mock_code = "default_code"

    with patch.object(build, "bisslog_fastapi_builder", return_value=mock_code) as mock_builder, \
            patch("builtins.open", mock_open()) as mock_file:
        build.build_boiler_plate_fastapi()

        mock_builder.assert_called_once()
        call_kwargs = mock_builder.call_args[1]
        assert call_kwargs["metadata_file"] is None
        assert call_kwargs["use_cases_folder_path"] is None

        mock_file.assert_called_once_with("fastapi_app.py", "w", encoding="utf-8")
