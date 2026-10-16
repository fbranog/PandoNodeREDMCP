import pytest

from nodered_flow_mcp.registry.node_registry import NodeRegistry

EDITOR_HTML = """
<script type="text/javascript">
RED.nodes.registerType('demo-call', {
    category: 'network',
    color: '#fff',
    defaults: {
        name: {value: ""},
        apiConfig: {value: "", type: "demo-config", required: true},
        topic: {value: "/x, y", required: true, validate: function(v){ return v.length > 0; }},
        outputs: {value: 2}
    },
    credentials: { token: {type: "password"} },
    inputs: 1,
    outputs: 2,
    label: function() { return this.name || "demo"; }
});
</script>
<script>RED.nodes.registerType('demo-config', {category:'config', defaults:{baseUrl:{value:"",required:true}}});</script>
"""


@pytest.fixture
def reg():
    r = NodeRegistry()
    r.load_schemas_from_html(EDITOR_HTML, "demo")
    r.load_schemas_from_html(
        "RED.nodes.registerType('debug',{category:'common',defaults:{name:{value:''}},inputs:1,outputs:0});"
        "RED.nodes.registerType('inject',{category:'common',defaults:{name:{value:''}},inputs:0,outputs:1});"
        "RED.nodes.registerType('http in',{category:'network',defaults:{},inputs:0,outputs:1});"
        "RED.nodes.registerType('http response',{category:'network',defaults:{},inputs:1,outputs:0});",
        "node-red")
    return r


@pytest.fixture
def base_flows():
    return [
        {"id": "t1", "type": "tab", "label": "Flow"},
        {"id": "c1", "type": "demo-config", "baseUrl": "http://x"},
        {"id": "a", "type": "inject", "z": "t1", "x": 100, "y": 100, "wires": [["b"]]},
        {"id": "b", "type": "demo-call", "z": "t1", "x": 300, "y": 100, "apiConfig": "c1", "topic": "/x", "outputs": 2,
         "wires": [["d"], []]},
        {"id": "d", "type": "debug", "z": "t1", "x": 500, "y": 100, "wires": []},
    ]
