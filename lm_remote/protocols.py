"""Shared base `Protocol` for the `self` annotations the App mixins use.

Each mixin (`ConnectionMixin`, `ServerDiscoveryMixin`, `LoadUnloadMixin`,
`ModelsTableMixin`) is only ever mixed into `LMStudioRemoteApp`. Protocol
classes let each mixin's methods be type-checked against just the App
members they actually use, without depending on the concrete App class.
"""

from __future__ import annotations

from typing import Any, Protocol


class AppStateBase(Protocol):
    """Members every App mixin's `self` annotation needs.

    Used only as a `self` annotation, never as a real base class, so it
    doesn't affect the runtime MRO of `LMStudioRemoteApp`.
    """

    def log_message(self, message: str, level: str = ...) -> None: ...
    def query_one(self, *args: Any, **kwargs: Any) -> Any: ...
