from __future__ import annotations

import json
from pathlib import Path

from ..api import context as ctx_api
from ..api import flows as flows_api
from ..api import nodes as nodes_api
from ..api import runtime as rt_api
from ..api.client import NodeRedError
from ..domain.graph import Graph, is_config, iter_wire_targets
from ..state import AppState

SAFE_SETTINGS = ("httpNodeRoot", "version", "user", "context", "flowFilePretty", "externalModules", "runtimeState",
                 "editorTheme", "functionExternalModules", "libraries", "diagnostics", "telemetryEnabled", "tlsConfigDisableLocalFiles")


def register(mcp, st: AppState):
    @mcp.tool
    async def get_runtime_info() -> dict:
        """Node-RED version, selected settings, and which optional capabilities are available."""
        c = st.client
        scheme = await c.auth_scheme()
        s = await rt_api.get_settings(c)
        diag = await rt_api.get_diagnostics(c)
        state = None
        if (s.get("runtimeState") or {}).get("enabled"):
            state = await flows_api.get_flows_state(c)
        ctxp = await ctx_api.probe(c)
        return {
            "version": s.get("version") or (diag or {}).get("runtime", {}).get("version"),
            "auth": scheme.get("type", "none"),
            "settings": {k: s[k] for k in SAFE_SETTINGS if k in s},
            "capabilities": {
                "flows_state": bool((s.get("runtimeState") or {}).get("enabled")),
                "diagnostics": diag is not None,
                "context_endpoint_unofficial": ctxp["available"],
                "projects": bool((s.get("editorTheme") or {}).get("projects", {}).get("enabled")),
            },
            "flows_state": state,
            "read_only_mode": st.settings.read_only,
        }

    @mcp.tool
    async def list_flows() -> dict:
        """List tabs, subflows and config-node counts of the active configuration, with the current revision."""
        data = await flows_api.get_flows(st.client)
        g = Graph(data["flows"])
        return {
            "rev": data["rev"],
            "tabs": [{"id": t["id"], "label": t.get("label"), "disabled": t.get("disabled", False),
                      "node_count": len(g.nodes_in(t["id"]))} for t in g.tabs],
            "subflows": [{"id": s["id"], "name": s.get("name"), "node_count": len(g.nodes_in(s["id"]))} for s in g.subflows],
            "global_config_nodes": sum(1 for n in g.configs if not n.get("z")),
        }

    @mcp.tool
    async def get_flow(flow_id: str, include_nodes: bool = True) -> dict:
        """Get a tab or subflow: its nodes (with wiring) and the config nodes they use."""
        data = await flows_api.get_flows(st.client)
        g = Graph(data["flows"])
        c = g.by_id.get(flow_id)
        if not c or c.get("type") not in ("tab", "subflow"):
            raise ValueError(f"{flow_id} is not a tab or subflow")
        members = g.nodes_in(flow_id)
        used = {r for m in members for r in g.references(m).values() if r in g.by_id and is_config(g.by_id[r])}
        out = {"rev": data["rev"], "container": c, "node_count": len(members),
               "config_nodes_used": [{"id": i, "type": g.by_id[i]["type"], "name": g.by_id[i].get("name")} for i in used]}
        if include_nodes:
            out["nodes"] = members
        else:
            out["topology"] = g.topology(flow_id)
        return out

    @mcp.tool
    async def get_node_details(node_id: str) -> dict:
        """Full properties of a node plus inbound/outbound wires and resolved references."""
        data = await flows_api.get_flows(st.client)
        g = Graph(data["flows"])
        n = g.by_id.get(node_id)
        if not n:
            raise ValueError(f"node {node_id} not found")
        inb = g.inbound().get(node_id, [])
        return {
            "node": n,
            "outbound": [{"port": p, "to": t, "to_type": g.by_id.get(t, {}).get("type")} for p, t in iter_wire_targets(n)],
            "inbound": [{"from": s, "port": p, "from_type": g.by_id[s].get("type")} for s, p in inb],
            "references": {k: {"id": v, "type": g.by_id[v].get("type")} for k, v in g.references(n).items()},
            "used_by": g.config_refs(node_id) if is_config(n) else [],
        }

    @mcp.tool
    async def list_installed_nodes(include_core: bool = False) -> dict:
        """Installed node sets and the node types they provide. Core node-red sets are hidden by default."""
        sets = await nodes_api.list_node_sets(st.client)
        res = [s for s in sets if include_core or s.get("module") != "node-red"]
        return {"count": len(res), "sets": [{"module": s.get("module"), "name": s.get("name"), "version": s.get("version"),
                "enabled": s.get("enabled"), "types": s.get("types"), "err": s.get("err")} for s in res]}

    @mcp.tool
    async def get_config_nodes(type_filter: str | None = None) -> list[dict]:
        """Config nodes (shared configuration) with the ids of nodes that reference each."""
        data = await flows_api.get_flows(st.client)
        g = Graph(data["flows"])
        return [{"id": n["id"], "type": n["type"], "name": n.get("name"), "scope": n.get("z") or "global",
                 "used_by": g.config_refs(n["id"])}
                for n in g.configs if not type_filter or n["type"] == type_filter]

    @mcp.tool
    async def export_flows(path: str) -> dict:
        """Save a snapshot of the active flows (no credentials) to a local JSON file."""
        data = await flows_api.get_flows(st.client)
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data["flows"], indent=2))
        return {"path": str(p), "rev": data["rev"], "nodes": len(data["flows"])}

    @mcp.tool
    async def inspect_runtime_state() -> dict:
        """Runtime flow state (started/stopped). Only available when settings.runtimeState.enabled is true."""
        s = await rt_api.get_settings(st.client)
        if not (s.get("runtimeState") or {}).get("enabled"):
            return {"available": False, "reason": "runtimeState.enabled is not set in settings.js"}
        return {"available": True, **(await flows_api.get_flows_state(st.client))}

    # ---- context (read-only; uses the editor's undocumented endpoint) ----
    @mcp.tool
    async def inspect_context_capabilities() -> dict:
        """Check whether live context reads work. Uses an UNDOCUMENTED editor endpoint; may change between versions."""
        return {**(await ctx_api.probe(st.client)), "writes": "not supported", "stability": "unofficial"}

    @mcp.tool
    async def read_global_context(key: str | None = None, store: str | None = None):
        """Read global context (all keys, or one key)."""
        return await _safe(ctx_api.read_context(st.client, "global", None, key, store))

    @mcp.tool
    async def read_flow_context(flow_id: str, key: str | None = None, store: str | None = None):
        """Read flow context for a tab id."""
        return await _safe(ctx_api.read_context(st.client, "flow", flow_id, key, store))

    @mcp.tool
    async def read_node_context(node_id: str, key: str | None = None, store: str | None = None):
        """Read a node's private context."""
        return await _safe(ctx_api.read_context(st.client, "node", node_id, key, store))

    @mcp.resource("nodered://flows")
    async def flows_resource() -> str:
        """Overview of the active flows."""
        data = await flows_api.get_flows(st.client)
        g = Graph(data["flows"])
        return json.dumps({"rev": data["rev"], "tabs": [{"id": t["id"], "label": t.get("label")} for t in g.tabs]}, indent=2)

    @mcp.resource("nodered://flows/{flow_id}")
    async def flow_resource(flow_id: str) -> str:
        """A single tab/subflow with its nodes."""
        data = await flows_api.get_flows(st.client)
        g = Graph(data["flows"])
        if flow_id not in g.by_id:
            raise ValueError("unknown flow")
        return json.dumps([g.by_id[flow_id]] + g.nodes_in(flow_id), indent=2)


async def _safe(coro):
    try:
        return await coro
    except NodeRedError as e:
        return {"error": str(e), "hint": "context endpoint is unofficial; check inspect_context_capabilities"}
