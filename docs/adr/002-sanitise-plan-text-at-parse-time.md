# ADR 002: Sanitise untrusted plan text at parse time

Status: accepted

## Context
Resource addresses come from the plan file and are echoed in tool output that a model
reads. A newline inside an address can forge a fake "end of tool output" boundary
followed by instructions, even though the verdict line itself stays correct.

## Options considered
1. **Escape inside `assess_risk` output only.** Covers one tool; `summarize_plan` and
   `find_destructive_changes` echo the same addresses.
2. **Sanitise when each tool formats output.** Easy to forget in a new tool.
3. **Sanitise once, where a `Change` is built (`tfguard/plan.py`).**

## Decision
Option 3: whitespace (including newlines and tabs) is flattened to single spaces and
values are truncated to 120 characters in `_clean`, applied in both `changes()` and
`after_values()`.

## Consequences
- Every tool inherits the protection, including ones added later.
- The text of a hostile name still appears (it is genuinely part of the plan); what is
  prevented is a forged boundary getting a line of its own. Tests assert structure,
  not vocabulary.
- Names longer than 120 characters are truncated in output, which is a deliberate
  loss of detail.
