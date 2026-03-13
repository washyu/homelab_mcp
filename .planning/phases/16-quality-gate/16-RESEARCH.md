# Phase 16: Quality Gate - Research

**Researched:** 2026-03-13
**Domain:** Python static analysis — ruff, mypy, bandit
**Confidence:** HIGH

## Summary

Phase 16 is a clean-up gate, not a feature phase. The goal is to make three tools exit 0 against the full `src/` tree: ruff, mypy, and bandit. The v1.2 change surface (Phases 12-15 new files) is already clean across all three tools. Two pre-existing problems in older files block the "exits 0" requirement and must be resolved.

**Ruff** already passes cleanly (`uv run ruff check src/ tests/` exits 0, no output). No work required here.

**Mypy** fails with 2 errors in `src/homelab_mcp/database.py` — missing type stubs for `psycopg2`, which is an optional soft-dependency imported inside a `try/except` block. The fix is a `[[tool.mypy.overrides]]` block in `pyproject.toml` telling mypy to ignore missing imports for the `psycopg2` module family.

**Bandit** exits 1 (non-zero) due to 9 medium-severity findings across three pre-existing files: `config.py` (1x B104), `database.py` (2x B608), and `infrastructure_crud.py` (6x B108). Every finding is intentional by design. The fix is surgical `# nosec` inline comments on the 9 specific lines.

**Primary recommendation:** Two targeted changes — one `[[tool.mypy.overrides]]` block in `pyproject.toml`, and 9 `# nosec` inline comments across 3 pre-existing files. No v1.2 feature code changes required.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QA-01 | All pre-commit checks (ruff, mypy, bandit) pass cleanly across all v1.2 changes | Ruff already passes; mypy blocked by psycopg2 stubs gap; bandit blocked by 9 pre-existing medium findings in non-v1.2 files — each has a documented fix below |
</phase_requirements>

## Current State (Verified 2026-03-13)

| Tool | Command | Current Exit | Target Exit | Work Needed |
|------|---------|-------------|-------------|-------------|
| ruff | `uv run ruff check src/ tests/` | 0 (PASS) | 0 | None |
| mypy | `uv run mypy src/` | 1 (FAIL) | 0 | Add psycopg2 override |
| bandit | `uv run bandit -r src/` | 1 (FAIL) | 0 | Add 9 `# nosec` comments |

## Standard Stack

### Tools in Use (Project-Standard, No Changes)

| Tool | Version | Command | Configuration |
|------|---------|---------|---------------|
| ruff | latest (in lock) | `uv run ruff check src/ tests/` | `[tool.ruff]` in `pyproject.toml` |
| mypy | >=1.13.0 | `uv run mypy src/` | `[tool.mypy]` in `pyproject.toml` |
| bandit | 1.8.6 | `uv run bandit -r src/` | `[tool.bandit]` in `pyproject.toml` |

### Existing pyproject.toml Configuration

**Ruff** (`pyproject.toml` lines 152-173):
- Selects: E, W, F, I (isort), B (bugbear), C4, UP (pyupgrade)
- Ignores: E501, B008, C901
- Per-file ignores for tests: B018, S101, S105, S106

**Mypy** (`pyproject.toml` lines 175-205):
- Strict settings: `disallow_untyped_defs`, `warn_return_any`, `strict_equality`, etc.
- Existing overrides: `tests.*` (relaxed), `homelab_mcp.http_app` (warn_unused_ignores=false)
- Pre-commit hook uses `--ignore-missing-imports`; `uv run mypy src/` does NOT — this gap causes the failure

**Bandit** (`pyproject.toml` lines 207-209):
- `exclude_dirs = ["tests"]`
- `skips = ["B101", "B601"]` — assert_used and shell=True already suppressed
- No `--exit-zero` in config; bandit exits 1 by default when any non-skipped finding exists

## Architecture Patterns

### Fix 1: Mypy psycopg2 Override (pyproject.toml)

**What:** `psycopg2` is imported inside a `try/except ImportError` block in `database.py:15-21`. It is not in the project's main dependencies (not in `uv.lock`). Mypy reports `import-untyped` errors because no stubs package exists in the environment.

**Why `ignore_missing_imports` override is correct:** The pre-commit hook already passes `--ignore-missing-imports` to mypy and succeeds. The canonical `uv run mypy src/` command (per CLAUDE.md success criteria) runs without this flag. Adding a module-scoped override in `pyproject.toml` makes both the CLI and hook consistent without weakening type checking on any homelab code.

**Do NOT** add `types-psycopg2` as a dependency. `psycopg2` is an optional feature for PostgreSQL database backends, not a core requirement. Installing stubs for an uninstalled optional library creates false type-checking coverage.

**Configuration change:**
```toml
[[tool.mypy.overrides]]
module = ["psycopg2", "psycopg2.*"]
ignore_missing_imports = true
```

Add this block after the existing `homelab_mcp.http_app` override (after line 205 in current `pyproject.toml`).

### Fix 2: Bandit #nosec Comments

**What:** 9 medium-severity bandit findings in 3 pre-existing files. All are intentional design decisions, not security vulnerabilities. Each needs a `# nosec BXXX` inline comment with a brief justification.

**Why `# nosec` over pyproject.toml `skips`:** The `skips` approach would suppress the rule class globally across all files including future code. `# nosec` on specific lines is surgical — future accidental uses of the same patterns in new code will still be flagged.

#### File: `src/homelab_mcp/config.py` (1 change)

| Line | Finding | Fix |
|------|---------|-----|
| 17 | B104: `"0.0.0.0"` hardcoded bind address | `# nosec B104 — configurable via MCP_HTTP_HOST env var; 0.0.0.0 is intentional default for homelab use` |

**Context:** `self.host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")` — the value comes from an environment variable; `0.0.0.0` is only the fallback default, appropriate for homelab server binding.

#### File: `src/homelab_mcp/database.py` (2 changes)

| Line | Finding | Fix |
|------|---------|-----|
| 581 | B608: SQL injection via f-string `UPDATE ssh_credentials SET {set_clause}` | `# nosec B608 — set_clause built from validated column names, not user input` |
| 1175 | B608: same pattern in PostgreSQL adapter | `# nosec B608 — set_clause built from validated column names, not user input` |

**Context:** `set_clause` is constructed from `**kwargs` where keys are column names validated by the caller. The SQL values are properly parameterized with `?` / `%s` placeholders. Bandit cannot statically prove the column names are safe — the `# nosec` annotation documents the human review.

#### File: `src/homelab_mcp/infrastructure_crud.py` (6 changes)

| Line | Finding | Fix |
|------|---------|-----|
| 485 | B108: `/tmp/infrastructure_backup_{backup_id}.json` | `# nosec B108 — backup_id is a UUID; /tmp use is intentional for homelab single-operator context` |
| 517 | B108: same path in restore function | `# nosec B108 — backup_id is a UUID; /tmp use is intentional for homelab single-operator context` |
| 1218 | B108: `/tmp/{service_name}_migration.tar.gz` | `# nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context` |
| 1219 | B108: same path (local destination) | `# nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context` |
| 1224 | B108: same path (upload source) | `# nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context` |
| 1225 | B108: same path (upload destination) | `# nosec B108 — SFTP transfer path; service_name is validated; homelab single-operator context` |

**Context:** Lines 1218-1225 are SFTP `get()`/`put()` arguments — string arguments to an SSH file transfer, not local `open()` calls. Bandit flags any string containing `/tmp/` regardless of whether it's a local path. The `backup_id` (lines 485/517) is a UUID generated internally.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Suppressing known false positives | Custom bandit wrapper script | `# nosec` inline annotation | Bandit's built-in mechanism; visible at point of use |
| Ignoring optional package stubs | `--ignore-missing-imports` CLI flag | `[[tool.mypy.overrides]]` in pyproject.toml | Config-file approach is persistent; CLI flag is session-only and inconsistent with pre-commit |
| Scoping bandit to v1.2 files only | Enumerating file list | Fix the pre-existing issues | Phase goal is full-codebase clean exit; partial scoping does not satisfy QA-01 |

## Common Pitfalls

### Pitfall 1: Wrong nosec Syntax

**What goes wrong:** `# nosec` (bare, no rule ID) suppresses ALL bandit findings on that line, including future ones. Also, `# nosec: B108` (with colon) is invalid syntax — bandit silently ignores it, so the finding persists.
**How to avoid:** Use `# nosec B108` (space-separated, no colon). Verify with `uv run bandit -r src/ --ignore-nosec` to confirm the nosec is parsed correctly (issues reappear).
**Warning signs:** Bandit still reports the line after adding `# nosec` — check spacing and rule ID format.

### Pitfall 2: Mypy Override Module Pattern

**What goes wrong:** `module = "psycopg2"` only suppresses errors for the top-level import. `import psycopg2.extras` triggers a separate error for the submodule.
**How to avoid:** Use `module = ["psycopg2", "psycopg2.*"]` (list form with wildcard).
**Warning signs:** After adding the override, mypy still reports 1 error for `psycopg2.extras`.

### Pitfall 3: Bandit Exit Code vs. pyproject Config

**What goes wrong:** The `[tool.bandit]` section in `pyproject.toml` is ONLY read when bandit is invoked with `-c pyproject.toml`. The plain `uv run bandit -r src/` command does NOT automatically read `pyproject.toml` unless bandit is invoked from the project root and a `.bandit` file exists.
**How to avoid:** Verify using `uv run bandit -r src/` (not `-c pyproject.toml`) to confirm the `# nosec` comments are effective regardless of config file loading.
**Warning signs:** Findings disappear with `-c pyproject.toml` but persist without it.

### Pitfall 4: Mypy Runs Inside Pre-commit Isolated Env

**What goes wrong:** The pre-commit mypy hook already passes `--ignore-missing-imports`. After adding the pyproject.toml override, running pre-commit may trigger `warn_unused_ignores` if the override flag now conflicts with the hook's `--ignore-missing-imports` argument.
**How to avoid:** The psycopg2 override uses `ignore_missing_imports = true` (a per-module flag), not a `# type: ignore` comment. This does not trigger `warn_unused_ignores`. The existing `homelab_mcp.http_app` override uses `warn_unused_ignores = false` as a precedent for exactly this situation — no need to replicate that pattern for psycopg2.
**Warning signs:** After the fix, `uv run mypy src/` passes but pre-commit mypy fails.

### Pitfall 5: Treating Low Severity bandit Findings as Blocking

**What goes wrong:** After the 9 medium `# nosec` fixes, `uv run bandit -r src/` may still exit 1 if there are any low-severity findings that bandit reports without the `-c pyproject.toml` flag (which currently skips B101 assert_used).
**How to avoid:** Run `uv run bandit -r src/` (the exact success-criteria command) and check the exit code, not the output summary.
**Warning signs:** The run reports only LOW findings but still exits 1.

## Code Examples

### pyproject.toml Mypy Override (verified pattern from existing project)

```toml
# Add after the homelab_mcp.http_app override block (currently lines 197-205)
[[tool.mypy.overrides]]
module = ["psycopg2", "psycopg2.*"]
ignore_missing_imports = true
```

Source: Existing pattern in this project — `homelab_mcp.http_app` override at `pyproject.toml:197-205`.

### #nosec Comment Syntax

```python
# CORRECT — space-separated, specific rule ID
self.host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")  # nosec B104 — configurable via env var

# CORRECT — multiple rules
value = f"UPDATE {table} SET {col} WHERE id = ?"  # nosec B608 B105

# WRONG — colon syntax (silently ignored by bandit)
self.host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")  # nosec: B104

# WRONG — bare nosec (suppresses all rules, too broad)
self.host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")  # nosec
```

Source: bandit documentation — https://bandit.readthedocs.io/en/latest/config.html#suppressing-individual-lines

### Verification Commands

```bash
# Verify ruff (should already pass)
uv run ruff check src/ tests/

# Verify mypy after override addition
uv run mypy src/

# Verify bandit after nosec comments
uv run bandit -r src/

# Verify nosec comments are being parsed (re-run ignoring them — should show original issues)
uv run bandit -r src/ --ignore-nosec | grep -E "Location:|Severity:"

# Run full test suite to confirm no regressions
uv run pytest tests/ -m "not integration" -q
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `--ignore-missing-imports` CLI flag for mypy | `[[tool.mypy.overrides]]` per module | Precise scoping; consistent between CLI and pre-commit |
| Blanket `skips` in bandit config | `# nosec BXXX` inline annotation | Visible at point of use; future code still checked |
| `|| true` in CI (current main.yml) | Fix underlying issues for clean exit | Phase 16 makes QA meaningful instead of cosmetic |

## Open Questions

1. **Bandit exit code without `-c pyproject.toml`**
   - What we know: Without `-c pyproject.toml`, bandit does NOT read `skips = ["B101", "B601"]` from pyproject.toml. This means B101 (assert_used) and B601 (shell=True) findings in `src/` will appear.
   - What's unclear: Whether those findings exist in src/ (they do — database.py and ssh_tools.py have `assert` statements, but B101 is in the skips list only when `-c` is used).
   - Recommendation: The plan must verify that `uv run bandit -r src/` (without `-c`) exits 0 after all `# nosec` annotations are added. If B101/B601 findings in `src/` cause a non-zero exit, those lines may also need `# nosec` annotations OR the `[tool.bandit]` skips must be confirmed as auto-detected from pyproject.toml in the project root.

   **Follow-up check needed in plan Wave 0:** Run `uv run bandit -r src/` in the project root and observe whether pyproject.toml is auto-detected.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -m "not integration" -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QA-01 | `uv run ruff check src/ tests/` exits 0 | smoke | `uv run ruff check src/ tests/` | N/A — tool invocation |
| QA-01 | `uv run mypy src/` exits 0 | smoke | `uv run mypy src/` | N/A — tool invocation |
| QA-01 | `uv run bandit -r src/` exits 0 | smoke | `uv run bandit -r src/` | N/A — tool invocation |

**Note:** QA-01 is verified by direct tool invocation, not by pytest tests. The "test" for this phase IS the quality tool run. No new pytest test files are needed.

### Sampling Rate
- **Per task commit:** `uv run ruff check src/ tests/ && uv run mypy src/ && uv run bandit -r src/`
- **Per wave merge:** Full suite: `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** All three quality tools exit 0 before `/gsd:verify-work`

### Wave 0 Gaps
None — no new test infrastructure required. Quality checks are the verification mechanism for this phase.

## Sources

### Primary (HIGH confidence)
- Direct tool execution against the codebase — all findings verified by running the actual commands
- `pyproject.toml` inspection — current tool configurations confirmed by reading the file
- `git log` — confirmed pre-existing files (config.py, database.py, infrastructure_crud.py) were not changed in phases 12-15

### Secondary (MEDIUM confidence)
- bandit documentation on `# nosec` syntax — https://bandit.readthedocs.io/en/latest/config.html

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Current tool state (ruff/mypy/bandit): HIGH — directly observed by running tools
- Fix approach (nosec syntax, mypy overrides): HIGH — matches existing patterns in the project
- Bandit auto-detect of pyproject.toml: MEDIUM — observed that `uv run bandit -r src/` and `uv run bandit -r src/ -c pyproject.toml` produce different counts; the auto-detection behavior needs confirmation in Wave 0

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (tools are stable; findings are pre-existing and won't change unless someone edits those files)
