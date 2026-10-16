from __future__ import annotations

import hashlib
import json
from typing import Any

POSITION_KEYS = {"x", "y"}


def canonical_hash(flows: list[dict]) -> str:
    s = json.dumps(sorted(flows, key=lambda n: str(n.get("id"))), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode()).hexdigest()


def _prop_diff(a: dict, b: dict) -> dict[str, Any]:
    out = {}
    for k in sorted(set(a) | set(b)):
        if a.get(k, _M) != b.get(k, _M):
            out[k] = {"before": a.get(k), "after": b.get(k)}
    return out


_M = object()


def diff_flows(base: list[dict], new: list[dict]) -> dict:
    bm = {n["id"]: n for n in base}
    nm = {n["id"]: n for n in new}
    added = [i for i in nm if i not in bm]
    removed = [i for i in bm if i not in nm]
    modified, moved_only = {}, []
    for i in nm:
        if i in bm and bm[i] != nm[i]:
            d = _prop_diff(bm[i], nm[i])
            if set(d) <= POSITION_KEYS:
                moved_only.append(i)
            else:
                modified[i] = d
    affected = set()
    for i in added + list(modified) + removed:
        n = nm.get(i) or bm.get(i)
        affected.add(n.get("z") or (n["id"] if n.get("type") in ("tab", "subflow") else "global"))
    return {
        "added": [{"id": i, "type": nm[i].get("type"), "name": nm[i].get("name", ""), "z": nm[i].get("z")} for i in added],
        "removed": [{"id": i, "type": bm[i].get("type"), "name": bm[i].get("name", ""), "z": bm[i].get("z")} for i in removed],
        "modified": [{"id": i, "type": nm[i].get("type"), "changes": d} for i, d in modified.items()],
        "moved_only": moved_only,
        "affected_containers": sorted(a for a in affected if a),
        "unchanged_count": sum(1 for i in nm if i in bm and bm[i] == nm[i]),
    }
