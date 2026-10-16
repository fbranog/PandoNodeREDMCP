from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from ..api import nodes as nodes_api
from ..api.client import NodeRedClient

OVERLAY_DIR = Path(__file__).parent / "overlays"

# Output counts for common core nodes with fixed ports (verified: Node-RED core).
CORE_FIXED_OUTPUTS = {
    "inject": 1, "debug": 0, "http in": 1, "http response": 0, "http request": 1,
    "catch": 1, "status": 1, "complete": 1, "link in": 1, "link out": 0, "link call": 1,
    "comment": 0, "change": 1, "template": 1, "delay": 1, "json": 1, "split": 1, "join": 1,
    "junction": 1,
}
# Property names that are node-ref arrays/strings for these core types, not config refs
NON_CONFIG_STRING_PROPS = {"name", "info", "func", "topic", "payload", "url", "method", "label"}

_REGISTER = re.compile(r"RED\.nodes\.registerType\(\s*['\"]([^'\"]+)['\"]")


@dataclass
class PropSchema:
    name: str
    required: bool = False
    config_type: str | None = None  # set when property references a config node
    default: Any = None
    has_validate: bool = False


@dataclass
class NodeSchema:
    type: str
    module: str | None = None
    category: str | None = None
    properties: dict[str, PropSchema] = field(default_factory=dict)
    credentials: list[str] = field(default_factory=list)
    inputs: int | None = None
    outputs: int | None = None
    parsed: bool = True
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _balanced(s: str, start: int, open_ch="{", close_ch="}") -> tuple[str, int]:
    depth, i, q = 0, start, None
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\":
                i += 1
            elif c == q:
                q = None
        elif c in "'\"`":
            q = c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return s[start : i + 1], i + 1
        i += 1
    return s[start:], len(s)


def _split_top(body: str) -> list[str]:
    """Split object body (without outer braces) on top-level commas."""
    parts, depth, q, cur = [], 0, None, []
    i = 0
    while i < len(body):
        c = body[i]
        if q:
            cur.append(c)
            if c == "\\":
                i += 1
                cur.append(body[i : i + 1])
            elif c == q:
                q = None
        elif c in "'\"`":
            q = c
            cur.append(c)
        elif c in "{[(":
            depth += 1
            cur.append(c)
        elif c in "}])":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _field_block(src: str, key: str) -> str | None:
    m = re.search(r"(?<![\w.])" + key + r"\s*:\s*\{", src)
    if not m:
        return None
    blk, _ = _balanced(src, m.end() - 1)
    return blk[1:-1]


def parse_register_blocks(html: str, module: str | None = None) -> dict[str, NodeSchema]:
    out: dict[str, NodeSchema] = {}
    for m in _REGISTER.finditer(html):
        t = m.group(1)
        brace = html.find("{", m.end())
        if brace < 0:
            continue
        body, _ = _balanced(html, brace)
        sch = NodeSchema(type=t, module=module)
        try:
            cat = re.search(r"category\s*:\s*['\"]([^'\"]+)['\"]", body)
            sch.category = cat.group(1) if cat else None
            ins = re.search(r"(?<![\w.])inputs\s*:\s*(\d+)", body)
            sch.inputs = int(ins.group(1)) if ins else None
            outs = re.search(r"(?<![\w.])outputs\s*:\s*(\d+)", body)
            sch.outputs = int(outs.group(1)) if outs else None
            dblk = _field_block(body, "defaults")
            if dblk is not None:
                for part in _split_top(dblk):
                    km = re.match(r"\s*['\"]?([\w$-]+)['\"]?\s*:\s*(.*)$", part, re.S)
                    if not km:
                        continue
                    name, val = km.group(1), km.group(2).strip()
                    ps = PropSchema(name=name)
                    if val.startswith("{"):
                        vm = re.search(r"(?<![\w.])value\s*:\s*(\"[^\"]*\"|'[^']*'|[\w.\[\]-]+)", val)
                        if vm:
                            ps.default = vm.group(1).strip("'\"")
                        ps.required = bool(re.search(r"required\s*:\s*true", val))
                        ps.has_validate = "validate" in val
                        tm = re.search(r"(?<![\w.])type\s*:\s*['\"]([^'\"]+)['\"]", val)
                        if tm:
                            ps.config_type = tm.group(1)
                    sch.properties[name] = ps
            cblk = _field_block(body, "credentials")
            if cblk is not None:
                sch.credentials = [
                    re.match(r"\s*['\"]?([\w$-]+)", p).group(1) for p in _split_top(cblk) if re.match(r"\s*['\"]?([\w$-]+)", p)
                ]
        except Exception as e:  # tolerant: report, never guess
            sch.parsed = False
            sch.notes = f"parse error: {e}"
        out[t] = sch
    return out


class NodeRegistry:
    def __init__(self):
        self.schemas: dict[str, NodeSchema] = {}
        self.sets: list[dict] = []
        self.overlays: dict[str, dict] = {}
        self.load_overlays()

    def load_overlays(self) -> None:
        self.overlays = {}
        for p in sorted(OVERLAY_DIR.glob("*.yaml")):
            data = yaml.safe_load(p.read_text()) or {}
            for t, v in (data.get("node_types") or {}).items():
                self.overlays[t] = v

    async def refresh(self, client: NodeRedClient) -> None:
        self.sets = await nodes_api.list_node_sets(client)
        self.schemas = {}
        for s in self.sets:
            if not s.get("enabled", True):
                continue
            module, name = s.get("module"), s.get("name")
            try:
                html = await nodes_api.get_set_html(client, module, name)
            except Exception:
                continue
            for t, sch in parse_register_blocks(html, module).items():
                self.schemas[t] = sch
            for t in s.get("types", []):
                self.schemas.setdefault(t, NodeSchema(type=t, module=module, parsed=False, notes="no registerType block found"))

    def load_schemas_from_html(self, html: str, module: str | None = None) -> None:
        self.schemas.update(parse_register_blocks(html, module))

    def is_core(self, t: str) -> bool:
        s = self.schemas.get(t)
        return bool(s and s.module == "node-red")

    def output_count(self, node: dict) -> int | None:
        if isinstance(node.get("outputs"), int):
            return node["outputs"]
        if isinstance(node.get("outputs"), str) and node["outputs"].isdigit():
            return int(node["outputs"])
        t = node.get("type")
        if t in CORE_FIXED_OUTPUTS:
            return CORE_FIXED_OUTPUTS[t]
        s = self.schemas.get(t)
        return s.outputs if s else None

    def usage(self, t: str) -> dict:
        return self.overlays.get(t) or {"provenance": "none", "note": "no curated overlay for this type"}

    def describe(self, t: str) -> dict | None:
        s = self.schemas.get(t)
        ov = self.overlays.get(t)
        if not s and not ov:
            return None
        return {"schema": s.to_dict() if s else None, "knowledge": ov}
