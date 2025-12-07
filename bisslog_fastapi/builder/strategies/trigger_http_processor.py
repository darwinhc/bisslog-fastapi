"""Processor for HTTP triggers definition"""

import re
from typing import Callable, Any, Optional

from bisslog_schema.schema import TriggerHttp
from bisslog_schema.use_case_code_inspector.use_case_code_metadata import UseCaseCodeInfo

from bisslog_fastapi.builder.static_python_construct_data import StaticPythonConstructData
from bisslog_fastapi.builder.strategies.trigger_processor import TriggerProcessor
from bisslog_fastapi.utils.get_param_type import get_param_type
from bisslog_fastapi.utils.infer_response_model import infer_response_model
from bisslog_fastapi.utils.type_to_str_and_imports import type_to_str_and_imports


class TriggerHttpProcessor(TriggerProcessor):
    """Processor for HTTP triggers."""

    @staticmethod
    def _extract_path_param_names_from_path(path: str) -> tuple[str, ...]:
        """
        Extracts path parameter names from a FastAPI-style path, e.g.:

            "/company/data/{schema}/{uid}" -> ("schema", "uid")
        """
        return tuple(re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", path or ""))

    def __call__(
        self, use_case_key: str, uc_var_name: str, uc_info: UseCaseCodeInfo,
        trigger_info: TriggerHttp, callable_obj: Callable[..., Any], identifier: int,
        use_case_name: Optional[str] = None, use_case_description: Optional[str] = None,
    ) -> StaticPythonConstructData:
        """Generates a FastAPI route handler for an HTTP trigger."""
        mapper = trigger_info.mapper or {}
        imports: dict[str, set[str]] = {}

        path = trigger_info.path or f"/{use_case_key}"
        method = (trigger_info.method or "GET").upper()

        if mapper:
            sig_params, uc_arg_names = self._process_mapper(mapper, callable_obj, imports)
        else:
            sig_params, uc_arg_names = self._process_default(path, callable_obj, imports)

        http_decorator = self._create_http_decorator(
            method, path, use_case_name, use_case_description
        )

        sig_line = self._create_handler_signature(
            use_case_key, identifier, uc_info, callable_obj, sig_params, imports
        )

        body_lines = [http_decorator, sig_line]
        if use_case_description:
            body_lines.append(f'    """{use_case_description}"""')

        body_lines.extend(self._build_handler_body(
            uc_var_name, uc_info.is_coroutine, uc_arg_names, bool(mapper), path
        ))

        return StaticPythonConstructData(importing=imports, body="\n".join(body_lines))

    @staticmethod
    def _create_http_decorator(
        method: str, path: str, name: Optional[str], description: Optional[str]) -> str:
        extra_args = []
        if name:
            extra_args.append(f'name="{name}"')
        if description:
            extra_args.append(f'description="{description}"')

        extra_args_str = ", ".join(extra_args)
        if extra_args_str:
            extra_args_str = ", " + extra_args_str

        return f'@app.{method.lower()}("{path}"{extra_args_str})'

    @staticmethod
    def _create_handler_signature(
        key: str, identifier: int, uc_info: UseCaseCodeInfo,
        callable_obj: Callable, sig_params: list[str], imports: dict
    ) -> str:
        handler_name = f"{key}_handler_{identifier}"
        def_or_async = "async def" if uc_info.is_coroutine else "def"

        ret_ann = infer_response_model(callable_obj)
        return_string = ""
        if ret_ann is not None:
            return_type_str, return_imports = type_to_str_and_imports(ret_ann)
            return_string = f" -> {return_type_str}"
            for mod, names in return_imports.items():
                imports.setdefault(mod, set()).update(names)

        return f"{def_or_async} {handler_name}({', '.join(sig_params)}){return_string}:"

    def _process_mapper(
            self, mapper: dict, callable_obj: Callable, imports: dict
    ) -> tuple[list[str], list[tuple[str, str]]]:
        sig_params: list[str] = []
        uc_arg_names: list[tuple[str, str]] = []

        # Path Params
        imports.setdefault("fastapi", set()).add("Depends")
        self._map_prefix(
            mapper, "path_query", "Path", callable_obj, imports, sig_params, uc_arg_names,
            default_val="...", include_alias=False
        )

        # Body
        self._map_key(
            mapper, "body", "Body", "Dict[str, Any]", callable_obj, imports, sig_params,
            uc_arg_names
        )
        self._map_prefix(
            mapper, "body", "Body", callable_obj, imports, sig_params, uc_arg_names
        )

        # Query Params
        self._map_key(
            mapper, "params", "Depends", "Dict[str, Any]", callable_obj, imports, sig_params,
            uc_arg_names,
            default_val="_all_query_params"
        )
        self._map_prefix(
            mapper, "params", "Query", callable_obj, imports, sig_params, uc_arg_names,
            default_val="None"
        )

        # Headers
        self._map_key(
            mapper, "headers", "Depends", "Dict[str, str]", callable_obj, imports, sig_params,
            uc_arg_names,
            default_val="_all_headers"
        )
        self._map_prefix(
            mapper, "headers", "Header", callable_obj, imports, sig_params, uc_arg_names
        )

        return sig_params, uc_arg_names

    @staticmethod
    def _map_key(
        mapper: dict, key: str, dep_name: str, default_type: str, callable_obj: Callable,
        imports: dict, sig_params: list, uc_arg_names: list, default_val: str = "...") -> None:
        if key not in mapper:
            return

        dst = mapper[key]
        ann = get_param_type(callable_obj, dst)

        if ann is None:
            type_str = default_type
            if "Dict" in default_type:
                imports.setdefault("typing", set()).update({"Dict", "Any"})
        else:
            type_str, extra_imports = type_to_str_and_imports(ann)
            for mod, names in extra_imports.items():
                imports.setdefault(mod, set()).update(names)

        imports.setdefault("fastapi", set()).add(dep_name)
        sig_params.append(f"{dst}: {type_str} = {dep_name}({default_val})")
        uc_arg_names.append((dst, dst))

    @staticmethod
    def _map_prefix(
        mapper: dict, prefix: str, dep_name: str, callable_obj: Callable, imports: dict,
        sig_params: list, uc_arg_names: list, default_val: str = "...", include_alias: bool = True
    ) -> None:
        prefix_dot = f"{prefix}."
        for source_key, dst in sorted(
                (k, v) for k, v in mapper.items() if k.startswith(prefix_dot) and k != prefix):
            field = source_key.split(".", 1)[1]
            ann = get_param_type(callable_obj, dst) or str

            type_str, extra_imports = type_to_str_and_imports(ann)
            for mod, names in extra_imports.items():
                imports.setdefault(mod, set()).update(names)

            imports.setdefault("fastapi", set()).add(dep_name)

            if default_val == "...":
                default_arg = "..."
            elif default_val == "None":
                default_arg = "None"
            else:
                default_arg = default_val

            if include_alias:
                sig_params.append(
                    f"{field}: {type_str} = {dep_name}({default_arg}, alias={field!r})")
            else:
                sig_params.append(f"{field}: {type_str} = {dep_name}({default_arg})")

            uc_arg_names.append((dst, field))

    def _process_default(
            self, path: str, callable_obj: Callable, imports: dict
    ) -> tuple[list[str], list[tuple[str, str]]]:
        sig_params: list[str] = []

        path_param_names = self._extract_path_param_names_from_path(path)
        for p_name in path_param_names:
            ann = get_param_type(callable_obj, p_name) or str
            type_str, extra_imports = type_to_str_and_imports(ann)
            for mod, names in extra_imports.items():
                imports.setdefault(mod, set()).update(names)
            imports.setdefault("fastapi", set()).add("Path")
            sig_params.append(f"{p_name}: {type_str} = Path(...)")

        imports.setdefault("fastapi", set()).add("Body")
        sig_params.append("body: Dict[str, Any] = Body(default={})")
        imports.setdefault("typing", set()).update({"Dict", "Any"})
        imports.setdefault("fastapi", set()).add("Depends")
        sig_params.append("query_params: Dict[str, Any] = Depends(_all_query_params)")
        sig_params.append("headers: Dict[str, str] = Depends(_all_headers)")

        return sig_params, []  # No explicit mapping needed for default

    def _build_handler_body(
            self, uc_var_name: str, is_coroutine: bool,
            uc_arg_names: list[tuple[str, str]], has_mapper: bool, path: str
    ) -> list[str]:
        lines = ["    _kwargs: Dict[str, Any] = {}"]

        if has_mapper:
            for dst, field in uc_arg_names:
                lines.append(f'    _kwargs["{dst}"] = {field}')
        else:
            path_param_names = self._extract_path_param_names_from_path(path)
            for p_name in path_param_names:
                lines.append(f'    _kwargs["{p_name}"] = {p_name}')
            lines.append("    if isinstance(body, dict):")
            lines.append("        _kwargs.update(body)")
            lines.append("    _kwargs.update(query_params)")
            lines.append("    _kwargs.update(headers)")

        if is_coroutine:
            lines.append(f"    result = await {uc_var_name}(**_kwargs)")
        else:
            lines.append(f"    result = {uc_var_name}(**_kwargs)")

        lines.append("    return result")
        lines.append("")
        return lines
