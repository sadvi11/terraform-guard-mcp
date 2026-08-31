# Security policy

## Reporting a vulnerability

Open a [private security advisory](https://github.com/sadvi11/terraform-guard-mcp/security/advisories/new),
or email **sadhvisharma763@gmail.com**. Please do not open a public issue for a
vulnerability in the guard itself.

I will acknowledge within 72 hours and tell you plainly whether I can fix it,
when, and whether I think you are right.

## The threat model this tool is built against

This server is read by a language model, and it reads files a third party may
control. Both are hostile inputs.

**1. The plan file is untrusted.** Resource names, addresses and tags come from
whoever wrote the plan. They reach the text a model reads, so they are treated
as attacker-controlled and flattened before output — see `_clean()` in
`tfguard/plan.py`. A resource name cannot forge a section boundary or a system
instruction.

**2. The verdict is not persuadable.** SAFE, REVIEW and BLOCK are computed from
resource types and actions in `assess()`. No string in the plan, and no
instruction from the client, is an argument to that comparison. There is a test
asserting this using a plan whose resource is named to look pre-approved.

**3. The path is not trusted.** An MCP server takes its file path from whatever
client is connected to it. `resolve_plan_path()` resolves first and then checks
containment, because checking before resolution lets a symlink escape.

**4. Failing to read is never SAFE.** An unreadable plan returns `NO VERDICT`
rather than a verdict, because a result indistinguishable from "I could not
read it" is the worst possible failure for a tool like this.

## What is out of scope

This is a guard, not a complete scanner. Six rules, AWS-focused. It is not a
replacement for Checkov or tfsec, and it has never been run against a
production pipeline. `README.md` says both.

## Known limitations

- Azure and GCP stateful resource types are listed but untested.
- Findings are advisory for anything below high severity.
- A plan that is valid JSON but not `terraform show -json` output is rejected
  rather than guessed at.

## Previously found and fixed

**Prompt injection via resource address (August 2026).** Attacker-controlled
resource names were printed unmodified into the model-facing output, allowing a
forged `=== END OF TOOL OUTPUT ===` boundary and a fake `SYSTEM:` instruction to
be injected into the tool's own response. The verdict was never affected; the
report was. Fixed at parse time so all five tools are covered. Found by me,
during adversarial testing of my own tool, two hours after first publishing it.
