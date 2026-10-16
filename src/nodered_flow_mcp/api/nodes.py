from __future__ import annotations

from .client import NodeRedClient


async def list_node_sets(c: NodeRedClient) -> list[dict]:
    return await c.get_json("/nodes", headers={"Accept": "application/json"})


async def get_set_html(c: NodeRedClient, module: str, set_name: str) -> str:
    r = await c.request("GET", f"/nodes/{module}/{set_name}", accept_html=True)
    return r.text


async def get_all_html(c: NodeRedClient) -> str:
    r = await c.request("GET", "/nodes", accept_html=True)
    return r.text
