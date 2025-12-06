"""
FastApi application initializer for Bisslog-based services.

This module defines a manager that reads service metadata and dynamically registers
use case endpoints into a FastApi application using resolvers for HTTP and WebSocket triggers.
"""

from typing import Optional, Callable

from bisslog_schema import read_service_info_with_code
from bisslog_schema.eager_import_module_or_package import EagerImportModulePackage
from bisslog_schema.schema import UseCaseInfo, TriggerHttp, ServiceInfo
from bisslog_schema.setup import run_setup
from fastapi import FastAPI

from .fastapi_http_resolver import BisslogFastAPIHttpResolver
from .fastapi_resolver import BisslogFastApiResolver
from .fastapi_ws_resolver import BisslogFastAPIWebSocketResolver


class InitFastApiApp:
    """
    Initializes a FastApi app by registering routes from metadata using
    HTTP and WebSocket resolvers.

    This manager reads metadata and code, then applies the appropriate processor (resolver)
    to each use case according to its trigger type.
    """

    def __init__(self,
                 resolver_http: BisslogFastApiResolver, resolver_ws: BisslogFastApiResolver,
                 force_import: Callable[[str], None]) -> None:
        self._http_processor = resolver_http
        self._ws_processor = resolver_ws
        self._force_import = force_import

    def __call__(
        self,
        metadata_file: Optional[str] = None,
        use_cases_folder_path: Optional[str] = None,
        infra_path: Optional[str] = None,
        app: Optional[FastAPI] = None,
        *,
        encoding: str = "utf-8",
        secret_key: Optional[str] = None,
        jwt_secret_key: Optional[str] = None,
        **kwargs
    ) -> FastAPI:
        """
        Loads metadata, discovers use case functions, registers routes and returns the FastApi app.

        This method reads metadata and code from the given paths, initializes the FastApi app
        (if not provided), configures security options, and applies HTTP or WebSocket processors
        based on the trigger type for each use case.

        Parameters
        ----------
        metadata_file : str, optional
            Path to the metadata file (YAML/JSON).
        use_cases_folder_path : str, optional
            Directory where use case code is located.
        infra_path : str, optional
            Path to the folder where infrastructure components (e.g., adapters) are defined.
            This is used to ensure that the necessary modules
             are imported before route registration.
        app : FastApi, optional
            An existing FastApi app instance to which routes will be added.
            If not provided, a new app is created using the service name.
        encoding : str, optional
            File encoding for reading metadata (default is "utf-8").
        **kwargs : Any
            Additional keyword arguments (not currently used).

        Returns
        -------
        FastApi
            The FastApi app instance with registered use case routes.
        """
        full_service_data = read_service_info_with_code(
            metadata_file=metadata_file,
            use_cases_folder_path=use_cases_folder_path,
            encoding=encoding
        )
        service_info: ServiceInfo = full_service_data.declared_metadata
        use_cases = full_service_data.discovered_use_cases

        # Force import
        self._force_import(infra_path)
        # Run global setup if defined
        run_setup("fastapi")

        # Initialize FastApi app
        if app is None:
            app = FastAPI(title=service_info.name, summary=service_info.description)

        # Register each use case to the appropriate processor
        for use_case_keyname in service_info.use_cases:
            use_case_info: UseCaseInfo = service_info.use_cases[use_case_keyname]
            use_case_callable: Callable = use_cases[use_case_keyname]

            for trigger in use_case_info.triggers:
                if isinstance(trigger.options, TriggerHttp):
                    self._http_processor(
                        app, use_case_info, trigger, use_case_callable, **kwargs)

        return app


BisslogFastAPI = InitFastApiApp(
    BisslogFastAPIHttpResolver(),
    BisslogFastAPIWebSocketResolver(),
    EagerImportModulePackage(("src.infra", "infra")),
)
