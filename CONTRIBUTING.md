# Contributing

Solo, personal project — but the workflow keeps changes reviewable and safe.

## Workflow

1. Branch off `main` (one branch per phase/feature).
2. Write tests alongside code. **Mock all Kite calls** — no live API in tests/CI.
3. Run the gates locally before pushing:
   ```bash
   uv run ruff check . && uv run ruff format --check .
   uv run pytest
   ```
4. Open a PR (the template's checklist must pass). CI runs gitleaks, ruff, and
   pytest against TimescaleDB + Redis.
5. Merge to `main` once CI is green.

## Hard rules

- **Secrets never touch git.** Read them via `pydantic-settings` from `.env`
  (gitignored). `gitleaks` runs on every commit and in CI.
- **Backtests report net P&L** after the full cost stack — never gross.
- **No real orders.** `LiveGateway` stays stubbed (`NotImplementedError`).

## Recommended branch protection for `main`

Set these in **Settings → Branches → Add branch ruleset** (requires repo admin;
can't be configured from code):

- Require a pull request before merging (1 approval; CODEOWNERS review).
- Require status checks to pass: **Secret scan (gitleaks)**, **Lint (ruff)**,
  **Tests (pytest)**.
- Require branches to be up to date before merging.
- Block force pushes and deletions of `main`.
