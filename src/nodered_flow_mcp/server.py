from __future__ import annotations

import logging
import sys

from fastmcp import FastMCP

from .state import AppState
from .tools import deployment, discovery, editing, knowledge


def build_server(state: AppState | None = None) -> FastMCP:
    st = state or AppState()
    mcp = FastMCP("nodered-flow-mcp", instructions=(
        "Engineering interface to Node-RED. Inspect flows, learn node schemas and patterns from the library, "
        "build changes in a local draft, validate, show the diff, and deploy only with explicit user approval."))
    discovery.register(mcp, st)
    knowledge.register(mcp, st)
    editing.register(mcp, st)
    deployment.register(mcp, st)
    return mcp


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)  # stdout is reserved for MCP
    build_server().run()


if __name__ == "__main__":
    main()
