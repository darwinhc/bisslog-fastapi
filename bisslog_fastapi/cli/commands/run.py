"""
Command module to run a Flask application using Bisslog metadata.

This module provides a simple `run` function that initializes a Flask app
with use case metadata and launches the server. It is intended to be used
by the `bisslog_flask run` CLI command or directly from Python code.
"""

from typing import Optional

import uvicorn

from bisslog_fastapi import BisslogFastAPI


def run(
        metadata_file: Optional[str] = None,
        use_cases_folder_path: Optional[str] = None,
        infra_path: Optional[str] = None,
        encoding: str = "utf-8",
        secret_key: Optional[str] = None,
        jwt_secret_key: Optional[str] = None,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
        workers: int = 1,
        log_level: str = "info",
):
    """
    Run a Flask application using metadata and use-case source.

    This function creates and runs a Flask app configured through the
    BisslogFlask integration layer. It loads metadata definitions,
    applies HTTP and WebSocket use case resolvers, and starts the server.

    Parameters
    ----------
    metadata_file : str, optional
        Path to the metadata file (YAML or JSON) containing service and trigger definitions.
    use_cases_folder_path : str, optional
        Path to the folder where the use case implementation code is located.
    infra_path : str, optional
        Path to the folder containing infrastructure code (e.g., database, cache).
        This is not used in the current implementation but can be extended.
    encoding : str, optional
        Encoding used to read the metadata file (default is "utf-8").
    secret_key : str, optional
        Value to set as Flask's SECRET_KEY for session signing.
    jwt_secret_key : str, optional
        Value to set as Flask's JWT_SECRET_KEY for JWT-based authentication.
    host : str, optional
        The hostname or IP address where the Uvicorn server will bind
        (default is `"0.0.0.0"` — all interfaces).
    port : int, optional
        Port number on which the server will listen (default is `8000`).
    reload : bool, optional
        If True, enables auto-reload when source files change — useful during
        development. Defaults to False.
    workers : int, optional
        Number of worker processes to spawn for handling requests. Defaults to 1.
    log_level : str, optional
        Logging verbosity level. Must be one of:
        "critical", "error", "warning", "info", "debug", or "trace".
        Defaults to "info".
    """
    app = BisslogFastAPI(
        metadata_file=metadata_file,
        use_cases_folder_path=use_cases_folder_path,
        infra_path=infra_path,
        encoding=encoding,
        secret_key=secret_key,
        jwt_secret_key=jwt_secret_key,

    )

    uvicorn.run(app, host=host, port=port, reload=reload, workers=workers, log_level=log_level)
