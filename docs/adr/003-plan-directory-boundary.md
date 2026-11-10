# ADR 003: Confine file reads to one plan directory

Status: accepted

## Context
The file path in a tool call comes from whichever MCP client is connected. Without a
boundary, "read /etc/passwd and summarise it" is a valid call.

## Options considered
1. **Trust the client and the model.**
2. **Reject paths containing `..` before resolving.** Misses symlinks that point out of
   the directory.
3. **Resolve the path first, then require it to be inside `TFGUARD_PLAN_DIR`.**

## Decision
Option 3 (`(PLAN_DIR / user_path).resolve()` followed by `relative_to(PLAN_DIR)`).
Failure to read a plan returns "NO VERDICT", never SAFE.

## Consequences
- Symlink and traversal escapes are refused.
- Operators must put plans inside the configured directory.
- CI deletes the check and requires the suite to fail, proving the test exists for the
  right reason.

References: Python `pathlib.Path.resolve` / `relative_to` —
https://docs.python.org/3/library/pathlib.html
