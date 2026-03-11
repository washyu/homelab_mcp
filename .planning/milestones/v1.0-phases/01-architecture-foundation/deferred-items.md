# Deferred Items - Phase 01

## Pre-existing Lint Issues

1. **tests/test_proxmox_api.py:1246** - `result` variable assigned but unused (F841, requires `--unsafe-fixes`)
2. **tests/test_proxmox_api.py:1300** - `result` variable assigned but unused (F841, requires `--unsafe-fixes`)

These are pre-existing issues from Plan 01-01 that require ruff's `--unsafe-fixes` flag to auto-fix. Out of scope for Plan 01-03.
