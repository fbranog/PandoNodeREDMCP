import copy

from nodered_flow_mcp.domain.validation import validate


def rules(r):
    return {i["rule"] for i in r["issues"] if i["severity"] == "error"}


def test_valid_baseline(reg, base_flows):
    assert validate(base_flows, reg)["ok"]


def test_dangling_wire_and_port(reg, base_flows):
    f = copy.deepcopy(base_flows)
    f[3]["wires"] = [["zzz"], [], ["d"]]
    assert {"wire.dangling", "wire.port_out_of_range"} <= rules(validate(f, reg))


def test_config_ref_checks(reg, base_flows):
    f = copy.deepcopy(base_flows)
    f[3]["apiConfig"] = "a"  # wrong type
    assert "config.type_mismatch" in rules(validate(f, reg))
    f[3]["apiConfig"] = ""
    assert "config.required" in rules(validate(f, reg))
    f[3]["apiConfig"] = "gone"
    assert "config.dangling" in rules(validate(f, reg))


def test_duplicate_and_bad_z(reg, base_flows):
    f = copy.deepcopy(base_flows) + [{"id": "a", "type": "debug", "z": "nope", "x": 1, "y": 1, "wires": []}]
    assert {"id.duplicate", "z.invalid"} <= rules(validate(f, reg))


def test_preservation(reg, base_flows):
    f = copy.deepcopy(base_flows)
    f[4]["name"] = "changed"
    assert "preserve.modified" in rules(validate(f, reg, base=base_flows, touched=[]))
    assert validate(f, reg, base=base_flows, touched=["d"])["ok"]


def test_http_needs_response(reg):
    f = [{"id": "t", "type": "tab"}, {"id": "h", "type": "http in", "z": "t", "x": 1, "y": 1, "wires": [["d"]]},
         {"id": "d", "type": "debug", "z": "t", "x": 2, "y": 2, "wires": []}]
    r = validate(f, reg)
    assert any(i["rule"] == "http.no_response" for i in r["issues"])
    f.append({"id": "r", "type": "http response", "z": "t", "x": 3, "y": 3, "wires": []})
    f[1]["wires"] = [["d", "r"]]
    assert not any(i["rule"] == "http.no_response" for i in validate(f, reg)["issues"])
