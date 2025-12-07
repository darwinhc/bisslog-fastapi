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
        """Generates a FastAPI route handler for an HTTP trigger.

        The handler signature is derived from the mapper and the use case
        callable annotations, using FastAPI's declarative parameter types
        (Path, Body, Query, Header, Depends, etc.).

        The handler is declared as `async def` if the use case callable
        is coroutine, otherwise as a synchronous `def`.
        """
        mapper = trigger_info.mapper or {}
        imports: dict[str, set[str]] = {}

        method = (trigger_info.method or "GET").upper()
        raw_path = trigger_info.path or f"/{use_case_key}"

        path = raw_path

        handler_name = f"{use_case_key}_handler_{identifier}"
        sig_params: list[str] = []
        uc_arg_names: list[tuple[str, str]] = []

        if mapper:
            imports.setdefault("fastapi", set()).add("Depends")
            for source_key, dst in sorted(
                    (k, v) for k, v in mapper.items() if k.startswith("path_query.")
            ):
                src = source_key.split(".", 1)[1]
                ann = get_param_type(callable_obj, dst) or str
                type_str, extra_imports = type_to_str_and_imports(ann)
                for mod, names in extra_imports.items():
                    imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Path")
                sig_params.append(
                    f"{src}: {type_str} = Path(...)"
                )
                uc_arg_names.append((dst, src))

            if "body" in mapper:
                dst = mapper["body"]
                ann = get_param_type(callable_obj, dst)
                if ann is None:
                    type_str = "Dict[str, Any]"
                    imports.setdefault("typing", set()).update({"Dict", "Any"})
                else:
                    type_str, extra_imports = type_to_str_and_imports(ann)
                    for mod, names in extra_imports.items():
                        imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Body")
                sig_params.append(
                    f"{dst}: {type_str} = Body(...)"
                )
                uc_arg_names.append((dst, dst))

            for source_key, dst in sorted(
                    (k, v) for k, v in mapper.items()
                    if k.startswith("body.") and k != "body"
            ):
                field = source_key.split(".", 1)[1]
                ann = get_param_type(callable_obj, dst) or str
                type_str, extra_imports = type_to_str_and_imports(ann)
                for mod, names in extra_imports.items():
                    imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Body")
                sig_params.append(
                    f"{field}: {type_str} = Body(..., alias={field!r}),  "
                )
                uc_arg_names.append((dst, field))

            if "params" in mapper:
                dst = mapper["params"]
                ann = get_param_type(callable_obj, dst)
                if ann is None:
                    type_str = "Dict[str, Any]"
                    imports.setdefault("typing", set()).update({"Dict", "Any"})
                else:
                    type_str, extra_imports = type_to_str_and_imports(ann)
                    for mod, names in extra_imports.items():
                        imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Depends")
                sig_params.append(
                    f"{dst}: {type_str} = Depends(_all_query_params),  "
                )
                uc_arg_names.append((dst, dst))

            for source_key, dst in sorted(
                    (k, v) for k, v in mapper.items()
                    if k.startswith("params.") and k != "params"
            ):
                field = source_key.split(".", 1)[1]
                ann = get_param_type(callable_obj, dst) or str
                type_str, extra_imports = type_to_str_and_imports(ann)
                for mod, names in extra_imports.items():
                    imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Query")
                sig_params.append(
                    f"{field}: {type_str} = Query(None, alias={field!r}),  "
                )
                uc_arg_names.append((dst, field))

            if "headers" in mapper:
                dst = mapper["headers"]
                ann = get_param_type(callable_obj, dst)
                if ann is None:
                    type_str = "Dict[str, str]"
                    imports.setdefault("typing", set()).add("Dict")
                else:
                    type_str, extra_imports = type_to_str_and_imports(ann)
                    for mod, names in extra_imports.items():
                        imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Depends")
                sig_params.append(
                    f"{dst}: {type_str} = Depends(_all_headers),  "
                )
                uc_arg_names.append((dst, dst))

            for source_key, dst in sorted(
                    (k, v) for k, v in mapper.items()
                    if k.startswith("headers.") and k != "headers"
            ):
                field = source_key.split(".", 1)[1]
                ann = get_param_type(callable_obj, dst) or str
                type_str, extra_imports = type_to_str_and_imports(ann)
                for mod, names in extra_imports.items():
                    imports.setdefault(mod, set()).update(names)
                imports.setdefault("fastapi", set()).add("Header")
                sig_params.append(
                    f"{field}: {type_str} = Header(..., alias={field!r}),  "
                )
                uc_arg_names.append((dst, field))

        else:
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
            sig_params.append(
                "query_params: Dict[str, Any] = Depends(_all_query_params)"
            )
            sig_params.append(
                "headers: Dict[str, str] = Depends(_all_headers)"
            )

        extra_args_decorator = ""
        if use_case_name:
            extra_args_decorator = f', name="{use_case_name}"'
        if use_case_description:
            extra_args_decorator += f', description="{use_case_description}"'
        http_decorator = (f'@app.{method.lower() if method else "GET"}'
                          f'("{path}"{extra_args_decorator})')

        lines: list[str] = [http_decorator]

        if uc_info.is_coroutine:
            def_or_async = "async def"
        else:
            def_or_async = "def"

        ret_ann = infer_response_model(callable_obj)
        return_string = ""
        if ret_ann is not None:
            return_type_str, return_imports = type_to_str_and_imports(ret_ann)
            return_string = f" -> {return_type_str}"
            for mod, names in return_imports.items():
                imports.setdefault(mod, set()).update(names)

        lines.append(f"{def_or_async} {handler_name}({', '.join(sig_params)}){return_string}:")
        if use_case_description:
            lines.append(f'    """{use_case_description}"""')
        lines.append("    _kwargs: Dict[str, Any] = {}")

        if mapper:
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

        if uc_info.is_coroutine:
            lines.append(f"    result = await {uc_var_name}(**_kwargs)")
        else:
            lines.append(f"    result = {uc_var_name}(**_kwargs)")

        lines.append("    return result")
        lines.append("")

        return StaticPythonConstructData(importing=imports, body="\n".join(lines))
