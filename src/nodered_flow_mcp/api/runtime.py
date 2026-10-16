from __future__ import annotations

from .client import NodeRedClient, NodeRedError


async def get_settings(c: NodeRedClient) -> dict:
    return await c.get_json("/settings")


async def get_diagnostics(c: NodeRedClient) -> dict | None:
    try:
        return await c.get_json("/diagnostics")
    except NodeRedError as e:
        if e.status in (404, 403):
            return None
        raise
