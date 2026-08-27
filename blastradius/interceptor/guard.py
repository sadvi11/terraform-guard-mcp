"""The part that makes the agent stop and wait.

This is Person 1's file. One function does the whole trick:

    require_approval(...)  ->  True if the human tapped YES
                               False if the human tapped NO

It sends the proposed change to the relay and then blocks - the agent
gets no answer, and therefore cannot act, until a human has tapped
something on the tablet.

Wire it into whatever the agent calls. For an MCP tool that is one line
at the top of the tool body:

    if not require_approval("terraform_apply", summary, resources):
        return "BLOCKED by human review"
"""

import json
import time
import urllib.error
import urllib.request

RELAY = "http://127.0.0.1:8000"

# How long the agent will hang before giving up. On stage nobody takes
# five minutes, but an agent that hangs forever is worse than one that
# fails closed.
TIMEOUT_SECONDS = 300
POLL_SECONDS = 0.5


class ApprovalTimeout(Exception):
    """Nobody tapped anything in time. Treat this as a NO."""


def _post(path: str, payload: dict) -> dict:
    raw = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{RELAY}{path}",
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{RELAY}{path}", timeout=10) as response:
        return json.loads(response.read())


def submit(tool: str, summary: str, resources: list[dict]) -> dict:
    """File the proposed change and get back the record, including the verdict."""
    return _post("/requests", {"tool": tool, "summary": summary, "resources": resources})


def wait_for_decision(request_id: str, timeout: float = TIMEOUT_SECONDS) -> str:
    """Block until a human taps. Returns 'approved' or 'blocked'."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = _get(f"/requests/{request_id}")
        if record["status"] != "pending":
            return record["status"]
        time.sleep(POLL_SECONDS)
    raise ApprovalTimeout(request_id)


def require_approval(tool: str, summary: str, resources: list[dict]) -> bool:
    """Submit, wait, and answer the only question the agent cares about.

    A SAFE change is not worth waking anybody for, so it passes straight
    through. Anything that destroys or exposes something goes to the
    tablet and hangs here until a human decides.
    """
    try:
        record = submit(tool, summary, resources)
    except urllib.error.URLError as error:
        # The relay is down. Fail closed: an approval system that waves
        # things through when it breaks is not an approval system.
        raise RuntimeError(f"cannot reach the relay at {RELAY}: {error}") from error

    if record["verdict"] == "SAFE":
        return True

    print(f"  [agent] waiting for a human - {record['verdict']} ({record['id']})")
    try:
        status = wait_for_decision(record["id"])
    except ApprovalTimeout:
        print("  [agent] nobody answered - treating silence as NO")
        return False

    return status == "approved"
