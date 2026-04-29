# Phase 39.1 Deferred Items

Out-of-scope discoveries logged during Phase 39.1 plan 01 execution. These predate this phase's changes (verified by running ruff/mypy on only the files modified in 39.1 — both pass cleanly).

## Pre-existing ruff issues (UP037 / F401)

`uv run ruff check src/ tests/` reports 9 errors at HEAD, all in files NOT touched by Phase 39.1:

- `tests/test_credential_store.py` — UP037 quoted-annotation removal needed (multiple `"pytest.MonkeyPatch"` occurrences)
- `tests/test_credentials_cli.py` — UP037
- `tests/test_openapi_infra_requirements.py` — formatting
- `tests/test_proxmox_tools_schema.py` — formatting
- `tests/test_sitemap.py` — formatting + unused `MagicMock` import
- `tests/test_ssh_tools.py` — formatting

All 9 are auto-fixable (`ruff check --fix`) but per SCOPE BOUNDARY rule are not Phase 39.1's responsibility — they pre-date this phase's commits.

## Pre-existing mypy issue

`src/homelab_mcp/openapi_app.py:18` — `Library stubs not installed for "jsonschema"`. Pre-existing; unrelated to drift_detection.py.

## Pre-existing bandit findings

`uv run bandit -r src/` reports 13 medium-confidence and 31 high-confidence findings at HEAD. Bandit on `src/homelab_mcp/drift_detection.py` (the only src file modified in this phase) returns 0 findings, confirming Phase 39.1 introduces no new security issues.

## Disposition

These items are tracked here, not fixed, per the GSD scope-boundary rule: "Only auto-fix issues DIRECTLY caused by the current task's changes." A future cleanup phase (or v1.8 hygiene sweep) should address them.
