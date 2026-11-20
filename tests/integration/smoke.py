"""Run after make up: python tests/integration/smoke.py [--agent]."""

import argparse
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--agent", action="store_true")
opts = parser.parse_args()
out = Path("artifacts")
out.mkdir(exist_ok=True)
# Read only the controller credential, never model credentials.
key = (
    os.getenv("DEMO_API_KEY")
    or json.loads(Path(".loop-sandbox/credentials.json").read_text())["token"]
)
base = os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8080")


def call(method, route, body=None, raw=False):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        base + route,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + (key or ""), "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            content = response.read()
            return content if raw else json.loads(content)
    except urllib.error.HTTPError as error:
        raise RuntimeError(str(error.code) + ": " + error.read().decode()) from error


print("health:", call("GET", "/health"))
sids = []
try:
    sid = call("POST", "/sandboxes", {})["sandbox_id"]
    sids.append(sid)
    root = "/sandboxes/" + sid
    call("POST", root + "/files", {"path": "sales.csv", "content": "item,amount\nA,10\nB,20\n"})
    script = "import csv, json\nfrom pathlib import Path\nrows=list(csv.DictReader(open('sales.csv')))\nPath('result.json').write_text(json.dumps({'total':sum(int(r['amount']) for r in rows)}))\n"
    call("POST", root + "/files", {"path": "main.py", "content": script})
    result = call("POST", root + "/commands", {"command": "python main.py"})
    assert result["exit_code"] == 0 and not result["timed_out"], result
    content = call("GET", root + "/files?path=result.json")["content"]
    assert json.loads(content)["total"] == 30
    (out / "result.json").write_bytes(call("GET", root + "/download?path=result.json", raw=True))
    call(
        "POST",
        root + "/browser",
        {
            "action": "set_content",
            "text": """<title>Demo</title><input id="q"><button onclick="document.querySelector('h1').textContent=document.querySelector('#q').value">Go</button><h1>Ready</h1>""",
        },
    )
    call("POST", root + "/browser", {"action": "fill", "selector": "#q", "text": "Sandbox works"})
    page = call("POST", root + "/browser", {"action": "click", "selector": "button"})
    assert "Sandbox works" in page["text"], page
    screenshot = call("POST", root + "/browser", {"action": "screenshot"})
    data = base64.b64decode(screenshot["base64"])
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    (out / "browser.png").write_bytes(data)
    sid2 = call("POST", "/sandboxes", {})["sandbox_id"]
    sids.append(sid2)
    isolated = call(
        "POST", "/sandboxes/" + sid2 + "/commands", {"command": "test ! -e /workspace/result.json"}
    )
    assert isolated["exit_code"] == 0, isolated
    timeout = call("POST", root + "/commands", {"command": "sleep 3", "timeout": 1})
    assert timeout["timed_out"], timeout
    print("PASS: files, execution, download, browser, screenshot, separate workspaces, timeout")
    if opts.agent:
        agent = call(
            "POST",
            root + "/agent",
            {
                "prompt": "Read sales.csv using tools. Calculate the sum with Python. Write agent-result.json containing {total: the numeric sum}, then verify it by reading it. Report the result.",
                "max_steps": 10,
            },
        )
        verified = json.loads(call("GET", root + "/files?path=agent-result.json")["content"])
        assert verified["total"] == 30, verified
        used = {entry["tool"] for entry in agent["trace"]}
        assert {"read_file", "run_command"} <= used, agent["trace"]
        (out / "agent-trace.json").write_text(
            json.dumps(agent, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("PASS: real model tool calling and verified artifact")
finally:
    cleanup_errors = []
    for sid in sids:
        try:
            print("cleanup:", sid, call("DELETE", "/sandboxes/" + sid))
        except Exception as error:
            cleanup_errors.append(str(error))
    if cleanup_errors:
        raise RuntimeError("Cleanup failed: " + "; ".join(cleanup_errors))
