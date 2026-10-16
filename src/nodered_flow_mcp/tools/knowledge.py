from __future__ import annotations

import json

from ..registry.config_registry import config_types
from ..state import AppState


def register(mcp, st: AppState):
    @mcp.tool
    async def get_node_schema(node_type: str, refresh: bool = False) -> dict:
        """Property schema of a node type (parsed from the installed editor definition) plus curated knowledge, each tagged with provenance."""
        reg = await st.ensure_registry(force=refresh)
        d = reg.describe(node_type)
        if d is None:
            raise ValueError(f"unknown node type '{node_type}'")
        return d

    @mcp.tool
    async def get_node_usage_rules(node_type: str) -> dict:
        """Curated usage rules for a node type. provenance = verified | observed | proposed."""
        reg = await st.ensure_registry()
        return reg.usage(node_type)

    @mcp.tool
    async def get_config_node_schema(config_type: str) -> dict:
        """Schema of a config node type and which node types/properties reference it."""
        reg = await st.ensure_registry()
        return {"schema": reg.describe(config_type), "referenced_by": config_types(reg).get(config_type, [])}

    @mcp.tool
    async def search_flow_patterns(node_types: list[str] | None = None, query: str | None = None, limit: int = 10) -> dict:
        """Find examples in the local flow library (observed from your working flows) and curated patterns."""
        pats = st.library.patterns()
        q = (query or "").lower()
        cur = [{"pattern": k, "purpose": v.get("purpose"), "provenance": v.get("provenance")} for k, v in pats.items()
               if not q or q in json.dumps(v).lower()]
        return {"curated_patterns": cur, "examples": st.library.search(node_types, query, limit)}

    @mcp.tool
    async def get_pattern(name: str) -> dict:
        """A curated pattern's files: metadata, flow.json, constraints, validation rules, limitations."""
        return st.library.pattern_files(name)

    @mcp.tool
    async def get_example(example_ref: str, include_configs: bool = True) -> list[dict]:
        """Nodes of an example tab ('<project>/<file>.json#<tab_id>' from search_flow_patterns). Credentials are never included."""
        file_key, tab_id = example_ref.split("#", 1)
        return st.library.tab_nodes(file_key, tab_id, include_configs)

    @mcp.resource("nodered://nodes")
    async def nodes_resource() -> str:
        reg = await st.ensure_registry()
        return json.dumps({t: {"module": s.module, "category": s.category} for t, s in sorted(reg.schemas.items())}, indent=2)

    @mcp.resource("nodered://nodes/{node_type}")
    async def node_resource(node_type: str) -> str:
        reg = await st.ensure_registry()
        return json.dumps(reg.describe(node_type), indent=2)

    @mcp.resource("nodered://patterns/{name}")
    def pattern_resource(name: str) -> str:
        return json.dumps(st.library.pattern_files(name), indent=2)

    @mcp.prompt
    def design_polling_flow(goal: str) -> str:
        """Plan a polling flow."""
        return _PROMPT.format(kind="polling flow", goal=goal, search="polling", checks=(
            "- polling interval, timeout and retry policy\n- overlap prevention (do not start a poll while one is in flight)\n"
            "- a defined stop condition or lifecycle"))

    @mcp.prompt
    def design_queue_processor(goal: str) -> str:
        """Plan a queue/outbox processor."""
        return _PROMPT.format(kind="queue processor", goal=goal, search="outbox queue", checks=(
            "- job state transitions and failure handling\n- duplicate-processing assumptions and retries\n"
            "- event-driven trigger vs polling fallback; context is not a durable queue"))

    @mcp.prompt
    def design_http_api_flow(goal: str) -> str:
        """Plan an HTTP/API flow."""
        return _PROMPT.format(kind="HTTP API flow", goal=goal, search="http-receive api-connect", checks=(
            "- every request path ends in a response (http response or sse-response)\n"
            "- upstream error and timeout handling\n- auth conventions"))


_PROMPT = """You are designing a Node-RED {kind}. Goal: {goal}

Workflow (do not skip steps):
1. Understand: list_flows, then search_flow_patterns (try: {search}) and get_example for the closest matches.
   Distinguish verified behavior, observed project conventions, and your own proposals.
2. For every node type you plan to use: get_node_schema and get_node_usage_rules. Never invent property names.
3. Design: describe topology and execution semantics. Cover:
{checks}
4. Construct: create_flow_draft, then add_node / connect_nodes / create_or_update_config_node.
5. Validate: validate_flow. Fix all errors; explain warnings.
6. Review: diff_flow_changes, show the user, and deploy_flow_changes ONLY after explicit approval.
"""
