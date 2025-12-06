"""Builder for FastAPI app from Bisslog metadata."""

import importlib
from typing import Optional, Callable, Any, Dict, Set, Tuple

from bisslog_schema import read_full_service_metadata
from bisslog_schema.eager_import_module_or_package import EagerImportModulePackage
from bisslog_schema.schema import TriggerHttp, TriggerWebsocket
from bisslog_schema.setup import get_setup_metadata
from bisslog_schema.use_case_code_inspector.use_case_code_metadata import (
    UseCaseCodeInfo,
    UseCaseCodeInfoClass,
    UseCaseCodeInfoObject,
)

from .static_python_construct_data import StaticPythonConstructData
from .strategies.trigger_http_processor import TriggerHttpProcessor
from .strategies.trigger_processor import TriggerProcessor


class BuilderFastAPIAppManager:
    """
    FastAPI application builder for Bisslog-based services.

    This builder:
    - Reads Bisslog metadata and discovered use cases.
    - Uses the mapper of each HTTP trigger to shape the FastAPI handler
      signature so that OpenAPI docs reflect the use case contract.
    - Detects types from the use case callable annotations.
    - Maps mapper keys to FastAPI parameter types:

        * path_query.<source> -> Path(...)
        * body -> Body(...)
        * body.<field> -> Body(..., alias="<field>")
        * params -> Dict via Depends(_all_query_params)
        * params.<name> -> Query(..., alias="<name>")
        * headers -> Dict via Depends(_all_headers)
        * headers.<name> -> Header(..., alias="<name>")
        * context -> Dict via Depends(_context_from_request)

    HTTP handlers are declared as `async def` if the use case is coroutine,
    or as `def` if the use case is synchronous. WebSocket handlers are
    always `async def` (as required by FastAPI).
    """

    def __init__(
        self, eager_importer: Callable[[str], None],
        trigger_http_processor: TriggerProcessor, trigger_ws_processor: TriggerProcessor,
    ):
        self._trigger_http_processor = trigger_http_processor
        self._trigger_ws_processor = trigger_ws_processor
        self._eager_importer = eager_importer

    def _get_bisslog_setup(self, infra_path: Optional[str]) -> Optional[StaticPythonConstructData]:
        """Generates Bisslog setup code for the 'fastapi' runtime, if declared.

        It first checks the generic setup_function, and then any runtime-specific
        setup for 'fastapi' in the metadata.
        """
        self._eager_importer(infra_path)
        setup_metadata = get_setup_metadata()
        if setup_metadata is None:
            return None

        if setup_metadata.setup_function is not None:
            n_params = setup_metadata.setup_function.n_params
            if n_params == 0:
                build = f"{setup_metadata.setup_function.function_name}()"
            elif n_params == 1:
                build = f'{setup_metadata.setup_function.function_name}("fastapi")'
            else:
                build = (
                    f'{setup_metadata.setup_function.function_name}("fastapi")'
                    "  # TODO: change this, one or more parameters are missing"
                )
            return StaticPythonConstructData(
                importing={
                    setup_metadata.setup_function.module: {
                        setup_metadata.setup_function.function_name
                    }
                },
                build=build,
            )

        custom_runtime_setup = setup_metadata.runtime.get("fastapi", None)
        if custom_runtime_setup is not None:
            return StaticPythonConstructData(
                importing={custom_runtime_setup.module: {custom_runtime_setup.function_name}},
                build=f"{custom_runtime_setup.function_name}()",
            )
        return None

    @staticmethod
    def _resolve_uc_callable(
        use_case_code_info: UseCaseCodeInfo,
    ) -> Tuple[str, Callable[..., Any], Dict[str, Set[str]], Optional[str]]:
        """
        Resolves a use case into a concrete callable and the code needed to
        reference it in the generated FastAPI app.

        For classes:
            - Instantiates the class.
            - Uses __call__ if present, otherwise .run().
        For objects:
            - Assumes the variable is already callable.

        Returns
        -------
        Tuple[str, Callable[..., Any], Dict[str, Set[str]], str]
            - The variable name that will be used in the generated code.
            - The Python callable to introspect.
            - A dict of imports (module -> set(symbols)).
            - Build code to create the callable variable.
        """
        importing: Dict[str, Set[str]] = {}
        uc_var_name = f"{use_case_code_info.name}_uc"
        build = None

        if isinstance(use_case_code_info, UseCaseCodeInfoClass):
            if not use_case_code_info.module or not use_case_code_info.class_name:
                raise ValueError("UseCaseCodeInfoClass requires module and class_name")

            importing[use_case_code_info.module] = {use_case_code_info.class_name}
            build = f"{uc_var_name} = {use_case_code_info.class_name}()"

            mod = importlib.import_module(use_case_code_info.module)
            cls = getattr(mod, use_case_code_info.class_name)
            py_callable = cls()

        elif isinstance(use_case_code_info, UseCaseCodeInfoObject):
            if not use_case_code_info.module or not use_case_code_info.var_name:
                raise ValueError("UseCaseCodeInfoObject requires module and var_name")
            importing[use_case_code_info.module] = {use_case_code_info.var_name}

            mod = importlib.import_module(use_case_code_info.module)
            py_callable = getattr(mod, use_case_code_info.var_name)
            uc_var_name = use_case_code_info.var_name
        else:
            raise ValueError("Unsupported UseCaseCodeInfo type")
        if not callable(py_callable):
            raise ValueError(f"Object {use_case_code_info.var_name} is not callable")
        return uc_var_name, py_callable, importing, build

    def __call__(
        self,
        metadata_file: Optional[str] = None,
        use_cases_folder_path: Optional[str] = None,
        infra_path: Optional[str] = None,
        *,
        encoding: str = "utf-8",
        secret_key: Optional[str] = None,
        jwt_secret_key: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Main entry point for generating the full FastAPI application code.

        Mirrors the Flask builder semantics when there is no mapper:
        - Collects path params, body, query params, and headers into kwargs
          and passes them to the use case.
        - When a mapper is present, uses it to explicitly declare each
          parameter via FastAPI's parameter types, improving OpenAPI.
        """
        full_service_metadata = read_full_service_metadata(
            metadata_file=metadata_file,
            use_cases_folder_path=use_cases_folder_path,
            encoding=encoding,
        )
        service_info = full_service_metadata.declared_metadata
        use_cases = full_service_metadata.discovered_use_cases

        # Base imports and helpers for the generated app
        base_imports: Dict[str, Optional[Set[str]]] = {
            "fastapi": {
                "FastAPI",
                "Request",
            },
            "typing": {"Any", "Dict"},
        }

        base_build = (
            f'app = FastAPI(title="{service_info.name}", '
            f'description="{service_info.description}")\n\n'
            "def _all_query_params(request: Request) -> Dict[str, Any]:\n"
            "    return dict(request.query_params)\n\n"
            "def _all_headers(request: Request) -> Dict[str, str]:\n"
            "    return dict(request.headers)\n\n"
        )

        res = StaticPythonConstructData(importing=base_imports, build=base_build)

        # Bisslog setup
        res += self._get_bisslog_setup(infra_path)

        # Use cases and triggers
        for use_case_key, use_case_info in service_info.use_cases.items():
            use_case_code_info: UseCaseCodeInfo = use_cases[use_case_key]

            uc_var_name, callable_obj, uc_imports, uc_build = self._resolve_uc_callable(
                use_case_code_info
            )

            triggers_http = [
                t for t in use_case_info.triggers if isinstance(t.options, TriggerHttp)
            ]
            triggers_ws = [
                t for t in use_case_info.triggers if isinstance(t.options, TriggerWebsocket)
            ]
            if not triggers_http and not triggers_ws:
                continue
            res += StaticPythonConstructData(importing=uc_imports, build=uc_build)

            for i, trigger in enumerate(triggers_http):
                res += self._trigger_http_processor(
                    use_case_key,
                    uc_var_name,
                    use_case_code_info,
                    trigger.options,
                    callable_obj,
                    i,
                    use_case_description=use_case_info.description,
                    use_case_name=use_case_info.name,
                )

            for i, trigger in enumerate(triggers_ws):
                res += self._trigger_ws_processor(
                    use_case_key,
                    uc_var_name,
                    use_case_code_info,
                    trigger.options,
                    callable_obj,
                    i,
                    use_case_description=use_case_info.description,
                    use_case_name=use_case_info.name,
                )

        return res.generate_boiler_plate_fastapi()


bisslog_fastapi_builder = BuilderFastAPIAppManager(
    EagerImportModulePackage(("src.infra", "infra")),
    trigger_http_processor=TriggerHttpProcessor(),
    trigger_ws_processor=TriggerHttpProcessor(),
)
