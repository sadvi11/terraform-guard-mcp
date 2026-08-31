# Contributing

Contributions welcome, especially new rules and new hostile test cases.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest                      # 34 tests. No cloud account, no API key, no network.
```

## The one rule for this repository

**Every guard must be provably able to fail.** CI removes each of the three
safety controls in turn and fails the build if the suite still passes without
it. If you add a guard, add the fault injection with it. A test that cannot go
red is worse than no test, because it produces confidence without coverage.

## Adding a rule

1. Write the failing test first, in `tests/test_guard.py`.
2. Add a fixture to `plans/` and allowlist it in `.gitignore` — real Terraform
   plans can contain secrets, so `plans/*` is denied and fixtures are permitted
   by name.
3. Add the rule to `tfguard/rules.py`. Rules return findings; only `assess()`
   decides a verdict.
4. Register it in `ALL_RULES_CHANGES` or `ALL_RULES_PLAN`.
5. Add the fault injection to `.github/workflows/ci.yml` if the rule is
   load-bearing.

## Deciding severity

`high` blocks. Everything else is advisory. Reserve `high` for things that are
unrecoverable — data destroyed, audit history removed, management ports opened
to the internet. **A tool that blocks everything gets ignored, and then it
blocks nothing.**

## Tests

Assert the property, not the wording. When testing untrusted input, assert that
hostile text cannot forge *structure* — the words themselves may legitimately be
part of a resource name, and removing them would misreport the plan.
