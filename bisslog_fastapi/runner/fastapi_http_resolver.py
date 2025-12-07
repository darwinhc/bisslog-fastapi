"""
FastAPI HTTP resolver for Bisslog-based use case routing.

This module defines a resolver that dynamically registers HTTP endpoints
in a FastAPI application from Bisslog "use case" metadata. It preserves
domain isolation by mapping transport details (path/query/body/headers)
into use case inputs via a configurable Mapper, adds per-endpoint CORS
headers when requested, and supports both synchronous and asynchronous
use cases efficiently.
"""
import inspect
from copy import deepcopy
from json import JSONDecodeError
from typing import (
    Callable, Optional, Dict, Union, Awaitable, Any, Mapping, List
)

from bisslog.utils.mapping import Mapper
from bisslog_schema.schema import UseCaseInfo, TriggerHttp, TriggerInfo
from bisslog_schema.schema.triggers.trigger_mappable import TriggerMappable
from fastapi import FastAPI, Request, Path, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.routing import APIRoute
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.responses import Response

from .fastapi_resolver import BisslogFastApiResolver
from ..utils.extract_path_vars import extract_path_vars
from ..utils.infer_response_model import infer_response_model


class BisslogFastAPIHttpResolver(BisslogFastApiResolver):
    """FastAPI HTTP resolver that registers routes from Bisslog metadata."""

    @staticmethod
    def _apply_cors_headers(resp: Response, trigger: TriggerHttp) -> None:
        """
        Apply CORS headers to a Starlette/FastAPI response object.

        Parameters
        ----------
        resp : Response
            The response object to mutate with CORS headers.
        trigger : TriggerHttp
            HTTP trigger containing CORS configuration.

        Returns
        -------
        None
        """
        if not trigger or not getattr(trigger, "allow_cors", False):
            return
        origins = trigger.allowed_origins or "*"
        methods = (trigger.method.upper(),)
        resp.headers["Access-Control-Allow-Origin"] = (
            origins if isinstance(origins, str)
            else ",".join(origins)
        )
        resp.headers["Access-Control-Allow-Methods"] = ",".join(methods)
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Credentials"] = "true"

    @staticmethod
    def _extract_mapper_path_query_vars(mapper: Optional[Mapper]) -> "List[str]":
        """Collect variables mapped from 'path_query.<name>'."""
        if not mapper:
            return []
        out = []
        if isinstance(mapper, Mapper):
            mapper_obj = mapper.base
        elif isinstance(mapper, dict):
            mapper_obj = mapper
        else:
            return []

        for _, src in mapper_obj.items():
            if isinstance(src, str) and src.startswith("path_query."):
                name = src.split(".", 1)[1]
                if name not in out:
                    out.append(name)
        return out

    @classmethod
    def _inject_path_query_signature(
            cls,
            endpoint: Callable,
            path: str,
            mapper: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Replace the endpoint signature so path/query params appear in OpenAPI docs.
        """
        params = [
            inspect.Parameter(
                "request",
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Request,
            )
        ]

        # Always include request

        path_vars = extract_path_vars(path)
        query_vars = cls._extract_mapper_path_query_vars(mapper)

        # Path params (required)
        for name in path_vars:
            params.append(
                inspect.Parameter(
                    name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=str,
                    default=Path(...),
                )
            )

        # Query params (optional)
        for name in query_vars:
            if name in path_vars:
                continue
            params.append(
                inspect.Parameter(
                    name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Optional[str],
                    default=Query(None),
                )
            )

        endpoint.__signature__ = inspect.Signature(parameters=params,
                                                   return_annotation=Response)
        endpoint.__name__ = f"{endpoint.__name__}_with_signature"

    @classmethod
    def _options_handler(
            cls, trigger: TriggerHttp) -> Callable[[Request], Awaitable[PlainTextResponse]]:
        """
        Create an OPTIONS handler suitable for CORS preflight requests.

        Parameters
        ----------
        trigger : TriggerHttp
            HTTP trigger containing CORS configuration.

        Returns
        -------
        Callable[[Request], Awaitable[PlainTextResponse]]
            An async endpoint function that returns an empty 200 response
            with the appropriate CORS headers applied.
        """

        async def options_endpoint(_: Request) -> PlainTextResponse:
            resp = PlainTextResponse("")
            cls._apply_cors_headers(resp, trigger)
            return resp

        return options_endpoint

    @classmethod
    def _use_case_factory(
            cls,
            use_case_name: str,
            fn: Callable[..., Any],
            mapper: Optional[Dict[str, str]] = None,
            trigger: Optional[TriggerHttp] = None,
            use_case_description: Optional[str] = None,
    ) -> Callable[[Request], Awaitable[JSONResponse]]:
        """
        Build a FastAPI endpoint for a use case, precomputing execution strategy
        (async vs. sync) and mapping behavior.

        Parameters
        ----------
        use_case_name : str
            Unique name of the use case (used for Mapper naming and diagnostics).
        fn : Callable[..., Any]
            Use case callable to invoke. It may be synchronous or asynchronous.
        mapper : dict, optional
            Mapping schema for request fields. If provided, a ``Mapper`` is
            instantiated to transform request data into keyword arguments.
        trigger : TriggerHttp, optional
            Trigger options used to configure HTTP method assumptions and CORS.
        use_case_description: str, optional
            Description of the use case.

        Returns
        -------
        Callable[[Request], Awaitable[JSONResponse]]
            An async FastAPI-compatible endpoint function.

        Notes
        -----
        - JSON body parsing is skipped for GET requests.
        - Synchronous use cases are executed via ``run_in_threadpool``.
        """
        use_case_fn = deepcopy(fn)
        http_method = (trigger.method.upper() if trigger else "GET")

        is_async = inspect.iscoroutinefunction(use_case_fn) or inspect.iscoroutinefunction(
            getattr(use_case_fn, "__call__", None)
        )

        if is_async:
            async def call_use_case(**kwargs) -> Any:
                return await use_case_fn(**kwargs)
        else:
            async def call_use_case(**kwargs) -> Any:
                # Execute sync use case in a thread to avoid blocking the event loop.
                return await run_in_threadpool(use_case_fn, **kwargs)

        __mapper__ = Mapper(name=f"Mapper {use_case_name}", base=mapper) if mapper else None

        if __mapper__ is None:
            async def build_kwargs(request: Request) -> Dict[str, Any]:
                """Build a dictionary of keyword arguments for use case execution."""
                res = {}
                if request.path_params:
                    res.update(request.path_params)
                if request.query_params:
                    res.update(request.query_params)
                if request.headers:
                    res.update(request.headers)
                if http_method not in ("GET", "DELETE"):
                    try:
                        body = await request.json()
                    except (JSONDecodeError, UnicodeDecodeError, ClientDisconnect):
                        body = {}
                    if body and isinstance(body, dict):
                        res.update(body)
                return res
        else:
            async def build_kwargs(request: Request) -> Dict[str, Any]:
                if http_method not in ("GET", "DELETE"):
                    try:
                        body = await request.json()
                    except (JSONDecodeError, UnicodeDecodeError, ClientDisconnect):
                        body = {}
                else:
                    body = {}
                return __mapper__.map({
                    "path_query": request.path_params or {},
                    "body": body or {},
                    "params": dict(request.query_params),
                    "headers": request.headers,
                })

        async def endpoint(request: Request, **_params: Mapping[str, Any]):
            """
            FastAPI endpoint that executes the bound use case.
            """
            kwargs = await build_kwargs(request)
            result = await call_use_case(**kwargs)
            if trigger and getattr(trigger, "allow_cors", False):
                cls._apply_cors_headers(result, trigger)
            return result

        endpoint.__doc__ = use_case_description
        endpoint.__name__ = f"{use_case_name}_endpoint"
        # Inject visible path/query parameters
        if trigger:
            cls._inject_path_query_signature(endpoint, trigger.path, mapper)

        return endpoint

    @classmethod
    def _add_use_case(
            cls,
            app: FastAPI,
            use_case_info: UseCaseInfo,
            trigger: TriggerInfo,
            use_case_function: Union[Callable[..., Any], Callable[..., Awaitable[Any]]],
    ) -> None:
        """
        Register a use case as a FastAPI route based on HTTP trigger metadata.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance.
        use_case_info : UseCaseInfo
            Metadata describing the use case (identifier, naming, etc.).
        trigger : TriggerInfo
            Trigger configuration. Only HTTP triggers are processed.
        use_case_function : Callable
            The use case callable to expose over HTTP. It may be sync or async.
        """
        if not isinstance(trigger.options, TriggerHttp):
            return

        path = trigger.options.path
        mapper = trigger.options.mapper if isinstance(trigger.options, TriggerMappable) else None

        endpoint = cls._use_case_factory(
            use_case_name=use_case_info.keyname,
            fn=use_case_function,
            mapper=mapper,
            trigger=trigger.options,
            use_case_description=use_case_info.description,
        )
        response_model = infer_response_model(use_case_function)

        app.add_api_route(
            path,
            endpoint,
            name=f"{use_case_info.keyname} {path} {trigger.options.method.upper()}",
            summary=use_case_info.name.lower().capitalize(),
            description=use_case_info.description,
            methods=[trigger.options.method.upper()],
            response_model=response_model,
        )

        if getattr(trigger.options, "allow_cors", False):
            has_options = any(
                isinstance(r, APIRoute) and r.path == path and "OPTIONS" in r.methods
                for r in app.router.routes
            )
            if not has_options:
                app.add_api_route(
                    path,
                    cls._options_handler(trigger.options),
                    name=f"{use_case_info.keyname} {path} OPTIONS",
                    methods=["OPTIONS"],
                )

    def __call__(self, app: FastAPI, use_case_info: UseCaseInfo, trigger_info: TriggerInfo,
                 use_case_callable: Callable[..., Any], **kwargs: Any) -> None:
        """
        Register a use case route using this resolver.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance.
        use_case_info : UseCaseInfo
            Use case metadata to drive route naming and diagnostics.
        trigger_info : TriggerInfo
            Trigger metadata (must carry a ``TriggerHttp`` in ``options``).
        use_case_callable : Callable[..., Any]
            The callable implementing the use case. It may be sync or async.
        **kwargs : Any
            Extra keyword arguments reserved for future extensions.

        Returns
        -------
        None
        """
        self._add_use_case(app, use_case_info, trigger_info, use_case_callable)
