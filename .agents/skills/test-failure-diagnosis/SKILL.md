---
name: test-failure-diagnosis
description: >
  Use when `mise run check` fails, when tests fail after a code change, or
  before running `--update-fixtures` or editing a test assertion. Prevents the
  anti-pattern of updating tests or fixtures to match incorrect output.
---

# Test Failure Diagnosis

When a test fails after a code change, the failure is signal — not noise to
suppress. Read what the test was asserting before touching it.

## The anti-pattern to avoid

```
1. Change algorithm
2. Tests fail
3. ❌ Edit test assertions / regenerate fixtures to match new output
4. Tests pass — bug silently baked in
```

This happened in PR #185: a formula change produced wrong alignment output.
The unit test caught it. The test was updated to pass instead of fixing the
formula. The regression survived until a human noticed the visual output.

## Decision tree when a test fails

```
Test fails after my change
│
├── Is the new behavior INTENTIONALLY correct?
│   ├── Yes → update test/fixture, document why the style changed
│   └── No  → fix the code, not the test
│
└── Unsure? → re-read what the test asserts, compare to the style guide,
              ask before changing anything
```

## Fixture safety (`--update-fixtures`)

`uv run pytest tests/test_fixtures.py --update-fixtures` regenerates all
`.expected.sql` files to match current output. It is only safe when:

- The output change is **intentional** (new rule, deliberate style change)
- You have **reviewed every regenerated file** — run the diff, read each one

Never run `--update-fixtures` as a way to silence failures without reviewing
the diff. A regenerated file that looks wrong means the code is wrong.

## Unit tests encode style contracts

Tests in `tests/test_formatter.py` (e.g. `test_alias_alignment_applied`)
lock in specific formatting behaviour. They should change only when the
**style itself** intentionally changes — not to accommodate an algorithm that
happens to produce different output.

If a formatter unit test fails:
1. Read the assertion carefully
2. Check `docs/sql-style-guide.md` for the documented rule
3. If the rule hasn't changed, the code is wrong — fix the code
4. If the rule is changing intentionally, update the style guide first, then
   the test, then regenerate fixtures

## Quick reference

| Situation | Correct action |
|---|---|
| Unit test fails, style rule unchanged | Fix the code |
| Unit test fails, style rule intentionally changing | Update style guide → test → fixtures |
| Fixture test fails, output looks correct | Regenerate + review diff |
| Fixture test fails, output looks wrong | Fix the code |
| Unsure if output is correct | Check `docs/sql-style-guide.md` or ask |
