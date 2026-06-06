## Summary

<!-- What does this PR do and why? -->

## Phase / scope

<!-- e.g. Phase 4 — risk + paper execution -->

## Checklist

- [ ] `uv run ruff check . && uv run ruff format --check .` passes
- [ ] `uv run pytest` passes (DB-integration tests run in CI)
- [ ] No secrets committed — `gitleaks` clean, nothing read from anything but `.env`
- [ ] Backtests report **net** P&L (full transaction costs applied)
- [ ] `LiveGateway` remains stubbed — no real orders placed
- [ ] Tests added/updated alongside the code; Kite calls are mocked

## Notes

<!-- Design decisions, follow-ups, anything reviewers should know -->
