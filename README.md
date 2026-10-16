# nodered-flow-mcp

Local stdio MCP server (FastMCP 2.x) for engineering Node-RED flows through the Admin API.
Flow: inspect -> learn schemas/patterns -> edit a local draft -> validate -> diff -> approved deploy.

## Setup

```
uv sync
cp .env.example .env     # set NODERED_URL and auth
uv run pytest
```

MCP client config (opencode `mcp` / Claude-style):

```json
{"command": ["uv", "run", "--directory", "/home/frank/Programs/working/nodered_mcp", "nodered-flow-mcp"]}
```

## Safety model

- `NODERED_READ_ONLY=true` (default): token scope is `read`, `deploy_flow_changes` refuses. Drafts are local files only.
- Deploy needs the `approval_token` from `diff_flow_changes`. It is bound to the draft content, base revision and deployment type, so any later edit invalidates it. Give it to the tool only after the user approves the diff.
- Deploys use Admin API v2 with the draft's base `rev`. If the runtime changed you get a conflict, never an overwrite. Use `rebase_draft` to replay the edits.
- Default deployment type is `nodes`. `full` must be requested explicitly.
- Credentials are never read, copied or accepted. `*_cred.json` files are skipped by the library loader.
- Pre-deploy snapshot is saved next to the draft (`<id>.predeploy.json`) for manual rollback by re-posting.

## Knowledge provenance

- Node schemas are parsed from the installed nodes' editor HTML (`GET /nodes/:module/:set`). Types that cannot be parsed are flagged, not guessed.
- `registry/overlays/*.yaml` hold curated rules tagged `verified | observed | proposed`. The current custom-node overlays are `observed` from `reference/projects`. Upgrade them to `verified` after reading the node sources.
- Pattern library: `src/nodered_flow_mcp/patterns/<name>/` (see its README). It is empty. Outbox/polling patterns still need to be curated.

## Known gaps

- Context reads use the editor's `/context/*` endpoint, which is **not** a documented Admin API. Writes are not implemented.
- Projects tooling (section D of the design) is not implemented. The documented Admin API has no project endpoints.
- Static rules are heuristic (response reachability, context key usage). Polling stop-conditions and queue-worker rules need curated patterns.
- Not tested against a live Node-RED instance yet.
