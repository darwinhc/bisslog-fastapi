"""
Unit tests for BisslogFastAPIWebSocketResolver class.
"""
from unittest.mock import MagicMock

import pytest
from bisslog_schema.schema import UseCaseInfo, TriggerInfo
from bisslog_schema.schema.triggers.trigger_websocket import TriggerWebsocket
from fastapi import FastAPI

from bisslog_fastapi.runner.fastapi_ws_resolver import BisslogFastAPIWebSocketResolver


@pytest.fixture
def ws_resolver():
    return BisslogFastAPIWebSocketResolver()


@pytest.fixture
def mock_app():
    return MagicMock(spec=FastAPI)


def test_ws_resolver_not_implemented(ws_resolver, mock_app):
    """Test that the resolver raises NotImplementedError currently."""

    # Setup
    trigger_opt = TriggerWebsocket(route_key="myroute")
    trigger = TriggerInfo(type="websocket", keyname="t1", options=trigger_opt)

    use_case_info = UseCaseInfo(name="Chat", description="Chat UC", triggers=[trigger])
    use_case_callable = lambda: None

    # Act & Assert
    with pytest.raises(NotImplementedError):
        ws_resolver(
            app=mock_app,
            use_case_info=use_case_info,
            trigger_info=trigger,
            use_case_callable=use_case_callable
        )
