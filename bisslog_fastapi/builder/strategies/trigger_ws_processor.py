"""Processor for WebSocket triggers definition"""

from typing import Any, Callable, Optional

from bisslog_schema.schema import TriggerWebsocket
from bisslog_schema.use_case_code_inspector.use_case_code_metadata import UseCaseCodeInfo

from bisslog_fastapi.builder.static_python_construct_data import StaticPythonConstructData
from bisslog_fastapi.builder.strategies.trigger_processor import TriggerProcessor


class TriggerWebsocketProcessor(TriggerProcessor):
    """Processor for WebSocket triggers."""

    def __call__(
        self, use_case_key: str, uc_var_name: str, uc_info: UseCaseCodeInfo,
        trigger_info: TriggerWebsocket, callable_obj: Callable[..., Any], identifier: int,
        use_case_name: Optional[str] = None, use_case_description: Optional[str] = None,
    ) -> StaticPythonConstructData:
        """
        Generates a basic WebSocket handler for FastAPI.

        This is intentionally simple; you can extend it to map messages via a
        mapper if needed.
        """
        raise NotImplementedError
