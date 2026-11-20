"""Exercise live capacity, network isolation, expiry and restart cleanup."""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

key = (
    os.getenv("DEMO_API_KEY")
    or json.loads(Path(".loop-sandbox/credentials.json").read_text())["token"]
)
base = os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8080")


def call(method, route, body=None):
    req = urllib.request.Request(
        base + route,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


sids = []
try:
    for _ in range(4):
        sids.append(call("POST", "/sandboxes", {"ttl_seconds": 60})["sandbox_id"])
    try:
        call("POST", "/sandboxes", {})
        raise AssertionError("Capacity was not enforced")
    except urllib.error.HTTPError as error:
        assert error.code == 429
    sid = sids[0]
    inspection = json.loads(docker("inspect", "loop-sandbox-" + sid))[0]
    assert inspection["HostConfig"]["ReadonlyRootfs"]
    assert inspection["HostConfig"]["Memory"] == 1024**3
    assert not inspection["HostConfig"]["PortBindings"]
    assert not any(m["Destination"] == "/var/run/docker.sock" for m in inspection["Mounts"])
    network = json.loads(docker("network", "inspect", "loop-sandbox-" + sid))[0]
    assert network["Internal"] is True
    assert len(network["Containers"]) == 2
    result = call(
        "POST", "/sandboxes/" + sid + "/commands", {"command": 'id -u; test -z "$LLM_API_KEY"'}
    )
    assert result["exit_code"] == 0 and result["output"].strip() != "0"
    # Wait for the minimum supported real lease to expire.
    deadline = time.monotonic() + 85
    while call("GET", "/sandboxes") and time.monotonic() < deadline:
        time.sleep(2)
    assert call("GET", "/sandboxes") == []
    while (
        docker("ps", "-aq", "--filter", "label=loop-sandbox.owner=local")
        and time.monotonic() < deadline
    ):
        time.sleep(1)
    assert not docker("ps", "-aq", "--filter", "label=loop-sandbox.owner=local")
    assert not docker("network", "ls", "-q", "--filter", "label=loop-sandbox.owner=local")
    sids.clear()
    sid = call("POST", "/sandboxes", {})["sandbox_id"]
    sids.append(sid)
    docker("kill", "loop-sandbox-api")
    docker("start", "loop-sandbox-api")
    # Start after a hard kill and verify startup sweeps old allocations.
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            if call("GET", "/health")["docker"]:
                break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    assert call("GET", "/sandboxes") == []
    assert not docker("ps", "-aq", "--filter", "label=loop-sandbox.owner=local")
    assert not docker("network", "ls", "-q", "--filter", "label=loop-sandbox.owner=local")
    sids.clear()
    print("PASS: capacity, container limits, private network, TTL, crash recovery")
finally:
    for sid in sids:
        try:
            call("DELETE", "/sandboxes/" + sid)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
