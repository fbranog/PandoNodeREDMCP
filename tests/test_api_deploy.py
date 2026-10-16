import httpx
import pytest
import respx

from nodered_flow_mcp.api import flows as flows_api
from nodered_flow_mcp.api.client import NodeRedClient, RevisionConflict
from nodered_flow_mcp.domain import deploy as dep
from nodered_flow_mcp.domain.draft import Draft
from nodered_flow_mcp.settings import Settings

URL = "http://nr.test"


def client(**kw):
    return NodeRedClient(Settings(url=URL, read_only=kw.pop("read_only", False), _env_file=None, **kw))


@respx.mock
async def test_password_auth_and_v2_header():
    respx.get(f"{URL}/auth/login").mock(return_value=httpx.Response(200, json={"type": "credentials"}))
    tok = respx.post(f"{URL}/auth/token").mock(return_value=httpx.Response(200, json={"access_token": "T"}))
    fl = respx.get(f"{URL}/flows").mock(return_value=httpx.Response(200, json={"rev": "r1", "flows": []}))
    c = client(user="u", password="p")
    assert (await flows_api.get_flows(c))["rev"] == "r1"
    assert b"scope=read" not in tok.calls[0].request.content and b"scope=%2A" in tok.calls[0].request.content
    req = fl.calls[0].request
    assert req.headers["Authorization"] == "Bearer T" and req.headers["Node-RED-API-Version"] == "v2"


@respx.mock
async def test_no_auth():
    respx.get(f"{URL}/auth/login").mock(return_value=httpx.Response(200, json={}))
    fl = respx.get(f"{URL}/flows").mock(return_value=httpx.Response(200, json={"rev": "r", "flows": []}))
    await flows_api.get_flows(client())
    assert "Authorization" not in fl.calls[0].request.headers


@respx.mock
async def test_post_flows_sends_rev_and_type():
    respx.get(f"{URL}/auth/login").mock(return_value=httpx.Response(200, json={}))
    p = respx.post(f"{URL}/flows").mock(return_value=httpx.Response(200, json={"rev": "r2"}))
    assert await flows_api.post_flows(client(), [], "r1", "flows") == "r2"
    r = p.calls[0].request
    assert r.headers["Node-RED-Deployment-Type"] == "flows" and b'"rev":"r1"' in r.content.replace(b" ", b"")


@respx.mock
async def test_conflict_maps_to_exception():
    respx.get(f"{URL}/auth/login").mock(return_value=httpx.Response(200, json={}))
    respx.post(f"{URL}/flows").mock(return_value=httpx.Response(409, json={"message": "version_mismatch"}))
    with pytest.raises(RevisionConflict):
        await flows_api.post_flows(client(), [], "old")


def _draft(base_flows, reg):
    d = Draft.create("r1", base_flows)
    n = d.add_node("debug", "t1", {}, reg)
    d.connect("a", n["id"])
    return d


@respx.mock
async def test_deploy_flow(reg, base_flows):
    respx.get(f"{URL}/auth/login").mock(return_value=httpx.Response(200, json={}))
    d = _draft(base_flows, reg)
    state = {"flows": base_flows, "rev": "r1"}

    def get(_):
        return httpx.Response(200, json=state)

    def post(req):
        import json
        body = json.loads(req.content)
        assert body["rev"] == "r1"
        state.update(flows=body["flows"], rev="r2")
        return httpx.Response(200, json={"rev": "r2"})

    respx.get(f"{URL}/flows").mock(side_effect=get)
    respx.post(f"{URL}/flows").mock(side_effect=post)
    c = client()
    tok = dep.review(d, reg)["approval_token"]
    with pytest.raises(PermissionError):
        await dep.deploy(c, d, reg, "bad")
    res = await dep.deploy(c, d, reg, tok)
    assert res["deployed"] and res["verified"] and res["new_rev"] == "r2"


@respx.mock
async def test_deploy_blocked_when_read_only_or_conflict(reg, base_flows):
    respx.get(f"{URL}/auth/login").mock(return_value=httpx.Response(200, json={}))
    d = _draft(base_flows, reg)
    tok = dep.review(d, reg)["approval_token"]
    with pytest.raises(PermissionError):
        await dep.deploy(client(read_only=True), d, reg, tok)
    respx.get(f"{URL}/flows").mock(return_value=httpx.Response(200, json={"rev": "other", "flows": base_flows}))
    res = await dep.deploy(client(), d, reg, tok)
    assert res["deployed"] is False and res["conflict"]


def test_token_changes_with_draft(reg, base_flows):
    d = _draft(base_flows, reg)
    t1 = dep.approval_token(d, "nodes")
    d.add_node("debug", "t1", {}, reg)
    assert dep.approval_token(d, "nodes") != t1
    assert dep.review(d, reg)["approval_token"] != t1
