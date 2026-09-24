# What changed and why (one paragraph, plain words)

# Brain refs (e.g. `04_BUSINESS_RULES.md §2`) or "none"

# ADR (link if this bends the brain, else "n/a")

Checklist before asking for review:

- [ ] `ruff check` + `ruff format --check` clean
- [ ] `mypy app worker engine seed` clean
- [ ] `pytest -q` green (new behavior has a test, incl. a negative one)
- [ ] No real supplier/price/contract data anywhere in the diff
- [ ] docs/BUILD_LOG.md has an entry
