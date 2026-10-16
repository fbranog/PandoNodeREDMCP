def test_parse_schema(reg):
    s = reg.schemas["demo-call"]
    assert s.category == "network"
    assert s.outputs == 2 and s.inputs == 1
    assert s.properties["apiConfig"].config_type == "demo-config"
    assert s.properties["apiConfig"].required
    assert s.properties["topic"].required and s.properties["topic"].has_validate
    assert s.credentials == ["token"]
    assert "baseUrl" in reg.schemas["demo-config"].properties


def test_overlays_load(reg):
    assert reg.usage("sse-response")["provenance"] == "observed"
    assert reg.usage("nope")["provenance"] == "none"
