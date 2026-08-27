"""The small server in the middle.

This is Person 2's file. It holds the requests the agent is waiting on,
hands them to the tablet, and remembers what the human tapped.

It also serves the tablet page itself, so there is one server, one port,
and nothing to configure at the event: the tablet just opens the laptop's
address in a browser.

    python3 relay/server.py

No pip install. Standard library only, on purpose - the last thing you
want at hour 6 is a dependency that will not build.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verdict  # noqa: E402

PORT = int(os.environ.get("PORT", "8000"))
TABLET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tablet"
)

# request id -> request dict. In memory on purpose: when the demo ends we
# want the state gone, and a database is a thing that can fail on stage.
REQUESTS: dict[str, dict] = {}
LOCK = threading.Lock()
COUNTER = [0]


def new_request(body: dict) -> dict:
    """Take what the agent sent, score it, and file it as pending."""
    resources = body.get("resources") or []
    with LOCK:
        COUNTER[0] += 1
        request_id = f"req_{COUNTER[0]}"
        record = {
            "id": request_id,
            "tool": body.get("tool", "unknown_tool"),
            "summary": body.get("summary", ""),
            # The agent may propose a verdict; we score it ourselves anyway.
            "verdict": verdict.assess(resources),
            "resources": verdict.annotate(resources),
            "status": "pending",
        }
        REQUESTS[request_id] = record
    return record


def decide(request_id: str, decision: str) -> dict | None:
    with LOCK:
        record = REQUESTS.get(request_id)
        if record is None:
            return None
        if record["status"] == "pending":
            record["status"] = "approved" if decision == "approve" else "blocked"
        return record


class Handler(BaseHTTPRequestHandler):
    # The default logger prints a line per poll and buries the demo output.
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, payload: dict | list):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: str, content_type: str):
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError:
            self._send(404, {"error": "not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if path in ("/", "/index.html"):
            self._send_file(os.path.join(TABLET_DIR, "index.html"), "text/html")
            return

        if path == "/requests/pending":
            with LOCK:
                pending = [r for r in REQUESTS.values() if r["status"] == "pending"]
            self._send(200, pending)
            return

        if path.startswith("/requests/"):
            request_id = path.split("/")[2]
            with LOCK:
                record = REQUESTS.get(request_id)
            if record is None:
                self._send(404, {"error": "no such request"})
                return
            self._send(200, record)
            return

        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "body was not json"})
            return

        if path == "/requests":
            record = new_request(body)
            print(f"  [relay] {record['id']}  {record['verdict']}  {record['summary']}")
            self._send(201, record)
            return

        if path.startswith("/requests/") and path.endswith("/decision"):
            request_id = path.split("/")[2]
            decision = str(body.get("decision", "")).lower()
            if decision not in ("approve", "block"):
                self._send(400, {"error": "decision must be approve or block"})
                return
            record = decide(request_id, decision)
            if record is None:
                self._send(404, {"error": "no such request"})
                return
            print(f"  [relay] {record['id']}  human tapped {decision.upper()}")
            self._send(200, record)
            return

        self._send(404, {"error": "not found"})


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"relay listening on http://0.0.0.0:{PORT}")
    print(f"open the tablet at  http://<this-laptop-ip>:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nrelay stopped")


if __name__ == "__main__":
    main()
