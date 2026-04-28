---
name: test-integrity
description: >-
  Use whenever `mise run check` or `mise run test` fails after changing formatter
  logic, generator overrides, or rule implementations. Ensures test failures are
  diagnosed as signals — not suppressed by updating tests or regenerating fixtures
  to match new (potentially wrong) output.
---

# Test Integrity

## The Anti-Pattern to Avoid

```
1. Change algorithm
2. Tests fail
3. ❌ Update tests/fixtures to match the new (wrong) output  ← bug baked in
4. Tests pass — regression silently hidden
```

This happened in PR #185: a formula change introduced a regression; the failing
test was updated to assert the wrong value instead of fixing the formula. The bug
survived until the user spotted it visually.

**Never update a test or regenerate a fixture until you understand why it failed.**

## When Tests Fail After a Code Change

1. **Read the failure message in full.** What value did the test expect?
   What did it actually get?
2. **Check what the test was asserting.** Open the test and confirm it was
   expressing the correct intended behavior.
3. **Ask: is the new output correct?**
   - **Yes** — the style rule intentionally changed. Update the test and
     fixtures to reflect the new contract. Document the change in
     `docs/sql-style-guide.md`.
   - **No** — the algorithm introduced a regression. Fix the code; do not
     touch the test.

## Tests Are Style Contracts

Unit tests in `tests/test_formatter.py` encode the project's style
decisions. They should only change when the *style itself* intentionally
changes, not as a side-effect of reformulating an algorithm.

If a test is in the way of passing `mise run check`, the test is doing its
job. Read it before touching it.

## `--update-fixtures` Is Not a Fix

```bash
# ⚠️  Only safe when you have already verified the new output is correct
uv run pytest tests/test_fixtures.py --update-fixtures
```

`--update-fixtures` regenerates `.expected.sql` files from the current
formatter output. If the formatter is wrong, this bakes the bug into the
fixture and hides it from future runs.

Run `--update-fixtures` only after confirming the output change is
intentional. Always `git diff` the regenerated fixtures before committing.

## Checklist Before Updating a Test or Fixture

- [ ] I read the full failure message
- [ ] I opened the test and confirmed what it was asserting
- [ ] I verified the new formatter output is the *correct* intended output
- [ ] I am updating the test because the **style rule changed**, not because
      the test was inconvenient
- [ ] I updated `docs/sql-style-guide.md` if the style contract changed
- [ ] I `git diff`-ed regenerated fixtures and reviewed every change

## Guardrails

- **Never run `--update-fixtures` as the first response to a failing test.**
  Always diagnose first.
- **Never change a unit test assertion to make it pass** unless you have
  confirmed the old assertion was wrong.
- A test that fails after your change is evidence about your change.
  Treat it as signal, not noise.
- If `mise run check` is failing and you cannot determine whether the new
  output is correct or not, stop and ask a human before proceeding.
