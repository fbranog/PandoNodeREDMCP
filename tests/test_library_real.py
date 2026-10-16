"""Run the validator and library over the real exported example flows."""
from pathlib import Path

import pytest

from nodered_flow_mcp.domain.validation import validate
from nodered_flow_mcp.library.loader import Library
from nodered_flow_mcp.registry.node_registry import NodeRegistry

ROOT = Path(__file__).parent.parent / "reference" / "projects"
pytestmark = pytest.mark.skipif(not ROOT.exists(), reason="no reference projects")


def test_library_indexes_and_skips_credentials():
    lib = Library(ROOT)
    assert lib.files and all("_cred" not in k and "backup" not in k for k in lib.files)
    assert any("sse-response" in e.node_types for e in lib.examples)
    hits = lib.search(node_types=["sse-response"])
    assert hits and hits[0]["provenance"] == "observed"


def test_real_flows_have_no_structural_errors():
    lib = Library(ROOT)
    reg = NodeRegistry()  # overlays only; core-type fixed outputs apply
    bad = {}
    for key, (_, nodes) in lib.files.items():
        errs = [i for i in validate(nodes, reg)["issues"] if i["severity"] == "error"]
        if errs:
            bad[key] = errs[:5]
    assert not bad, bad


def test_tab_nodes_extract():
    lib = Library(ROOT)
    e = next(e for e in lib.examples if "sse-response" in e.node_types)
    nodes = lib.tab_nodes(e.file, e.tab_id)
    assert nodes[0]["type"] == "tab" and any(n["type"] == "api-config" for n in nodes)
