from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..domain.graph import Graph, is_config

SKIP_PARTS = ("_cred", "package.json", ".backup", "flows_cred", "node_modules")


@dataclass
class Example:
    project: str
    file: str
    tab_id: str
    label: str
    node_count: int
    node_types: dict[str, int] = field(default_factory=dict)
    config_ids: list[str] = field(default_factory=list)


def _is_flow_file(p: Path) -> bool:
    n = p.name
    return p.suffix == ".json" and not any(s in n for s in SKIP_PARTS) and ".git" not in p.parts


def _load_flow_file(p: Path):
    try:
        d = json.loads(p.read_text())
    except Exception:
        return None
    return d if isinstance(d, list) and all(isinstance(x, dict) for x in d) else None


class Library:
    def __init__(self, examples_dir: Path | None, patterns_dir: Path | None = None):
        self.examples_dir = examples_dir
        self.patterns_dir = patterns_dir or Path(__file__).parent.parent / "patterns"
        self.files: dict[str, tuple[Path, list[dict]]] = {}
        self.examples: list[Example] = []
        self.load()

    def load(self) -> None:
        self.files, self.examples = {}, []
        if not self.examples_dir or not self.examples_dir.exists():
            return
        for p in sorted(self.examples_dir.rglob("*.json")):
            if not _is_flow_file(p):
                continue
            nodes = _load_flow_file(p)
            if nodes is None:
                continue
            project = p.relative_to(self.examples_dir).parts[0] if len(p.relative_to(self.examples_dir).parts) > 1 else p.stem
            key = f"{project}/{p.name}"
            self.files[key] = (p, nodes)
            g = Graph(nodes)
            for tab in g.tabs:
                members = g.nodes_in(tab["id"])
                types: dict[str, int] = {}
                for m in members:
                    types[m["type"]] = types.get(m["type"], 0) + 1
                self.examples.append(Example(project, key, tab["id"], tab.get("label", ""), len(members), types))

    def tab_nodes(self, file_key: str, tab_id: str, include_configs: bool = True) -> list[dict]:
        _, nodes = self.files[file_key]
        g = Graph(nodes)
        tab = g.by_id[tab_id]
        members = g.nodes_in(tab_id)
        out = [tab] + members
        if include_configs:
            ids = {m["id"] for m in members}
            for c in g.configs:
                if any(c["id"] in g.references(m).values() for m in members):
                    out.append(c)
        return out

    def search(self, node_types: list[str] | None = None, query: str | None = None, limit: int = 10) -> list[dict]:
        scored = []
        q = (query or "").lower()
        for e in self.examples:
            score = 0
            if node_types:
                score += sum(1 for t in node_types if t in e.node_types) * 10
                if not any(t in e.node_types for t in node_types):
                    continue
            if q:
                if q in e.label.lower():
                    score += 8
                _, nodes = self.files[e.file]
                blob = " ".join(
                    str(n.get("name", "")) + " " + str(n.get("func", ""))[:2000]
                    for n in nodes if n.get("z") == e.tab_id
                ).lower()
                hits = sum(blob.count(w) for w in q.split() if w)
                if hits == 0 and not node_types and q not in e.label.lower():
                    continue
                score += min(hits, 20)
            scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        return [
            {"example_ref": f"{e.file}#{e.tab_id}", "project": e.project, "label": e.label, "node_count": e.node_count,
             "top_node_types": dict(sorted(e.node_types.items(), key=lambda kv: -kv[1])[:8]), "score": s,
             "provenance": "observed"}
            for s, e in scored[:limit]
        ]

    def patterns(self) -> dict[str, dict]:
        out = {}
        if not self.patterns_dir.exists():
            return out
        for d in sorted(p for p in self.patterns_dir.iterdir() if p.is_dir()):
            meta = d / "metadata.yaml"
            if not meta.exists():
                continue
            m = yaml.safe_load(meta.read_text()) or {}
            m["name"] = m.get("name", d.name)
            m["_dir"] = str(d)
            out[d.name] = m
        return out

    def pattern_files(self, name: str) -> dict:
        d = self.patterns_dir / name
        if not d.is_dir() or "/" in name or ".." in name:
            raise KeyError(name)
        res = {}
        for fn in ("metadata.yaml", "design_constraints.md", "validation_rules.yaml", "known_limitations.md"):
            if (d / fn).exists():
                res[fn] = (d / fn).read_text()
        if (d / "flow.json").exists():
            res["flow.json"] = json.loads((d / "flow.json").read_text())
        return res
