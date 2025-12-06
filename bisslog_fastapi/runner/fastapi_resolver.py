"""
Abstract base class for Bisslog FastApi route resolvers.

This module defines a common interface for resolving use case routes
in a FastApi application. Subclasses implement logic to register routes
based on different trigger types.
"""
from abc import abstractmethod, ABC
from typing import Callable

from bisslog_schema.schema import UseCaseInfo, TriggerInfo
from fastapi import FastAPI


class BisslogFastApiResolver(ABC):
    """Abstract base class for registering use case routes in a FastApi application.

    Implementations of this class handle the translation of trigger metadata
    into concrete route registration logic, such as for HTTP or WebSocket endpoints."""

    @abstractmethod
    def __call__(self, app: FastAPI, use_case_info: UseCaseInfo,
                 trigger_info: TriggerInfo, use_case_callable: Callable, **kwargs) -> Callable:
        """
        Registers a use case route in a FastApi app based on the given trigger.

        Parameters
        ----------
        app : FastAPI
            The Fastapi application instance where the route should be registered.
        use_case_info : UseCaseInfo
            Metadata describing the use case, including name and key.
        trigger_info : TriggerInfo
            Trigger metadata describing how the route is activated.
        use_case_callable : Callable
            The function or class instance that implements the use case logic.

        Raises
        ------
        NotImplementedError
            If the method is not implemented by a subclass.
        """
        raise NotImplementedError
