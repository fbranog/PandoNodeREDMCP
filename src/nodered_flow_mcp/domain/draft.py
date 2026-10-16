from __future__ import annotations

import copy
import json
import secrets
from pathlib import Path
from typing import Any

from ..registry.node_registry import NodeRegistry
from .graph import Graph, is_config, is_container
from .ids import new_id


class DraftError(Exception):
    pass


class Draft:
    def __init__(self, draft_id: str, base_rev: str | None, base: list[dict], nodes: list[dict] | None = None,
                 touched: set[str] | None = None, ops: list[dict] | None = None):
        self.id = draft_id
        self.base_rev = base_rev
        self.base = base
        self.nodes = nodes if nodes is not None else copy.deepcopy(base)
        self.touched: set[str] = touched or set()
        self.ops: list[dict] = ops or []

    # ---- persistence ----
    @classmethod
    def create(cls, base_rev, base) -> "Draft":
        return cls(secrets.token_hex(4), base_rev, base)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{self.id}.json").write_text(json.dumps({
            "id": self.id, "base_rev": self.base_rev, "base": self.base, "nodes": self.nodes,
            "touched": sorted(self.touched), "ops": self.ops}))

    @classmethod
    def load(cls, directory: Path, draft_id: str) -> "Draft":
        p = directory / f"{draft_id}.json"
        if not p.exists() or "/" in draft_id or ".." in draft_id:
            raise DraftError(f"unknown draft {draft_id}")
        d = json.loads(p.read_text())
        return cls(d["id"], d["base_rev"], d["base"], d["nodes"], set(d["touched"]), d["ops"])

    # ---- helpers ----
    def graph(self) -> Graph:
        return Graph(self.nodes)

    def _get(self, node_id: str) -> dict:
        for n in self.nodes:
            if n.get("id") == node_id:
                return n
        raise DraftError(f"node {node_id} not found")

    def _ids(self) -> set[str]:
        return {n.get("id") for n in self.nodes}

    def _log(self, op: str, **args) -> None:
        self.ops.append({"op": op, "args": args})

    def _auto_pos(self, z: str) -> tuple[int, int]:
        xs = [(n.get("x", 0), n.get("y", 0)) for n in self.nodes if n.get("z") == z and "x" in n]
        if not xs:
            return 200, 100
        return 200, max(y for _, y in xs) + 60

    # ---- ops ----
    def add_node(self, node_type: str, z: str | None, properties: dict | None = None, reg: NodeRegistry | None = None,
                 node_id: str | None = None, _log: bool = True) -> dict:
        props = dict(properties or {})
        for forbidden in ("id", "type", "wires"):
            props.pop(forbidden, None)
        nid = node_id or new_id(self._ids())
        if nid in self._ids():
            raise DraftError(f"id {nid} exists")
        n: dict[str, Any] = {"id": nid, "type": node_type}
        sch = reg.schemas.get(node_type) if reg else None
        if sch is None and reg is not None and reg.schemas and node_type not in ("tab", "subflow", "group"):
            raise DraftError(f"unknown node type '{node_type}' (not installed)")
        if node_type == "tab":
            n.update({"label": props.pop("label", "New Flow"), "disabled": False, "info": ""})
        else:
            if z is None and not (props.get("_config") or (sch and "x" not in props and node_type.endswith("config"))):
                pass
            if z is not None:
                if not is_container(self._get(z)):
                    raise DraftError(f"z={z} is not a tab/subflow")
                n["z"] = z
            is_cfg = bool(props.pop("_config", False))
            if not is_cfg:
                if z is None:
                    raise DraftError("z (tab id) required for canvas nodes; pass _config=true for config nodes")
                x, y = props.pop("x", None), props.pop("y", None)
                n["x"], n["y"] = (x, y) if x is not None and y is not None else self._auto_pos(z)
                n["wires"] = [[] for _ in range(self._expected_outputs(node_type, props, reg))]
        n.update(props)
        self.nodes.append(n)
        self.touched.add(nid)
        if _log:
            self._log("add_node", node_type=node_type, z=z, properties=properties or {}, node_id=nid)
        return n

    @staticmethod
    def _expected_outputs(t, props, reg) -> int:
        if isinstance(props.get("outputs"), int):
            return props["outputs"]
        if reg:
            c = reg.output_count({"type": t})
            if c is not None:
                return c
        return 1

    def update_node(self, node_id: str, properties: dict, _log: bool = True) -> dict:
        n = self._get(node_id)
        for k in ("id", "type"):
            if k in properties:
                raise DraftError(f"cannot change '{k}'")
        props = dict(properties)
        wires = props.pop("wires", None)
        if wires is not None:
            raise DraftError("use connect_nodes/disconnect_nodes to change wires")
        n.update(props)
        if "outputs" in props and isinstance(props["outputs"], int) and "wires" in n:
            w = n["wires"]
            n["wires"] = (w + [[] for _ in range(props["outputs"])])[: props["outputs"]]
        self.touched.add(node_id)
        if _log:
            self._log("update_node", node_id=node_id, properties=properties)
        return n

    def delete_node(self, node_id: str, _log: bool = True) -> dict:
        n = self._get(node_id)
        removed = {node_id}
        if n.get("type") in ("tab", "subflow"):
            removed |= {m["id"] for m in self.nodes if m.get("z") == node_id}
        self.nodes = [m for m in self.nodes if m["id"] not in removed]
        for m in self.nodes:
            if "wires" in m:
                changed = False
                new = []
                for port in m["wires"]:
                    kept = [t for t in port if t not in removed]
                    changed |= len(kept) != len(port)
                    new.append(kept)
                if changed:
                    m["wires"] = new
                    self.touched.add(m["id"])
            if m.get("links"):
                k = [l for l in m["links"] if l not in removed]
                if len(k) != len(m["links"]):
                    m["links"] = k
                    self.touched.add(m["id"])
        self.touched |= removed
        if _log:
            self._log("delete_node", node_id=node_id)
        return {"removed": sorted(removed)}

    def connect(self, src: str, dst: str, port: int = 0, _log: bool = True) -> None:
        s, d = self._get(src), self._get(dst)
        if "wires" not in s:
            raise DraftError(f"{src} has no output ports")
        if s.get("z") != d.get("z"):
            raise DraftError("nodes are on different tabs; use link nodes")
        while len(s["wires"]) <= port:
            s["wires"].append([])
        if port < 0:
            raise DraftError("port must be >= 0")
        if dst not in s["wires"][port]:
            s["wires"][port].append(dst)
        self.touched.add(src)
        if _log:
            self._log("connect", src=src, dst=dst, port=port)

    def disconnect(self, src: str, dst: str, port: int | None = None, _log: bool = True) -> None:
        s = self._get(src)
        for p, ts in enumerate(s.get("wires", [])):
            if port is None or p == port:
                s["wires"][p] = [t for t in ts if t != dst]
        self.touched.add(src)
        if _log:
            self._log("disconnect", src=src, dst=dst, port=port)

    def replay(self, ops: list[dict], reg: NodeRegistry | None = None) -> None:
        for o in ops:
            a, op = o["args"], o["op"]
            if op == "add_node":
                self.add_node(a["node_type"], a["z"], a["properties"], reg, node_id=a["node_id"])
            elif op == "update_node":
                self.update_node(a["node_id"], a["properties"])
            elif op == "delete_node":
                self.delete_node(a["node_id"])
            elif op == "connect":
                self.connect(a["src"], a["dst"], a["port"])
            elif op == "disconnect":
                self.disconnect(a["src"], a["dst"], a["port"])
            elif op == "import_pattern":
                self.import_nodes(a["nodes"], a["z"], reg)

    def import_nodes(self, nodes: list[dict], z: str, reg: NodeRegistry | None = None) -> dict[str, str]:
        """Copy nodes into tab z with fresh ids; remap wires, links, groups and intra-set refs."""
        if not is_container(self._get(z)):
            raise DraftError(f"z={z} is not a tab/subflow")
        src_ids = {n["id"] for n in nodes if n.get("type") != "tab"}
        used = self._ids()
        mapping: dict[str, str] = {}
        for i in sorted(src_ids):
            mapping[i] = new_id(used | set(mapping.values()))
        for n in nodes:
            if n.get("type") == "tab":
                continue
            c = copy.deepcopy(n)
            c["id"] = mapping[n["id"]]
            if "x" in c:
                c["z"] = z
            elif c.get("z"):
                c["z"] = z
            if c.get("g") in mapping:
                c["g"] = mapping[c["g"]]
            elif "g" in c:
                del c["g"]
            if "wires" in c:
                c["wires"] = [[mapping[t] for t in port if t in mapping] for port in c["wires"]]
            if c.get("links"):
                c["links"] = [mapping[l] for l in c["links"] if l in mapping]
            if c.get("type") == "group" and c.get("nodes"):
                c["nodes"] = [mapping[x] for x in c["nodes"] if x in mapping]
            for k, v in list(c.items()):
                if k not in ("id", "z", "g") and isinstance(v, str) and v in mapping:
                    c[k] = mapping[v]
            self.nodes.append(c)
            self.touched.add(c["id"])
        self._log("import_pattern", nodes=nodes, z=z)
        return mapping
