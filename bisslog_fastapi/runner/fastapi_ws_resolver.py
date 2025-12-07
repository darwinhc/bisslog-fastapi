"""
FastAPI WebSocket resolver for Bisslog-based use case routing.

This module defines a resolver that dynamically registers WebSocket endpoints
in a FastAPI application from Bisslog "use case" metadata. It maps incoming
WebSocket messages into use case inputs via a configurable Mapper, supports
both synchronous and asynchronous use cases without blocking the event loop,
and provides a simple strategy to derive a path from the trigger metadata.
"""

from __future__ import annotations

from typing import Any, Callable

from bisslog_schema.schema import UseCaseInfo, TriggerInfo
from fastapi import FastAPI

from .fastapi_resolver import BisslogFastApiResolver


class BisslogFastAPIWebSocketResolver(BisslogFastApiResolver):
    """
    FastAPI resolver that registers WebSocket routes from Bisslog metadata.

    This resolver binds WebSocket triggers (identified by a ``route_key`` and an
    optional custom ``path``) to callable use cases. It handles message receive,
    mapping, use case execution, and response sending for each message until the
    client disconnects.

    Notes
    -----
    - If a use case is synchronous, it is executed with ``run_in_threadpool`` to
      avoid blocking the asyncio event loop.
    - The resolver attempts to receive JSON messages first; if decoding fails, it
      falls back to raw text. Mapped inputs use keys: ``route_key``, ``connection_id``,
      ``body``, and ``headers``.
    """

    def __call__(
        self,
        app: FastAPI,
        use_case_info: UseCaseInfo,
        trigger_info: TriggerInfo,
        use_case_callable: Callable[..., Any],
        **kwargs: Any,
    ) -> None:
        """
        Register a WebSocket use case using this resolver.

        Parameters
        ----------
        app : FastAPI
            The FastAPI application instance.
        use_case_info : UseCaseInfo
            Use case metadata used for diagnostics and naming.
        trigger_info : TriggerInfo
            Trigger metadata (must carry a ``TriggerWebsocket`` in ``options``).
        use_case_callable : Callable[..., Any]
            The callable implementing the use case. It may be sync or async.
        **kwargs : Any
            Extra keyword arguments reserved for future extensions.

        Returns
        -------
        None
        """
        raise NotImplementedError
