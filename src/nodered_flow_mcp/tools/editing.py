from __future__ import annotations

from ..api import flows as flows_api
from ..domain.draft import Draft, DraftError
from ..domain.graph import is_config
from ..state import AppState


def register(mcp, st: AppState):
    def _d(draft_id: str) -> Draft:
        return st.load_draft(draft_id)

    @mcp.tool
    async def create_flow_draft() -> dict:
        """Snapshot the active flows (with revision) into a new local draft. Nothing is changed in Node-RED."""
        data = await flows_api.get_flows(st.client)
        d = Draft.create(data["rev"], data["flows"])
        st.save_draft(d)
        return {"draft_id": d.id, "base_rev": d.base_rev, "node_count": len(d.nodes)}

    @mcp.tool
    async def add_node(draft_id: str, node_type: str, tab_id: str, properties: dict | None = None) -> dict:
        """Add a canvas node to a tab. Unknown node types are rejected; wires start empty. Do not pass credentials."""
        reg = await st.ensure_registry()
        d = _d(draft_id)
        n = d.add_node(node_type, tab_id, properties, reg)
        st.save_draft(d)
        return {"node": n}

    @mcp.tool
    async def add_tab(draft_id: str, label: str) -> dict:
        """Add a new empty tab."""
        d = _d(draft_id)
        n = d.add_node("tab", None, {"label": label})
        st.save_draft(d)
        return {"node": n}

    @mcp.tool
    async def update_node(draft_id: str, node_id: str, properties: dict) -> dict:
        """Update properties of a node (not id/type/wires)."""
        d = _d(draft_id)
        n = d.update_node(node_id, properties)
        st.save_draft(d)
        return {"node": n}

    @mcp.tool
    async def delete_node(draft_id: str, node_id: str) -> dict:
        """Delete a node (or a tab with its contents); wires/links to it are cleaned up."""
        d = _d(draft_id)
        r = d.delete_node(node_id)
        st.save_draft(d)
        return r

    @mcp.tool
    async def connect_nodes(draft_id: str, source_id: str, target_id: str, source_port: int = 0) -> dict:
        """Wire a source output port to a target."""
        d = _d(draft_id)
        d.connect(source_id, target_id, source_port)
        st.save_draft(d)
        return {"wires": d._get(source_id)["wires"]}

    @mcp.tool
    async def disconnect_nodes(draft_id: str, source_id: str, target_id: str, source_port: int | None = None) -> dict:
        """Remove wire(s) from source to target."""
        d = _d(draft_id)
        d.disconnect(source_id, target_id, source_port)
        st.save_draft(d)
        return {"wires": d._get(source_id)["wires"]}

    @mcp.tool
    async def create_or_update_config_node(draft_id: str, node_type: str, properties: dict, node_id: str | None = None,
                                           tab_id: str | None = None) -> dict:
        """Create (or update if node_id exists) a config node. tab_id scopes it to a flow; omit for global. Credentials are not accepted."""
        reg = await st.ensure_registry()
        d = _d(draft_id)
        if "credentials" in properties:
            raise DraftError("credentials are not accepted; set them in the Node-RED editor")
        if node_id and any(n.get("id") == node_id for n in d.nodes):
            n = d.update_node(node_id, properties)
            if not is_config(n):
                raise DraftError(f"{node_id} is not a config node")
        else:
            n = d.add_node(node_type, tab_id, {**properties, "_config": True}, reg, node_id=node_id)
        st.save_draft(d)
        return {"node": n}

    @mcp.tool
    async def import_pattern_into_draft(draft_id: str, example_ref: str, tab_id: str) -> dict:
        """Copy an example tab's nodes into a draft tab with fresh ids and remapped wires.
        Config nodes are NOT copied; point references at existing config nodes afterwards (validate_flow flags dangling ones)."""
        d = _d(draft_id)
        file_key, src_tab = example_ref.split("#", 1)
        nodes = st.library.tab_nodes(file_key, src_tab, include_configs=False)
        mapping = d.import_nodes(nodes, tab_id, await st.ensure_registry())
        st.save_draft(d)
        return {"imported": len(mapping), "id_map": mapping}

    @mcp.tool
    async def get_draft(draft_id: str) -> dict:
        """Draft summary."""
        d = _d(draft_id)
        return {"draft_id": d.id, "base_rev": d.base_rev, "node_count": len(d.nodes), "touched": sorted(d.touched), "ops": len(d.ops)}
