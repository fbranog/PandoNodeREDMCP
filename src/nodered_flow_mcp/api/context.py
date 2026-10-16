from __future__ import annotations

from urllib.parse import quote

from .client import NodeRedClient, NodeRedError

# NOTE: /context/* is the editor's endpoint. It is NOT part of the documented Admin API.

SCOPES = {"global", "flow", "node"}


def _path(scope: str, ident: str | None, key: str | None) -> str:
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {sorted(SCOPES)}")
    p = f"/context/{scope}"
    if scope != "global":
        if not ident:
            raise ValueError(f"{scope} scope requires an id")
        p += f"/{quote(ident, safe='')}"
    if key:
        p += f"/{quote(key, safe='')}"
    return p


async def read_context(c: NodeRedClient, scope: str, ident: str | None = None, key: str | None = None, store: str | None = None):
    path = _path(scope, ident, key)
    if store:
        path += f"?store={quote(store)}"
    return await c.get_json(path)


async def probe(c: NodeRedClient) -> dict:
    try:
        data = await c.get_json("/context/global")
        return {"available": True, "keys_in_default_store": list(data.keys()) if isinstance(data, dict) else None}
    except NodeRedError as e:
        return {"available": False, "reason": f"HTTP {e.status}"}
