from __future__ import annotations

from collections import defaultdict
from typing import Any

Node = dict[str, Any]

NON_NODE = {"tab", "subflow"}


def is_config(n: Node) -> bool:
    """Config nodes have no canvas position and are not tabs/subflows."""
    return n.get("type") not in NON_NODE and "x" not in n and "y" not in n


def is_container(n: Node) -> bool:
    return n.get("type") in NON_NODE


def iter_wire_targets(n: Node):
    """Yield (port, target_id)."""
    for port, targets in enumerate(n.get("wires") or []):
        for t in targets or []:
            yield port, t


class Graph:
    def __init__(self, nodes: list[Node]):
        self.nodes = nodes
        self.by_id: dict[str, Node] = {}
        self.duplicate_ids: list[str] = []
        for n in nodes:
            i = n.get("id")
            if i in self.by_id:
                self.duplicate_ids.append(i)
            self.by_id[i] = n

    @property
    def tabs(self) -> list[Node]:
        return [n for n in self.nodes if n.get("type") == "tab"]

    @property
    def subflows(self) -> list[Node]:
        return [n for n in self.nodes if n.get("type") == "subflow"]

    @property
    def configs(self) -> list[Node]:
        return [n for n in self.nodes if is_config(n)]

    def nodes_in(self, container_id: str) -> list[Node]:
        return [n for n in self.nodes if n.get("z") == container_id and not is_container(n)]

    def inbound(self) -> dict[str, list[tuple[str, int]]]:
        inb: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for n in self.nodes:
            for port, t in iter_wire_targets(n):
                inb[t].append((n["id"], port))
        return inb

    def link_targets(self, n: Node) -> list[str]:
        """Effective link-out destinations (for 'link out' nodes in link mode)."""
        return list(n.get("links") or []) if n.get("type") in ("link out", "link in") else []

    def config_refs(self, config_id: str) -> list[str]:
        """Ids of nodes that reference this config node in any top-level string property."""
        out = []
        for n in self.nodes:
            if n.get("id") == config_id:
                continue
            for k, v in n.items():
                if k in ("id", "z", "g", "wires", "links") or not isinstance(v, str):
                    continue
                if v == config_id:
                    out.append(n["id"])
                    break
        return out

    def references(self, n: Node) -> dict[str, str]:
        """property -> referenced node id, for string props that equal an existing node id."""
        refs = {}
        for k, v in n.items():
            if k in ("id", "z", "g", "wires", "links", "x", "y") or not isinstance(v, str):
                continue
            if v and v in self.by_id and v != n.get("id"):
                refs[k] = v
        return refs

    def topology(self, container_id: str) -> list[dict]:
        out = []
        for n in self.nodes_in(container_id):
            out.append(
                {
                    "id": n["id"],
                    "type": n.get("type"),
                    "name": n.get("name", ""),
                    "wires_out": [
                        [t for t in (ts or [])] for ts in (n.get("wires") or [])
                    ],
                }
            )
        return out
