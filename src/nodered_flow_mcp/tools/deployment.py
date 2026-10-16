from __future__ import annotations

import json

from ..api import flows as flows_api
from ..domain import deploy as dep
from ..domain.draft import Draft
from ..domain.validation import validate
from ..state import AppState


def register(mcp, st: AppState):
    @mcp.tool
    async def validate_flow(draft_id: str) -> dict:
        """Validate a draft: structure, wires/ports, config refs, required props, response paths, preservation of untouched nodes."""
        reg = await st.ensure_registry()
        d = st.load_draft(draft_id)
        return validate(d.nodes, reg, base=d.base, touched=d.touched)

    @mcp.tool
    async def diff_flow_changes(draft_id: str, deployment_type: str = "nodes") -> dict:
        """Diff of draft vs its base snapshot, validation result, and (if valid) the approval token needed to deploy."""
        reg = await st.ensure_registry()
        return dep.review(st.load_draft(draft_id), reg, deployment_type)

    @mcp.tool
    async def deploy_flow_changes(draft_id: str, approval_token: str, deployment_type: str = "nodes") -> dict:
        """Deploy a draft. Requires the approval_token from diff_flow_changes; use it ONLY after the USER approved the diff.
        Uses Admin API v2 with the base revision; a changed runtime yields a conflict instead of overwriting."""
        reg = await st.ensure_registry()
        d = st.load_draft(draft_id)
        res = await dep.deploy(st.client, d, reg, approval_token, deployment_type)
        if res.get("deployed"):
            snap = st.settings.drafts_dir / f"{d.id}.predeploy.json"
            snap.write_text(json.dumps(res.pop("pre_deploy_snapshot")))
            res["rollback_snapshot"] = str(snap)
        return res

    @mcp.tool
    async def rebase_draft(draft_id: str) -> dict:
        """Recreate a draft on the current runtime flows and replay its recorded edit operations."""
        reg = await st.ensure_registry()
        old = st.load_draft(draft_id)
        data = await flows_api.get_flows(st.client)
        new = Draft(old.id, data["rev"], data["flows"])
        new.replay(old.ops, reg)
        st.save_draft(new)
        return {"draft_id": new.id, "base_rev": new.base_rev, "replayed_ops": len(old.ops),
                "validation": validate(new.nodes, reg, base=new.base, touched=new.touched)["counts"]}
