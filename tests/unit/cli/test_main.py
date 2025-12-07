"""
Unit tests for the CLI main entry point.
"""
import sys
import types
from unittest.mock import patch, MagicMock

# Create a mock module for bisslog_fastapi
mock_bisslog = types.ModuleType("bisslog_fastapi")
mock_bisslog.__path__ = []
mock_bisslog.BisslogFastAPI = MagicMock()

with patch.dict(sys.modules, {"uvicorn": MagicMock()}):
    import bisslog_fastapi.cli as cli


def test_main_dispatches_to_run_command():
    """Test that main calls run command when 'run' arg is provided."""

    with patch.object(sys, "argv",
                      ["bisslog-fastapi", "run", "--metadata-file", "meta.json", "--port", "9000"]), \
            patch.object(cli, "run") as mock_run:
        cli.main()

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["metadata_file"] == "meta.json"
        assert call_kwargs["port"] == 9000
        assert call_kwargs["host"] == "0.0.0.0"  # Default


def test_main_dispatches_to_build_command():
    """Test that main calls build command when 'build' arg is provided."""

    with patch.object(sys, "argv",
                      ["bisslog-fastapi", "build", "--metadata-file", "meta.json",
                       "--target-filename", "app.py"]), \
            patch.object(cli, "build_boiler_plate_fastapi") as mock_build:
        cli.main()

        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args[1]
        assert call_kwargs["target_filename"] == "app.py"
        assert call_kwargs["encoding"] == "utf-8"  # Default


def test_main_exits_on_unknown_command():
    """Test that system exits if no valid command is provided."""
    # argparse will exit typically. We need to catch SystemExit.

    with patch.object(sys, "argv", ["bisslog-fastapi", "unknown"]), \
            patch("sys.stderr", new_callable=MagicMock):
        try:
            cli.main()
        except SystemExit as e:
            assert e.code != 0


def test_main_handles_exception_gracefully():
    """Test that main catches exceptions and exits with 1."""

    with patch.object(sys, "argv", ["bisslog-fastapi", "run"]), \
            patch.object(cli, "run") as mock_run, \
            patch("traceback.print_exc") as mock_print_exc:

        mock_run.side_effect = Exception("Test Exception")
        try:
            cli.main()
        except SystemExit as e:
            assert e.code == 1

        mock_print_exc.assert_called_once()
