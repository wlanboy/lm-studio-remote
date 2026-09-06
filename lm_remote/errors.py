"""Shared helper for running an LM Studio client call from a worker and
logging failures instead of propagating them."""

from __future__ import annotations

from collections.abc import Awaitable

import httpx2

from lm_remote.protocols import AppStateBase


async def call_or_log[T](state: AppStateBase, awaitable: Awaitable[T], error_prefix: str) -> T | None:
    """Await `awaitable`, logging `"{error_prefix}: {exc}"` and returning
    None on an HTTP/connection failure instead of letting it propagate."""
    try:
        return await awaitable
    except (httpx2.HTTPError, OSError) as exc:
        state.log_message(f"{error_prefix}: {exc}", "error")
        return None
