from __future__ import annotations

import hashlib
import json

from ..api import flows as flows_api
from ..api.client import NodeRedClient, RevisionConflict
from .diff import canonical_hash, diff_flows
from .draft import Draft
from .validation import validate


def approval_token(draft: Draft, deployment_type: str) -> str:
    h = hashlib.sha256(f"{draft.id}|{draft.base_rev}|{canonical_hash(draft.nodes)}|{deployment_type}".encode())
    return h.hexdigest()[:24]


def review(draft: Draft, reg, deployment_type: str = "nodes") -> dict:
    d = diff_flows(draft.base, draft.nodes)
    v = validate(draft.nodes, reg, base=draft.base, touched=draft.touched)
    return {
        "draft_id": draft.id,
        "base_rev": draft.base_rev,
        "deployment_type": deployment_type,
        "diff": d,
        "validation": v,
        "approval_token": approval_token(draft, deployment_type) if v["ok"] else None,
        "note": "Present this diff to the user. Call deploy_flow_changes with approval_token only after explicit approval."
        if v["ok"] else "Fix validation errors; no approval token issued.",
    }


async def deploy(client: NodeRedClient, draft: Draft, reg, token: str, deployment_type: str = "nodes") -> dict:
    if client.settings.read_only:
        raise PermissionError("server is in read-only mode (NODERED_READ_ONLY=true)")
    if token != approval_token(draft, deployment_type):
        raise PermissionError("approval token does not match current draft; run diff_flow_changes again")
    v = validate(draft.nodes, reg, base=draft.base, touched=draft.touched)
    if not v["ok"]:
        raise ValueError("draft no longer validates")
    try:
        before = await flows_api.get_flows(client)
        if before["rev"] != draft.base_rev:
            raise RevisionConflict(409, "runtime flows changed since draft was created; rebase the draft", None)
        snapshot = before["flows"]
        new_rev = await flows_api.post_flows(client, draft.nodes, draft.base_rev, deployment_type)
    except RevisionConflict as e:
        return {"deployed": False, "conflict": True, "message": str(e), "hint": "call rebase_draft"}
    after = await flows_api.get_flows(client)
    ids_after = {n["id"] for n in after["flows"]}
    missing = [n["id"] for n in draft.nodes if n["id"] not in ids_after]
    return {
        "deployed": True, "new_rev": new_rev or after["rev"], "verified": not missing,
        "missing_after_deploy": missing, "pre_deploy_snapshot": snapshot,
    }
