# ADR 001: The verdict is computed in code, not by the model

Status: accepted

## Context
An AI assistant asked "is this Terraform plan safe to apply?" answers from judgement.
Terraform writes a replacement as `delete` + `create`, so a replaced database can read
as routine. The plan file is also untrusted input: resource names are free text that
the model will read.

## Options considered
1. **Prompt the model to be careful.** Cheap, but a prompt is a request, not a guarantee.
2. **Let the model call a scanner and relay its output.** Better, but the model still
   decides how to word and weigh the result.
3. **Compute SAFE / REVIEW / BLOCK in a plain function (`tfguard.rules.assess`) and
   expose it as one MCP tool whose description tells the model to report it verbatim.**

## Decision
Option 3. The verdict depends only on resource types and planned actions in the plan,
never on resource names, comments or the model's reading. A small, readable rule set
(six rules) is preferred over a large one that people learn to skip.

## Consequences
- Deterministic and unit-testable with no cloud account, key or network.
- Hostile wording in a plan cannot change the verdict (covered by a test).
- Coverage is only as wide as the rules: it is a guard, not a replacement for a full
  scanner such as Checkov. New resource types require a code change.
- CI removes the BLOCK logic on purpose and requires the suite to go red, so the
  guard is shown to be load-bearing.
