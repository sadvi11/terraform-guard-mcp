import json, os, subprocess, sys, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:8000"

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read())

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

def wait_until(fn, what, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            v = fn()
            if v: return v
        except Exception: pass
        time.sleep(0.2)
    raise SystemExit(f"FAIL: timed out waiting for {what}")

fails = []
def check(cond, label):
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond: fails.append(label)

relay = subprocess.Popen([sys.executable, "relay/server.py"], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    wait_until(lambda: get("/requests/pending") == [], "relay to come up")
    print("\n--- relay up ---")

    # tablet page is served by the relay itself
    with urllib.request.urlopen(BASE + "/", timeout=5) as r:
        html = r.read().decode()
    check(r.status == 200 and "Blast Radius" in html, "relay serves the tablet page at /")

    for decision, expect_in_output, label in (("block", "BLOCKED", "NO"), ("approve", "APPLIED", "YES")):
        print(f"\n--- run where the human taps {label} ---")
        agent = subprocess.Popen([sys.executable, "demo/run_demo.py"], cwd=ROOT,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        pending = wait_until(lambda: get("/requests/pending") or None, "the agent to ask")
        req = pending[0]
        check(req["verdict"] == "BLOCK", f"verdict is BLOCK (got {req['verdict']})")
        fatal = [r["name"] for r in req["resources"] if r["fatal"]]
        check(fatal == ["aws_db_instance.prod-db"], f"prod-db flagged fatal, nothing else (got {fatal})")
        check(agent.poll() is None, "agent is still frozen, waiting for a human")

        post(f"/requests/{req['id']}/decision", {"decision": decision})
        out, _ = agent.communicate(timeout=15)
        check(expect_in_output in out, f"agent printed {expect_in_output}")
        check(get("/requests/pending") == [], "nothing left pending afterwards")

    print("\n--- verdict function ---")
    check(post("/requests", {"tool": "t", "summary": "s",
          "resources": [{"name": "aws_instance.worker", "action": "create"}]})["verdict"] == "SAFE",
          "creates only -> SAFE")
    check(post("/requests", {"tool": "t", "summary": "s",
          "resources": [{"name": "aws_instance.worker", "action": "delete"}]})["verdict"] == "REVIEW",
          "deletes a server that comes back -> REVIEW")
    check(post("/requests", {"tool": "t", "summary": "s",
          "resources": [{"name": "aws_cloudtrail.audit", "action": "delete"}]})["verdict"] == "BLOCK",
          "deletes the audit trail -> BLOCK")
    check(post("/requests", {"tool": "t", "summary": "s",
          "resources": [{"name": "aws_security_group.web", "action": "update", "opens_to_world": True}]})["verdict"] == "BLOCK",
          "opens SSH to the world on an update -> BLOCK")

    print("\n--- fails closed ---")
    check(post("/requests", {"tool": "t", "summary": "s", "resources": []})["verdict"] == "SAFE",
          "empty change -> SAFE")
    try:
        post("/requests/req_999/decision", {"decision": "block"}); check(False, "unknown id rejected")
    except urllib.error.HTTPError as e:
        check(e.code == 404, "unknown request id -> 404")
    try:
        post("/requests/req_1/decision", {"decision": "maybe"}); check(False, "bad decision rejected")
    except urllib.error.HTTPError as e:
        check(e.code == 400, "decision must be approve or block -> 400")
finally:
    relay.terminate()

print("\n" + ("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
