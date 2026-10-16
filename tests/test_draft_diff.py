import pytest

from nodered_flow_mcp.domain.diff import diff_flows
from nodered_flow_mcp.domain.draft import Draft, DraftError
from nodered_flow_mcp.domain.validation import validate


def make(base_flows):
    return Draft.create("rev1", base_flows)


def test_add_connect_diff_validate(reg, base_flows):
    d = make(base_flows)
    n = d.add_node("debug", "t1", {"name": "new"}, reg)
    d.connect("a", n["id"])
    diff = diff_flows(d.base, d.nodes)
    assert [x["id"] for x in diff["added"]] == [n["id"]]
    assert [x["id"] for x in diff["modified"]] == ["a"]
    assert validate(d.nodes, reg, d.base, d.touched)["ok"]
    assert d.base == base_flows  # base is untouched


def test_unknown_type_rejected(reg, base_flows):
    with pytest.raises(DraftError):
        make(base_flows).add_node("not-installed", "t1", {}, reg)


def test_delete_cleans_wires(reg, base_flows):
    d = make(base_flows)
    d.delete_node("b")
    assert d._get("a")["wires"] == [[]]
    assert validate(d.nodes, reg, d.base, d.touched)["ok"]


def test_replay_rebase(reg, base_flows):
    d = make(base_flows)
    n = d.add_node("debug", "t1", {}, reg)
    d.connect("a", n["id"])
    d2 = Draft("x", "rev2", base_flows)
    d2.replay(d.ops, reg)
    assert d2.nodes == d.nodes


def test_import_remaps(reg, base_flows):
    d = make(base_flows)
    d.add_node("tab", None, {"label": "T2"})
    t2 = d.nodes[-1]["id"]
    m = d.import_nodes([n for n in base_flows if n.get("z") == "t1"], t2, reg)
    assert set(m) == {"a", "b", "d"}
    new_a = d._get(m["a"])
    assert new_a["wires"] == [[m["b"]]] and new_a["z"] == t2


def test_persist(tmp_path, base_flows):
    d = make(base_flows)
    d.save(tmp_path)
    assert Draft.load(tmp_path, d.id).nodes == d.nodes
    with pytest.raises(DraftError):
        Draft.load(tmp_path, "../x")
