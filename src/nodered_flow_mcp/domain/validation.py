from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable

from ..registry.node_registry import NodeRegistry
from .graph import Graph, is_config, is_container, iter_wire_targets

RESPONSE_TYPES = {"http response", "sse-response"}
HTTP_ENTRY_TYPES = {"http in", "http-receive"}
CTX_CALL = re.compile(r"\b(flow|global|context)\.(get|set)\(\s*['\"]([^'\"]+)['\"]")


@dataclass
class Issue:
    severity: str  # error | warning | info
    rule: str
    message: str
    node_id: str | None = None

    def to_dict(self):
        return asdict(self)


def _reachable(g: Graph, start: dict) -> set[str]:
    seen, stack = set(), [start["id"]]
    link_in_by_id = g.by_id
    while stack:
        i = stack.pop()
        if i in seen or i not in g.by_id:
            continue
        seen.add(i)
        n = g.by_id[i]
        for _, t in iter_wire_targets(n):
            stack.append(t)
        if n.get("type") == "link out" and n.get("mode", "link") != "return":
            stack.extend(n.get("links") or [])
        if n.get("type") == "link call":
            stack.extend(n.get("links") or [])
    return seen


def validate(nodes: list[dict], registry: NodeRegistry | None = None, base: list[dict] | None = None, touched: Iterable[str] | None = None) -> dict:
    reg = registry or NodeRegistry()
    g = Graph(nodes)
    issues: list[Issue] = []
    add = lambda sev, rule, msg, nid=None: issues.append(Issue(sev, rule, msg, nid))

    for n in nodes:
        if not n.get("id"):
            add("error", "id.missing", f"node of type {n.get('type')} has no id")
        if not n.get("type"):
            add("error", "type.missing", "node has no type", n.get("id"))
    for d in g.duplicate_ids:
        add("error", "id.duplicate", f"duplicate id {d}", d)

    for n in nodes:
        nid, t = n.get("id"), n.get("type")
        if is_container(n):
            continue
        # container membership
        z = n.get("z")
        if z:
            if z not in g.by_id or not is_container(g.by_id[z]):
                add("error", "z.invalid", f"z={z} is not an existing tab/subflow", nid)
        elif not is_config(n):
            add("error", "z.missing", "canvas node has no z (tab/subflow)", nid)
        gid = n.get("g")
        if gid and (gid not in g.by_id or g.by_id[gid].get("type") != "group"):
            add("error", "group.invalid", f"g={gid} is not an existing group", nid)

        # wires
        wires = n.get("wires")
        if wires is not None and not isinstance(wires, list):
            add("error", "wires.shape", "wires must be a list of lists", nid)
            wires = []
        outs = reg.output_count(n)
        for port, tgt in iter_wire_targets(n):
            if tgt not in g.by_id:
                add("error", "wire.dangling", f"port {port} wires to missing node {tgt}", nid)
            else:
                tn = g.by_id[tgt]
                if tn.get("z") != n.get("z") and not is_config(tn):
                    add("error", "wire.cross_container", f"wire to {tgt} crosses tabs", nid)
                if is_container(tn) or is_config(tn):
                    add("error", "wire.bad_target", f"wire to non-canvas node {tgt}", nid)
        if outs is not None and wires is not None:
            extra = [p for p, ts in enumerate(wires) if p >= outs and ts]
            if extra:
                add("error", "wire.port_out_of_range", f"wires on port(s) {extra} but node has {outs} output(s)", nid)
            if t and outs and len(wires) != outs and t not in ("link out",):
                add("warning", "wire.port_count", f"len(wires)={len(wires)} but outputs={outs}", nid)

        # links
        if t in ("link in", "link out", "link call"):
            for l in n.get("links") or []:
                if l not in g.by_id:
                    add("error", "link.dangling", f"link target {l} missing", nid)

        # subflow instance
        if t and t.startswith("subflow:"):
            if t.split(":", 1)[1] not in g.by_id:
                add("error", "subflow.missing", f"instance of unknown subflow {t}", nid)

        # config refs from schema + overlays
        sch = reg.schemas.get(t)
        ref_types: dict[str, tuple[str, bool]] = {}
        if sch:
            for p in sch.properties.values():
                if p.config_type:
                    ref_types[p.name] = (p.config_type, p.required)
        for prop, ctype in (reg.overlays.get(t, {}).get("config_refs") or {}).items():
            ref_types.setdefault(prop, (ctype, False))
        for prop, (ctype, required) in ref_types.items():
            v = n.get(prop)
            if not v:
                if required:
                    add("error", "config.required", f"required config ref '{prop}' ({ctype}) is empty", nid)
                continue
            if isinstance(v, str):
                target = g.by_id.get(v)
                if target is None:
                    add("error", "config.dangling", f"'{prop}' references missing node {v}", nid)
                elif target.get("type") != ctype:
                    add("error", "config.type_mismatch", f"'{prop}' expects {ctype}, found {target.get('type')}", nid)

        # required props
        if sch:
            for p in sch.properties.values():
                if p.required and not p.config_type and n.get(p.name) in (None, ""):
                    add("warning", "prop.required_empty", f"required property '{p.name}' is empty", nid)

    # HTTP entry must reach a response
    for n in nodes:
        if n.get("type") in HTTP_ENTRY_TYPES and n.get("z"):
            reach = _reachable(g, n)
            if not any(g.by_id[i].get("type") in RESPONSE_TYPES for i in reach if i in g.by_id):
                # a link/subflow may hide it; warning only
                add("warning", "http.no_response", "no http/sse response reachable from this entry node", n["id"])

    # context key usage (info)
    reads: dict[tuple[str, str], list[str]] = {}
    writes: dict[tuple[str, str], list[str]] = {}
    for n in nodes:
        if n.get("type") == "function":
            code = "\n".join(str(n.get(k, "")) for k in ("func", "initialize", "finalize"))
            for scope, op, key in CTX_CALL.findall(code):
                (reads if op == "get" else writes).setdefault((scope, key), []).append(n["id"])
    for k, ids in reads.items():
        if k[0] != "context" and k not in writes:
            add("info", "context.read_never_written", f"{k[0]} context key '{k[1]}' is read but no function writes it in this config", ids[0])

    # preservation of unrelated nodes
    if base is not None:
        tset = set(touched or [])
        bm = {n["id"]: n for n in base}
        for i, bn in bm.items():
            cur = g.by_id.get(i)
            if cur is None:
                if i not in tset:
                    add("error", "preserve.removed", f"node {i} ({bn.get('type')}) removed without an explicit edit", i)
            elif cur != bn and i not in tset:
                add("error", "preserve.modified", f"node {i} ({bn.get('type')}) changed without an explicit edit", i)

    errors = [i for i in issues if i.severity == "error"]
    return {
        "ok": not errors,
        "counts": {s: sum(1 for i in issues if i.severity == s) for s in ("error", "warning", "info")},
        "issues": [i.to_dict() for i in issues],
    }
