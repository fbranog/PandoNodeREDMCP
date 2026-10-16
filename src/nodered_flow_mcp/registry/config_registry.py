from __future__ import annotations

from .node_registry import NodeRegistry


def config_types(reg: NodeRegistry) -> dict[str, list[dict]]:
    """config_type -> [{node_type, property, required}] using schema-declared refs."""
    out: dict[str, list[dict]] = {}
    for s in reg.schemas.values():
        for p in s.properties.values():
            if p.config_type:
                out.setdefault(p.config_type, []).append(
                    {"node_type": s.type, "property": p.name, "required": p.required}
                )
    return out
