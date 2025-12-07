"""Trigger processor base class definition."""

from abc import ABC, abstractmethod
from typing import Union, Any, Callable, Optional

from bisslog_schema.schema import TriggerHttp, TriggerWebsocket
from bisslog_schema.use_case_code_inspector.use_case_code_metadata import UseCaseCodeInfo

from ..static_python_construct_data import StaticPythonConstructData


class TriggerProcessor(ABC):
    """Abstract base class for trigger processors."""

    @abstractmethod
    def __call__(
        self, use_case_key: str, uc_var_name: str, uc_info: UseCaseCodeInfo,
        trigger_info: Union[TriggerHttp, TriggerWebsocket],
        callable_obj: Callable[..., Any], identifier: int,
        use_case_name: Optional[str] = None, use_case_description: Optional[str] = None,
    ) -> StaticPythonConstructData:
        """Generates a FastAPI route handler for a trigger.

        The handler signature is derived from the mapper and the use case
        callable annotations, using FastAPI's declarative parameter types
        (Path, Body, Query, Header, Depends, etc.).

        The handler is declared as `async def` if the use case callable
        is coroutine, otherwise as a synchronous `def`."""
        raise NotImplementedError
