from __future__ import annotations

from .client import NodeRedClient

V2 = {"Node-RED-API-Version": "v2"}
DEPLOY_TYPES = {"full", "nodes", "flows", "reload"}


async def get_flows(c: NodeRedClient) -> dict:
    """Returns {'rev': str, 'flows': [...]}"""
    return await c.get_json("/flows", headers=V2)


async def post_flows(c: NodeRedClient, flows: list[dict], rev: str | None, deployment_type: str = "nodes") -> str | None:
    if deployment_type not in DEPLOY_TYPES:
        raise ValueError(f"deployment_type must be one of {sorted(DEPLOY_TYPES)}")
    body: dict = {"flows": flows}
    if rev is not None:
        body["rev"] = rev
    r = await c.request(
        "POST", "/flows", headers={**V2, "Node-RED-Deployment-Type": deployment_type}, json=body
    )
    return r.json().get("rev") if r.content else None


async def get_flows_state(c: NodeRedClient) -> dict:
    return await c.get_json("/flows/state")
