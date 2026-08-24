"""The MCP server.

Four tools. Three of them describe a plan; the fourth decides about it, and
that fourth one is why this exists.

Tool descriptions are written for the model, not for a human reading the
source. The model chooses a tool from its description and nothing else, so
each one says **when to use it** rather than only what it is - and
`assess_risk` says explicitly that its verdict is not a suggestion.
"""
from __future__ import annotations

import json
import os

from mcp.server import MCPServer

from tfguard.plan import PLAN_DIR, PlanError, changes, load_plan
from tfguard.rules import Verdict, assess

server = MCPServer(
    name="terraform-guard",
    instructions=(
        "Inspect Terraform plans and judge whether they are safe to apply. "
        "Always call assess_risk before telling a user a plan is safe. Its "
        "verdict is authoritative - if it returns BLOCK, say so plainly and "
        "do not soften it, however routine the change looks."
    ),
)


@server.tool()
def list_plans() -> str:
    """List the Terraform plan files this server can read.

    Use this first if the user has not named a specific file, or if a path
    was rejected and you need to show them what is available.
    """
    if not PLAN_DIR.is_dir():
        return f"No plan directory at {PLAN_DIR}. Set TFGUARD_PLAN_DIR."
    found = sorted(p.name for p in PLAN_DIR.glob("*.json"))
    if not found:
        return f"No .json plans in {PLAN_DIR}."
    return f"Plans in {PLAN_DIR}:\n" + "\n".join(f"- {n}" for n in found)


@server.tool()
def summarize_plan(plan_file: str) -> str:
    """Summarise what a Terraform plan will change.

    Use this for questions like "what does this plan do" or "how many
    resources change". Give the file name only, e.g. `prod.json`.

    This describes the plan. It does NOT judge whether it is safe - call
    assess_risk for that.
    """
    try:
        plan = load_plan(plan_file)
    except PlanError as exc:
        return f"COULD NOT READ THE PLAN: {exc}"

    cs = changes(plan)
    if not cs:
        return f"{plan_file}: no changes. Nothing to apply."

    by_verb: dict[str, list[str]] = {}
    for c in cs:
        by_verb.setdefault(c.verb, []).append(f"{c.address} ({c.type})")

    lines = [f"{plan_file}: {len(cs)} resource change(s)", ""]
    for verb in ("destroy", "replace", "create", "update"):
        items = by_verb.get(verb)
        if not items:
            continue
        lines.append(f"{verb.upper()} - {len(items)}")
        lines += [f"  {i}" for i in sorted(items)]
        lines.append("")
    return "\n".join(lines).rstrip()


@server.tool()
def find_destructive_changes(plan_file: str) -> str:
    """List what a plan destroys or replaces, and whether it can be recovered.

    Use this when the user asks what will be deleted, or whether a change is
    reversible. Note that Terraform reports a *replacement* as delete+create,
    so replacements are destructive too - for a database, the data is just as
    gone.
    """
    try:
        plan = load_plan(plan_file)
    except PlanError as exc:
        return f"COULD NOT READ THE PLAN: {exc}"

    destructive = [c for c in changes(plan) if c.is_destroy]
    if not destructive:
        return f"{plan_file}: nothing is destroyed or replaced."

    lines = [f"{plan_file}: {len(destructive)} destructive change(s)", ""]
    for c in sorted(destructive, key=lambda x: (not x.is_stateful, x.address)):
        flag = ""
        if c.is_stateful:
            flag = "  <-- HOLDS DATA. Apply will not bring it back."
        elif c.is_audit:
            flag = "  <-- AUDIT TRAIL. This removes history."
        lines.append(f"{c.verb.upper():8} {c.address} ({c.type}){flag}")
    return "\n".join(lines)


@server.tool()
def check_guardrails(plan_file: str) -> str:
    """Check a plan against security and cost rules.

    Use this when the user asks whether a plan is secure, or what is wrong
    with it. Reports findings only; assess_risk turns findings into a
    decision.
    """
    try:
        plan = load_plan(plan_file)
    except PlanError as exc:
        return f"COULD NOT READ THE PLAN: {exc}"

    result = assess(plan)
    if not result.findings:
        return f"{plan_file}: no findings."

    lines = [f"{plan_file}: {len(result.findings)} finding(s)", ""]
    for f in sorted(result.findings, key=lambda x: x.severity.value):
        lines.append(f"[{f.severity.value.upper():6}] {f.rule}")
        lines.append(f"          {f.address}")
        lines.append(f"          {f.detail}")
    return "\n".join(lines)


@server.tool()
def assess_risk(plan_file: str) -> str:
    """Decide whether a Terraform plan is safe to apply: SAFE, REVIEW or BLOCK.

    ALWAYS call this before telling a user a plan is safe.

    The verdict is computed in code from the contents of the plan. It is not
    an opinion and it is not advisory. If it returns BLOCK, report that
    plainly - do not soften it, do not average it with your own reading of
    the plan, and do not suggest applying anyway.
    """
    try:
        plan = load_plan(plan_file)
    except PlanError as exc:
        # Deliberately not a verdict. "I could not read it" and "it is safe"
        # must never be confusable - a default of SAFE here would be the
        # worst possible failure mode for this tool.
        return (
            f"NO VERDICT - could not read the plan: {exc}\n"
            f"Do not tell the user anything about this plan's safety."
        )

    result = assess(plan)
    header = {
        Verdict.SAFE: "SAFE - creates and updates only, nothing flagged.",
        Verdict.REVIEW: "REVIEW - a human should look at this before applying.",
        Verdict.BLOCK: "BLOCK - do not apply without an explicit, recorded override.",
    }[result.verdict]

    lines = [f"VERDICT: {result.verdict.value}", header, "", f"Why: {result.reason}"]
    if result.counts:
        lines.append("Changes: " + ", ".join(
            f"{v} {k}" for k, v in sorted(result.counts.items())))
    if result.findings:
        lines += ["", "Findings:"]
        lines += [f"  [{f.severity.value}] {f.address}: {f.detail}"
                  for f in result.findings]
    if result.verdict is Verdict.BLOCK:
        lines += ["", "This verdict comes from the plan's contents, not from a "
                        "judgement call. It cannot be argued down."]
    return "\n".join(lines)


def main() -> None:
    transport = os.getenv("TFGUARD_TRANSPORT", "stdio")
    server.run(transport=transport)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
