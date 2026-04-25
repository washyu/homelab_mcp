# Deferred Items — Phase 33.1

Out-of-scope pre-existing issues discovered during plan execution.

## Plan 33.1-02 — Pre-existing test failures (NOT introduced by this plan)

Verified against base commit `e6cf7a1` — both fail without any Plan 02 changes applied.

| Test | File | Failure | Scope |
|------|------|---------|-------|
| `test_ssh_credentials_table_dropped_postgres` | `tests/test_database.py:538` | `monkeypatch.setattr("src.homelab_mcp.database.psycopg2", ...)` — ImportError because `database` is a module, not a package. The test assumes `database` is a package with `psycopg2` sub-module. | Pre-existing database module shape mismatch. Out of scope for Plan 02 (schema cleanup). Candidate for a follow-up fix. |
| `TestGetProxmoxClient::test_client_missing_host` | `tests/test_proxmox_api.py:230` | Expects `ValueError("Proxmox host must be provided...")` — not raised. Handler behavior changed or test env leaks `PROXMOX_HOST`. | Pre-existing Proxmox client behavior/test-isolation bug. Out of scope for Plan 02. |

Plan 02's own tests (`test_discover_and_map_schema_no_password_no_mcp_admin_default`, `test_update_mcp_admin_groups_schema_no_password`, `test_sitemap_tool_schemas`) all pass. The full sweep has **only these two pre-existing failures**, matching the baseline.
