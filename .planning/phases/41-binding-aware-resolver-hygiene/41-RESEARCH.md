# Phase 41: Binding-Aware Resolver Hygiene — Research

**Researched:** 2026-04-29
**Domain:** Python async resolver / row-binding refactor; UAT bug closure (Bugs AA, BB, V)
**Confidence:** HIGH (codebase verified)

## Summary

Three UAT bugs (AA, BB, V) trace to one architectural inconsistency: `discover_and_map` and `scan_drift` both want "look up the sitemap row, use its bound credential, dial its connection_ip" — but only `scan_drift` actually does that. `discover_and_map` resolves SSH credentials by hostname-keyring scan (registry only, sitemap-row-blind), dials the user-supplied identifier rather than the row's `connection_ip`, and on failure produces an error envelope with no `hostname` field, which `parse_discovery_output` then materializes as a degenerate `(hostname="", connection_ip=<input>)` zombie row.

The fix is a single shared sitemap-row-aware resolver that both call sites use:
1. **Lookup**: `find_devices_by_hostname_or_ip(identifier)` (already exists at `database.py:440-452`).
2. **Resolve**: thread the row's `ssh_credential_id` through `resolve_ssh_credentials(..., credential_id=...)` (D-14 keyword-only, already exists at `ssh_tools.py:95+`).
3. **Dial**: use `row.connection_ip` when present, else fall back to the input identifier.
4. **Persist on failure**: when discovery fails, write the error to a row keyed on the resolved `(hostname, connection_ip)` pair from the sitemap row — never to a degenerate `(hostname="", ...)` row.

This mirrors `_bulk_universal_core_probes._probe_one` (`drift_detection.py:488-541`), which is the working reference for Bug AA. The shared helper plus an AST guard (mirroring Phase 41.1's `TestPhase41_1KeyringHygiene` pattern at `tests/test_ast_regression.py:1072-1196`) locks the invariant.

**Primary recommendation:** Extract a single `resolve_ssh_for_sitemap_row(identifier) -> (SSHCredentials, sitemap_row | None)` helper in `ssh_tools.py`. Both `discover_and_store` and `_bulk_universal_core_probes._probe_one` call it. AST guard in `test_ast_regression.py` enforces the invariant.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| Bug AA | `discover_and_map hostname=<sitemap-row-hostname>` resolves SSH credentials via the same row-binding-aware helper that drift scan uses | New shared helper `resolve_ssh_for_sitemap_row()`; both `sitemap.discover_and_store` and `drift_detection._bulk_universal_core_probes._probe_one` call it. Reference impl at `drift_detection.py:497`. |
| Bug V | When a sitemap row exists for the target identifier, the Proxmox API client and SSH dial target use `row.connection_ip`, not `row.hostname` | The shared helper returns the sitemap row alongside resolved creds; both call sites use `row.connection_ip` (when truthy and non-degenerate) for the dial target. Same fix applies inside `drift_detection.py:759-763` (today passes `host=hostname`). |
| Bug BB | A failed `discover_and_map` writes the error to a row matching the requested identifier, never a degenerate empty-hostname zombie row | Fix in two places: (a) `error_handling.py:248-317` `ssh_connection_wrapper` error envelopes need a `hostname` field set to the input identifier; (b) `sitemap.parse_discovery_output` at `sitemap.py:138-141` uses the input identifier for `hostname` on the error path; (c) `discover_and_store` looks up the existing sitemap row first and merges error onto it instead of inserting a fresh degenerate row. |
| AST Guard | Locks the shared-helper invariant for both `discover_and_map` and `_drift_probe_one` (or successor symbols) | Mirror Phase 41.1's `TestPhase41_1KeyringHygiene` allowlist pattern. New class `TestPhase41BindingAwareResolver` with two checks: (a) every direct call to `resolve_ssh_credentials(...)` from `sitemap.py` and `drift_detection.py` is on the allowlist of "intentional bypass" call sites, otherwise it must go through `resolve_ssh_for_sitemap_row(...)`; (b) the new helper exists and both call sites use it. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Sitemap row lookup by identifier | Database adapter (`database.py:440 find_devices_by_hostname_or_ip`) | — | Single funnel; SQLite + Postgres parity already exists |
| SSH credential resolution by UUID | Resolver (`ssh_tools.resolve_ssh_credentials` Tier-0) | — | UUID short-circuit already wired (Phase 38.1 D-14) |
| Row-binding-aware credential resolution | New helper in `ssh_tools.py` | Both `sitemap.py` and `drift_detection.py` consume it | New code; locks Bug AA invariant |
| SSH dial target selection (connection_ip vs hostname) | New helper in `ssh_tools.py` | — | Bug V fix point; helper returns the row for both creds and dial target |
| Discovery failure persistence (non-degenerate row) | `sitemap.discover_and_store` + `database.store_device` | `error_handling.ssh_connection_wrapper` (envelope shape) | Failed-discovery path must carry the requested identifier through to the row write |
| AST guard | `tests/test_ast_regression.py` | — | Mirrors `TestPhase41_1KeyringHygiene`, `TestPhase381CredBinding`, `TestPhase39_1NoSkipInDriftEnum` patterns already in this file |

## Standard Stack

### Core (already in tree, no new deps)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncssh` | >=2.14.0 | Async SSH client used by `ssh_discover_system` | Project standard since v1.0 |
| `aiohttp` | >=3.9.0 | Async HTTP client for Proxmox API | Project standard since v1.0 |
| `pytest` + `pytest-asyncio` | >=8.3.5 / >=0.23.0 | Test framework | Project standard |
| `pytest-mock` | >=3.14.0 | `mocker.patch` for SSH connection / sitemap row mocks | Project standard |
| `ast` (stdlib) | 3.12 | AST guard implementation | Pattern established in Phase 33.1 D-14, 35 D-14/15/16, 38.1 D-15, 39.1, 41.1 |

**No new dependencies required.** All work is internal refactor + new shared helper + new AST guard class.

[VERIFIED: `pyproject.toml` lines for asyncssh/aiohttp/pytest checked at research time]

### Tooling

| Tool | Command | When |
|------|---------|------|
| Test runner | `uv run pytest tests/test_sitemap.py tests/test_ssh_tools.py tests/test_drift_detection.py tests/test_ast_regression.py -v` | Per-task |
| Targeted run | `uv run pytest tests/test_ast_regression.py::TestPhase41BindingAwareResolver -v` | AST guard |
| Lint | `uv run ruff check src/ tests/` | Pre-commit |
| Type check | `uv run mypy src/` | Pre-commit |

## Architecture Patterns

### Current Call Graph (broken — Bug AA + V + BB)

```
discover_and_map(hostname="pve")
   └─> handle_discover_and_map (network_handlers.py:10)
        └─> sitemap.discover_and_store (sitemap.py:410)
             └─> ssh_discover_system_with_binding (ssh_tools.py:838)
                  ├─> _scan_registry_for_binding(hostname, username)  # KEYRING REGISTRY ONLY
                  │     └─> list_credentials() / .get("hostname") == hostname  # ← Bug AA: keyring-keyed, sitemap-row-blind
                  └─> ssh_discover_system(hostname, ...)
                       ├─> resolve_ssh_credentials(hostname, ...)  # KEYRING REGISTRY ONLY (no credential_id passed)
                       └─> ssh_connect(creds.hostname, ...)  # ← Bug V: dials creds.hostname, NOT row.connection_ip
                                                                # creds.hostname = input identifier "pve"
                                                                # ↳ requires DNS / /etc/hosts to resolve "pve"

   On failure (timeout / auth / network):
   └─> ssh_connection_wrapper (error_handling.py:229) returns:
        {"status": "error", "connection_ip": "pve", "error": "..."}  # ← Bug BB: NO `hostname` field
        └─> sitemap.parse_discovery_output (sitemap.py:76)
             ├─> hostname = data.get("hostname", "")  # ← "" (degenerate)
             └─> NetworkDevice(hostname="", connection_ip="pve", ...)
                  └─> database.store_device (database.py:267)
                       └─> Falls back to (hostname="", connection_ip="pve") composite key
                            ↳ Distinct rows per failed identifier, BUT all errors collide on (hostname="", connection_ip="unknown")
                              when JSON parsing itself fails (sitemap.py:143-151) — that's the "zombie row"
```

### Working Reference (drift's pattern — what Bug AA wants to mirror)

```
scan_drift (drift_detection.py:564)
   └─> rows = db_adapter.get_all_devices()
        └─> for row in rows:
             ├─> hostname = row.get("hostname")
             ├─> binding = row.get("ssh_credential_id")     # ← row-bound UUID
             └─> _bulk_universal_core_probes(eligible_rows) (drift_detection.py:455)
                  └─> for row in eligible:
                       └─> _probe_one(row) (drift_detection.py:488)
                            ├─> creds = resolve_ssh_credentials(hostname, credential_id=binding)
                            │     ↳ Tier-0 UUID short-circuit, sitemap-row-bound
                            └─> ssh_connect(creds.hostname, ...)  # STILL dials creds.hostname
                                                                   # ← Bug V also affects drift here

For Proxmox path (drift_detection.py:759-763):
   └─> client = await get_proxmox_client(host=hostname, session=session, credential_id=binding)
        ↳ Bug V: passes row.hostname, not row.connection_ip
```

**The asymmetry**: drift uses `credential_id` from the row but still dials `row.hostname` (Bug V also affects drift). `discover_and_map` doesn't even use `credential_id` from the row (Bug AA).

### Target Call Graph (post-fix)

```
discover_and_map(hostname="pve")
   └─> sitemap.discover_and_store
        └─> resolve_ssh_for_sitemap_row("pve")     # NEW helper in ssh_tools.py
             ├─> rows = db.find_devices_by_hostname_or_ip("pve")
             ├─> if exactly one row: use row.ssh_credential_id + row.connection_ip
             ├─> if zero rows: fall back to current behavior (Tier-1/2 keyring scan, dial input)
             ├─> if multiple rows: ambiguous — surface a structured error (mirror resolve_ssh_credentials's multi-match shape)
             └─> returns (SSHCredentials, sitemap_row | None)
        └─> ssh_discover_system(creds, dial_target=row.connection_ip or hostname)

   On failure:
   └─> error envelope carries `hostname` field set to the requested identifier
        └─> parse_discovery_output uses input identifier for the hostname
             └─> store_device upserts onto the existing row (looked up by find_devices_by_hostname_or_ip)
                  ↳ NO degenerate (hostname="") row created
```

### Recommended Project Structure (no new files; surgical edits)

```
src/homelab_mcp/
├── ssh_tools.py
│   ├── resolve_ssh_credentials              # existing, unchanged
│   ├── _scan_registry_for_binding           # existing, retained for back-compat
│   ├── ssh_discover_system_with_binding     # existing; refactor to use new helper internally
│   └── resolve_ssh_for_sitemap_row          # NEW — the shared helper Bug AA needs
├── sitemap.py
│   ├── discover_and_store                   # MODIFIED — calls new helper, passes dial_target
│   └── parse_discovery_output               # MODIFIED — uses requested_identifier on error
├── drift_detection.py
│   ├── _bulk_universal_core_probes._probe_one  # MODIFIED — call new helper, dial connection_ip
│   └── scan_drift row loop (line 759)       # MODIFIED — pass row.connection_ip, not row.hostname
├── error_handling.py
│   └── ssh_connection_wrapper               # MODIFIED — error envelopes carry `hostname`
└── database.py                              # NO CHANGES (find_devices_by_hostname_or_ip already exists)

tests/
├── test_sitemap.py                          # NEW tests for Bug AA + BB regression
├── test_drift_detection.py                  # NEW test for Bug V row.connection_ip dial
├── test_ssh_tools.py                        # NEW unit tests for resolve_ssh_for_sitemap_row helper
└── test_ast_regression.py
    └── TestPhase41BindingAwareResolver      # NEW — mirrors TestPhase41_1KeyringHygiene shape
```

### Pattern 1: Shared Resolver Helper (the proposed shape)

```python
# Source: PROPOSED — extract from drift_detection.py:488-497 reference + sitemap row lookup
# Location: src/homelab_mcp/ssh_tools.py (new function near _scan_registry_for_binding)

def resolve_ssh_for_sitemap_row(
    identifier: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> tuple[SSHCredentials, dict[str, Any] | None]:
    """Phase 41 Bug AA + V shared helper — sitemap-row-aware SSH credential resolver.

    Both ``sitemap.discover_and_store`` and ``drift_detection._probe_one`` call
    this so the row-binding contract from Phase 38.1 R3/R6 reaches every SSH
    credential lookup, not just the drift path.

    Resolution order:
      1. Look up sitemap row(s) matching ``identifier`` (hostname OR connection_ip)
         via ``database.find_devices_by_hostname_or_ip``.
      2. Exactly-one match with non-null ``ssh_credential_id`` →
         ``resolve_ssh_credentials(identifier, credential_id=row['ssh_credential_id'])``
         (Tier-0 UUID short-circuit). Returns ``(creds, row)``.
      3. Exactly-one match with null binding → degenerate row; fall back to
         standard ``resolve_ssh_credentials`` (Tier-1/2). Returns ``(creds, row)``.
      4. Zero matches → no sitemap row yet (fresh discovery); standard
         ``resolve_ssh_credentials``. Returns ``(creds, None)``.
      5. Multi-match → ambiguous; raise CredentialNotFoundError with disambiguation
         pointer (mirror resolve_ssh_credentials multi-match shape).

    Args:
        identifier: hostname OR connection_ip the user passed.
        username/password/key_path/port: standard resolver passthrough.

    Returns:
        ``(SSHCredentials, sitemap_row_dict_or_None)`` — the row dict carries
        ``connection_ip`` for the caller to use as the dial target (Bug V).
    """
    from .database import get_database_adapter
    db = get_database_adapter()
    matched_rows = db.find_devices_by_hostname_or_ip(identifier)

    if len(matched_rows) == 0:
        creds = resolve_ssh_credentials(identifier, username, password, key_path, port)
        return creds, None
    if len(matched_rows) >= 2:
        # Disambiguate by status='success' if exactly one is healthy; else surface error
        healthy = [r for r in matched_rows if r.get("status") == "success"]
        if len(healthy) == 1:
            matched_rows = healthy
        else:
            registered = ", ".join(f"{r.get('hostname','?')}@{r.get('connection_ip','?')}" for r in matched_rows)
            raise CredentialNotFoundError(
                f"Multiple sitemap rows matched {identifier!r}: {registered}. "
                "Disambiguate by passing the exact hostname or connection_ip, "
                "or call get_network_sitemap to inspect."
            )

    row = matched_rows[0]
    binding = row.get("ssh_credential_id")
    if binding:
        # Tier-0 UUID short-circuit via row binding
        creds = resolve_ssh_credentials(
            identifier, username, password, key_path, port, credential_id=binding,
        )
    else:
        # Row exists but unbound (legacy / degenerate) — Tier-1/2 keyring scan
        creds = resolve_ssh_credentials(identifier, username, password, key_path, port)
    return creds, row
```

[ASSUMED — proposed by researcher; not yet in codebase. Locked decisions to confirm in discuss-phase: helper name, multi-match disambiguation policy, and whether matched-row signal feeds back into `discover_and_map`'s dial-target choice when the row's `connection_ip` is empty/degenerate.]

### Pattern 2: Failure Path Carries Requested Identifier

```python
# Source: PROPOSED — fix at sitemap.py:138-141 + error_handling.py:248-317
# error_handling.ssh_connection_wrapper additions: include `hostname` in every error envelope

# error_handling.py — every json.dumps({"status": "error", ...}) gains:
"hostname": kwargs.get("hostname", args[0] if args else "unknown"),  # already pulled for connection_ip

# sitemap.py:138-141 — explicit assignment from caller-known identifier:
elif data.get("status") == "error":
    # Phase 41 Bug BB: preserve the requested identifier so the upsert lands
    # on the correct row, not the degenerate (hostname="") zombie.
    if not device.hostname:
        device.hostname = data.get("hostname") or requested_identifier or ""
    device.error_message = data.get("error", "Unknown error")
```

### Pattern 3: Row Upsert by Existing-Row Lookup First

```python
# Source: PROPOSED — fix at sitemap.discover_and_store (sitemap.py:438-448)
# After ssh_discover_system_with_binding returns:

device = sitemap.parse_discovery_output(discovery_result)

# Phase 41 Bug BB: when discovery failed AND we know the requested identifier,
# look up an existing row and reuse its (hostname, connection_ip) so the
# error update lands on the correct row instead of creating a zombie.
if device.status == "error":
    matched = sitemap.db_adapter.find_devices_by_hostname_or_ip(requested_identifier)
    if matched:
        # Reuse the existing row's identity fields; merge error_message in.
        existing = matched[0]
        device.hostname = existing["hostname"]
        device.connection_ip = existing.get("connection_ip", device.connection_ip)
```

### Anti-Patterns to Avoid

- **Hand-rolling a separate "lookup-by-IP" path**: `find_devices_by_hostname_or_ip` already does the OR-match across both columns. Don't write a parallel scanner.
- **Bypassing `resolve_ssh_credentials` Tier-0**: the UUID short-circuit handles all D-11/D-12/D-13 reason-hint logic. The new helper MUST delegate to it, not duplicate the auth_type branching.
- **Caching the matched row across an iteration**: Phase 39 review (WR-06 in `drift_detection.py:730-738`) already paid this cost — variable-leak across `for` iterations. Reset row state per call.
- **Fixing only one of the three bugs**: AA, V, BB share a root cause. A fix that closes AA but leaves drift dialing `row.hostname` (Bug V on drift's side) leaves the milestone half-shipped.
- **Adding a new database lookup adapter method**: `find_devices_by_hostname_or_ip` is sufficient. Don't expand the adapter surface.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sitemap row lookup by identifier | Custom SQL or row scan | `database.find_devices_by_hostname_or_ip` (`database.py:440`) | Already exists, SQLite + Postgres parity |
| UUID-keyed credential resolution | Direct keyring `get_credential` calls | `resolve_ssh_credentials(..., credential_id=...)` (Tier-0 short-circuit) | Phase 38.1 D-13/D-14 logic + reason-hint mapping live here |
| Multi-match disambiguation | Custom error class | `CredentialNotFoundError` with disambiguation message (`ssh_tools.py:85-91` pattern) | Existing pattern; tests already assert this shape |
| AST guard for shared-helper invariant | New AST visitor framework | `ast.walk` + allowlist set (mirror `TestPhase41_1KeyringHygiene` at `tests/test_ast_regression.py:1072-1196`) | Pattern is well-established in this repo (5 prior phases use it) |
| SSH connection error envelope | New error wrapper | Extend `ssh_connection_wrapper` (`error_handling.py:229-317`) — add `hostname` field | Already produces error envelopes; just add the missing field |
| Degenerate-row routing | Custom routing logic | `find_devices_by_hostname_or_ip` + reuse existing row's identity | Existing primitive; Phase 35 D-01a already established the (hostname, connection_ip) composite-key fallback |

**Key insight:** Every primitive needed for the fix already exists. This is a wiring phase, not a building phase.

## Runtime State Inventory

> Phase 41 is a refactor + bug fix; verifying runtime state in case behavior change has out-of-tree impact.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Sitemap rows: existing degenerate `(hostname="", connection_ip=...)` rows from prior failed discoveries are in `~/.homelab_mcp/homelab.db`. Phase 41 fix changes failure-path persistence behavior going forward but does NOT auto-migrate existing zombie rows. | Document in plan: existing zombies remain visible until user runs `purge_failed_discoveries`. No auto-migration (homelab single-user scope; mirrors v1.6 / v1.7 migration policy). |
| Live service config | None — Proxmox API tokens and SSH credentials live in keyring + JSON registry; not in external services. | None. |
| OS-registered state | None — no Windows tasks, systemd units, or pm2 processes embed the changed code paths. | None. |
| Secrets/env vars | `PROXMOX_HOST` / `PROXMOX_USER` / `PROXMOX_PASSWORD` / `PROXMOX_API_TOKEN` env vars still respected by `get_proxmox_client` (Phase 38.1 D-10 explicit-auth bypass at `proxmox_api.py:494-516`). Bug V fix must NOT change this — env-var-only callers still need to work. | Verify in tests: an env-var-only Proxmox call (no sitemap row) still resolves correctly. |
| Build artifacts / installed packages | None — pure Python source edits, no compiled artifacts. | None. |

**Nothing found in category** for live service config / OS state / build artifacts — verified via grep + file inspection.

## Common Pitfalls

### Pitfall 1: `_resolve_ssh_credentials_with_binding` is dead code (don't call it)
**What goes wrong:** Reading the source, the obvious-looking helper is `_resolve_ssh_credentials_with_binding` at `ssh_tools.py:314`. It returns `(creds, used_credential_id)` — looks ideal. But it's marked DEAD CODE (banner at line 306).
**Why it happens:** Phase 38.1 R3 originally proposed this helper, then implementation switched to `_scan_registry_for_binding` + `ssh_discover_system_with_binding` for separation-of-concerns. The dead function was retained for plan-acceptance grep (Phase 38.1 WR-01).
**How to avoid:** New helper is a fresh symbol (`resolve_ssh_for_sitemap_row`). Don't repurpose the dead one. AST guard explicitly bans new direct callers of `_resolve_ssh_credentials_with_binding` (status quo: zero callers).
**Warning signs:** A plan that says "rename the dead helper" — that's the wrong move; the dead helper does registry scanning, not sitemap row lookup.

### Pitfall 2: Bug V also affects drift's row loop
**What goes wrong:** Treating Bug V as discover-only misses that `drift_detection.py:759-763` and `drift_detection.py:498-503` (the SSH probe in `_probe_one`) BOTH dial `hostname` (= `row.hostname`) instead of `row.connection_ip`. The bug exists symmetrically.
**Why it happens:** Drift was wired to iterate `rows`, where `hostname = row.get("hostname")` — the natural-key field. The `connection_ip` field is read only for the response payload (`drift_detection.py:748, 769, 781, ...`), never for dialing.
**How to avoid:** Fix both call sites in the same phase. The shared helper returns the row; both sitemap and drift use `row.connection_ip` (when truthy and not "unknown").
**Warning signs:** A plan that touches only `sitemap.py` for Bug V leaves drift's IP-vs-hostname dial unchanged — half-fix.

### Pitfall 3: Failed-JSON-decode path pre-dates Bug BB awareness
**What goes wrong:** `sitemap.parse_discovery_output` at `sitemap.py:143-151` catches `JSONDecodeError` and produces `NetworkDevice(hostname="unknown", connection_ip="unknown", ...)`. ALL such failures collapse onto the SAME `(hostname="unknown", connection_ip="unknown")` row, which is the canonical zombie.
**Why it happens:** When `ssh_connection_wrapper` returns a sentinel non-JSON-string (rare; only on `Exception` types it fails to serialize), or when a future caller swallows the JSON contract, this path triggers.
**How to avoid:** Pass `requested_identifier` into `parse_discovery_output(..., requested_identifier=...)` and use it for both `hostname` and `connection_ip` on the JSON-decode-error path. Never literal `"unknown"`.
**Warning signs:** Tests that mock `discover_and_store` with malformed JSON and expect a row keyed on `"unknown"` — those expectations need updating.

### Pitfall 4: `connection_ip` on a fresh-discovery row equals the input identifier
**What goes wrong:** When `discover_and_map hostname=pve` succeeds, `ssh_discover_system` writes `{"hostname": <actual_remote_hostname>, "connection_ip": "pve", ...}` (`ssh_tools.py:802-804`). So `row.connection_ip = "pve"` after first discovery. The Bug V "use row.connection_ip" rule is a no-op on first discovery — it only matters once an actual IP-shaped value lands in `connection_ip`.
**Why it happens:** `connection_ip` is misnamed; it's actually "the identifier the caller used to dial." Real-IP-shaped values land there only when the caller passed an IP.
**How to avoid:** The fix is still correct — using `row.connection_ip` over `row.hostname` is what the user wants. But add a guard: if `row.connection_ip` is empty/None/equals the input identifier, fall back to the input identifier (no-op). The win comes on the second-and-later discovery against the same row.
**Warning signs:** A test that asserts "first discovery dials a different value than input" — that's not the contract; the contract is "subsequent discoveries dial the row's stored connection_ip even when the input is the human-friendly hostname."

### Pitfall 5: Function-rename gotcha (Phase 38.1 RESEARCH Pitfall 1 cited)
**What goes wrong:** AST guards keyed on function names break silently when the function is renamed.
**Why it happens:** Phase 38.1 D-15 guard is keyed on `scan_drift` (not `scan_infrastructure_drift` — that's the MCP tool name). The repo has two function-name layers: tool-handler functions (e.g., `handle_discover_and_map`) and implementation functions (e.g., `discover_and_store`). Mixing them up makes the guard silently miss.
**How to avoid:** Phase 41 AST guard targets `discover_and_store` (sitemap.py) and `_probe_one` (drift_detection.py inside `_bulk_universal_core_probes`). Use ast.walk + nested function discovery (mirror Phase 39.1's pattern at `tests/test_ast_regression.py:853+`).
**Warning signs:** A guard that asserts `discover_and_map` exists somewhere — that's the MCP tool name, not the implementation. Use the implementation symbol.

### Pitfall 6: Multi-match disambiguation policy is a user-visible decision
**What goes wrong:** `find_devices_by_hostname_or_ip("pve")` could match (a) one row with `hostname="pve"`, (b) one row with `connection_ip="pve"`, OR (c) both, OR (d) neither. The current SQL is `WHERE hostname = ? OR connection_ip = ?` — both rows return.
**Why it happens:** Sitemap allows the same identifier to land in two slots across two rows (a pre-Phase-35 history artifact, or a deliberate IP-vs-hostname dual-record).
**How to avoid:** Phase 41 must lock a multi-match disambiguation policy. Recommended: prefer status='success' rows; if still ambiguous, raise `CredentialNotFoundError` with a list of candidates and a pointer to `get_network_sitemap`. Discuss-phase decision.
**Warning signs:** A plan that silently picks `matched[0]` without ordering — non-deterministic test failures depending on row insertion order.

## Code Examples

### Verified pattern: drift's row-bound credential resolution (the reference Bug AA wants to mirror)

```python
# Source: src/homelab_mcp/drift_detection.py:488-524 (verified)
async def _probe_one(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    hostname = row.get("hostname", "")
    binding = row.get("ssh_credential_id")
    if binding is None:
        return (hostname, {"_error": "no_ssh_credential_id"})
    async with semaphore:
        try:
            creds = resolve_ssh_credentials(hostname, credential_id=binding)
            async with await ssh_connect(
                hostname=creds.hostname,  # ← Bug V: should be row.connection_ip
                username=creds.username,
                port=creds.port,
                password=creds.password,
                key_path=creds.key_path,
            ) as conn:
                ...
```

### Verified pattern: AST guard with allowlist (the reference for the new guard)

```python
# Source: tests/test_ast_regression.py:1154-1195 (verified)
def test_no_unprotected_credential_writes_in_tests(self) -> None:
    tests_root = Path(__file__).parent
    repo_root = tests_root.parent
    violations: list[str] = []
    for py_file in sorted(tests_root.rglob("*.py")):
        rel = py_file.relative_to(repo_root).as_posix()
        if rel in self._ALLOWLIST:
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in self._GUARDED_SYMBOLS
            ):
                violations.append(f"{rel}:{node.lineno} — {node.func.id}(...) in non-allowlisted file")
    assert not violations, ("Phase 41.1 SC-2: ..." + "\n  ".join(violations))
```

### Verified pattern: function-scoped AST guard (Phase 39.1)

```python
# Source: tests/test_ast_regression.py:853+ (verified — TestPhase39_1NoSkipInDriftEnum)
# Walk drift_detection.py, find _enum_one, assert every get_proxmox_client call
# inside it has credential_id= as a keyword argument.
target = next(
    (n for n in ast.walk(tree)
     if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "_enum_one"),
    None,
)
violations = [
    n.lineno for n in ast.walk(target)
    if isinstance(n, ast.Call)
    and isinstance(n.func, ast.Name) and n.func.id == "get_proxmox_client"
    and "credential_id" not in {kw.arg for kw in n.keywords}
]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct keyring lookup by hostname | Tier-0 UUID short-circuit + row-bound `ssh_credential_id` | Phase 38.1 (2026-04-27) | Drift uses it; discover_and_map doesn't (Bug AA) |
| Drop-and-recreate `drift_baselines` table | Sitemap as single source of truth | Phase 36 (2026-04-25) | Sitemap row IS the baseline |
| `discover_and_map` keyring-only credential resolution | Phase 41 row-binding-aware resolver (this phase) | Phase 41 (this phase) | Closes Bug AA |

**Deprecated/outdated:**
- `_resolve_ssh_credentials_with_binding` at `ssh_tools.py:314` — DEAD CODE per Phase 38.1 WR-01. Do not call. Phase 41 may delete this since the new helper supersedes it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Multi-match disambiguation policy: prefer status='success', raise CredentialNotFoundError on ambiguity | Pattern 1 + Pitfall 6 | Wrong policy could mask legitimate multi-row scenarios; user-visible. Discuss-phase decision. |
| A2 | New helper named `resolve_ssh_for_sitemap_row` | Pattern 1 | Naming-only; no architectural impact. Discuss-phase confirm. |
| A3 | `_resolve_ssh_credentials_with_binding` (dead code) can be deleted in Phase 41 | State of the Art | If a downstream test still grep-pins the symbol name, deleting breaks the test. Verify by greppingbefore delete. |
| A4 | Existing zombie rows (created pre-Phase-41) are NOT auto-migrated | Runtime State Inventory | Mirrors Phase 36 / 38.1 migration policy; user must run `purge_failed_discoveries`. Should be confirmed in discuss-phase. |
| A5 | The dial-target fallback (when `row.connection_ip` is empty) uses the input identifier | Pitfall 4 | Edge case. If wrong, first-time discovery against an existing degenerate row could regress. |
| A6 | `requested_identifier` parameter threaded through `parse_discovery_output` is acceptable signature change | Pattern 2 | Minor signature change; tests calling `parse_discovery_output` directly need updates. |
| A7 | Bug V fix applies to BOTH `sitemap.discover_and_store` AND `drift_detection`'s probe + Proxmox-client call sites | Pitfall 2 | If the discuss-phase scopes Bug V to discover-only, drift remains broken. Confirm scope. |

**These assumptions are explicit hypotheses for discuss-phase to confirm or revise.** None are blockers; all have safe defaults.

## Open Questions (RESOLVED)

1. **Multi-match disambiguation policy** — see Assumption A1.
   - **RESOLVED:** Prefer rows with status='success'; if exactly one healthy row remains, use it. Otherwise raise CredentialNotFoundError with a disambiguation pointer to get_network_sitemap. Encoded in Plan 02 (resolve_ssh_for_sitemap_row body) and Plan 02 unit test test_helper_raises_on_ambiguous_match + test_helper_disambiguates_multi_match_via_status_success.
   - What we know: `find_devices_by_hostname_or_ip` returns all matches; multi-match is a real possibility (e.g., hostname collision across IPs).
   - What's unclear: whether to pick the first healthy row, raise an error, or let the caller decide.
   - Recommendation: lock as discuss-phase question; default to "prefer status='success', else raise."

2. **Should drift's Bug V fix happen in this phase or a follow-up?**
   - **RESOLVED:** In scope for this phase. Both call sites (sitemap.discover_and_store and drift_detection._probe_one + Proxmox-client loop) use the shared helper. Encoded in Plans 03 + 04; AST guard test_shared_helper_used_by_both_call_sites enforces.
   - What we know: drift symmetrically suffers from Bug V (`drift_detection.py:759, 498`).
   - What's unclear: scope — UAT bug V was filed against `discover_and_map`, so technically drift's version is a separate bug.
   - Recommendation: include both in this phase. They share the helper, and the AST guard naturally covers both.

3. **Backwards compat for `register_server` and `bulk_discover_and_map`** —
   - **RESOLVED:** bulk_discover_and_store loops discover_and_store and inherits the fix transparently (no separate plan needed). register_server scope deferred — Phase 41 does not modify it; a follow-up phase covers it if UAT surfaces a need. Documented in Plan 03 SUMMARY scope notes.
   - What we know: `register_server` (`ssh_tools.py:997+`) and `bulk_discover_and_store` also resolve SSH credentials.
   - What's unclear: whether they should ALSO use the new helper, or stay on `resolve_ssh_credentials` direct.
   - Recommendation: scope `register_server` IN (it benefits from row-binding too) and `bulk_discover_and_store` IN (it loops `discover_and_store`, inherits the fix). Discuss-phase confirm.

4. **Telemetry / logging on the new path** —
   - **RESOLVED:** DEBUG-level logs at the three resolution outcomes (zero rows / single row + binding / single row no binding). No log on multi-match raise — exception message is the signal. Encoded in Plan 02 task 1 action under "DEBUG logging".
   - What we know: Phase 38.1 D-12 added `reason_hint` on `CredentialNotFoundError`; drift uses it for bucket routing.
   - What's unclear: whether the helper's row-found / row-not-found / multi-match outcomes need a structured log line.
   - Recommendation: log at DEBUG ("resolved via sitemap row" / "no row matched, fell back to keyring scan") for observability; no error-path log unless multi-match.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All code paths | ✓ | 3.12.13 | — |
| `uv` | Test runner | ✓ | (verified earlier in session) | `python -m pytest` |
| `asyncssh` | SSH tests | ✓ | >=2.14.0 | — |
| `aiohttp` | Drift tests | ✓ | >=3.9.0 | — |
| `pytest` | Test runner | ✓ | >=8.3.5 | — |
| `pytest-asyncio` | Async tests | ✓ | >=0.23.0 | — |
| `pytest-mock` | Mock fixtures | ✓ | >=3.14.0 | — |

**No missing dependencies.** All work runs against the existing toolchain.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 + pytest-asyncio 0.23.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_sitemap.py tests/test_ssh_tools.py tests/test_ast_regression.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| Bug AA | `discover_and_map hostname=pve` resolves SSH creds via row-binding helper when sitemap row exists | functional / regression | `uv run pytest tests/test_sitemap.py::test_discover_and_map_uses_row_binding_when_row_exists -x` | ❌ Wave 0 |
| Bug AA | `discover_and_store` and `_probe_one` both call `resolve_ssh_for_sitemap_row` | AST guard | `uv run pytest tests/test_ast_regression.py::TestPhase41BindingAwareResolver::test_shared_helper_used_by_both_call_sites -x` | ❌ Wave 0 |
| Bug V | When sitemap row's `connection_ip` is set, dial uses it (not `row.hostname`) for SSH | unit + functional | `uv run pytest tests/test_ssh_tools.py::test_dial_target_uses_row_connection_ip -x` | ❌ Wave 0 |
| Bug V | Drift's Proxmox client uses `row.connection_ip` for the `host=` arg | unit | `uv run pytest tests/test_drift_detection.py::test_drift_dials_connection_ip_not_hostname -x` | ❌ Wave 0 |
| Bug BB | Failed `discover_and_map` writes error to row matching the requested identifier (not zombie) | functional / regression | `uv run pytest tests/test_sitemap.py::test_failed_discover_writes_to_requested_identifier_row -x` | ❌ Wave 0 |
| Bug BB | Empty-hostname zombie row never collects errors from named hosts | functional / regression | `uv run pytest tests/test_sitemap.py::test_failed_discover_does_not_collapse_to_empty_hostname -x` | ❌ Wave 0 |
| Helper edge: zero matches | `resolve_ssh_for_sitemap_row("never-seen")` falls back to keyring scan | unit | `uv run pytest tests/test_ssh_tools.py::test_helper_falls_back_when_no_row_matches -x` | ❌ Wave 0 |
| Helper edge: multi-match | `resolve_ssh_for_sitemap_row` raises CredentialNotFoundError on ambiguity | unit | `uv run pytest tests/test_ssh_tools.py::test_helper_raises_on_ambiguous_match -x` | ❌ Wave 0 |
| Helper edge: row exists but binding null | Falls back to Tier-1/2 keyring scan but still returns the row | unit | `uv run pytest tests/test_ssh_tools.py::test_helper_handles_unbound_row -x` | ❌ Wave 0 |
| Helper edge: malformed connection_ip | Helper returns row even when `connection_ip` is empty/None; caller falls back to identifier | unit | `uv run pytest tests/test_ssh_tools.py::test_helper_handles_empty_connection_ip -x` | ❌ Wave 0 |
| Error envelope | `ssh_connection_wrapper` error envelopes carry `hostname` field | unit | `uv run pytest tests/test_ssh_tools.py::test_error_envelope_carries_hostname -x` | ❌ Wave 0 |
| AST guard | New AST guard class blocks future direct `resolve_ssh_credentials` calls in `sitemap.py` and `drift_detection.py` outside allowlist | AST guard | `uv run pytest tests/test_ast_regression.py::TestPhase41BindingAwareResolver::test_no_unguarded_resolve_ssh_credentials_in_call_chain -x` | ❌ Wave 0 |

### Manual UAT Scenarios (deferred to milestone close per project memory)

These require live agents and a reachable Proxmox host; document in `41-HUMAN-UAT.md` and batch at milestone close (per `feedback_manual_uat_timing.md`):

1. **Bug AA closure**: With `pve` registered in keyring under IP `192.168.10.20` and a sitemap row created via `discover_and_map hostname=192.168.10.20`, run `discover_and_map hostname=pve`. Expect: success (no "credentials not found" error). Today: fails because keyring is keyed on IP.
2. **Bug V closure**: Without `/etc/hosts` entry for `pve`, after a successful `discover_and_map hostname=192.168.10.20` (which registers `connection_ip=192.168.10.20`), run `scan_infrastructure_drift node=pve`. Expect: success (drift dials `connection_ip` not the unresolvable hostname).
3. **Bug BB closure**: Pick a hostname not yet in sitemap (`fakehost.local`); call `discover_and_map hostname=fakehost.local`. Expect: a single new row with `hostname="fakehost.local"`, `status="error"`. Verify `get_network_sitemap` shows ONE row with the requested name; the empty-hostname zombie row has not gained another error.
4. **Coexistence**: After Phase 41, run a fresh `credentials add --type proxmox <new-host> root@pam!tok <token>` + `discover_and_map <new-host>`. Verify the upsert wires `ssh_credential_id` and the row's `connection_ip` matches the input. Verify a follow-up `scan_infrastructure_drift` reports the host in `probed_ok`.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_sitemap.py tests/test_ssh_tools.py tests/test_drift_detection.py tests/test_ast_regression.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"` (full unit suite)
- **Phase gate:** Full unit suite green + AST guard green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ssh_tools.py` — verify file exists; if not, add it. Will house unit tests for `resolve_ssh_for_sitemap_row`.
- [ ] `tests/test_sitemap.py` — already exists (`tests/test_sitemap.py`); add new test functions for Bug AA + BB regressions.
- [ ] `tests/test_drift_detection.py` — verify file exists; if not, add it. Will house Bug V drift-side test.
- [ ] `tests/test_ast_regression.py` — already exists; add new `TestPhase41BindingAwareResolver` class.
- [ ] No framework install needed (pytest, pytest-asyncio, pytest-mock all in pyproject.toml).
- [ ] No new fixtures needed in `tests/conftest.py`; existing `freeze_now` and mock fixtures suffice.

## Project Constraints (from CLAUDE.md)

- **Type hints required**: all new functions in `resolve_ssh_for_sitemap_row` and tests must have full type annotations.
- **Async-first**: SSH and DB I/O are async; helper is async-compatible (the DB lookup is sync via existing adapter, which is fine).
- **Error handling**: use `error_handling.py` patterns — extend `ssh_connection_wrapper` rather than write a new wrapper.
- **Tool definitions**: no NEW MCP tools — this is a behavior fix to existing `discover_and_map` / `bulk_discover_and_map` / `scan_infrastructure_drift`.
- **TestSprite Rules**: do NOT run TestSprite. Do NOT modify `testsprite_tests/`. Phase 41 is server-code-only.
- **uv preferred**: all test commands use `uv run pytest`.
- **Pre-commit hooks**: ruff + mypy + bandit must pass before commit.
- **Branch**: stay on the milestone branch (`credential-cleanup` or whichever the v1.7 milestone branch is) — don't create a per-phase branch (Phase 41 is mid-milestone, per CLAUDE.md "Inserted phases stay on the milestone branch").

## Sources

### Primary (HIGH confidence) — codebase verified
- `src/homelab_mcp/ssh_tools.py:95-303` — `resolve_ssh_credentials` Tier-0/1/2 logic (Phase 38.1 D-11/12/13/14)
- `src/homelab_mcp/ssh_tools.py:314-400` — `_resolve_ssh_credentials_with_binding` (DEAD CODE; reference only)
- `src/homelab_mcp/ssh_tools.py:528-545` — `ssh_discover_system` resolver call site (today)
- `src/homelab_mcp/ssh_tools.py:802-809` — discovery payload shape (`hostname`, `connection_ip`)
- `src/homelab_mcp/ssh_tools.py:812-836` — `_scan_registry_for_binding` (current Bug-AA-affected code path)
- `src/homelab_mcp/ssh_tools.py:838-874` — `ssh_discover_system_with_binding`
- `src/homelab_mcp/sitemap.py:76-151` — `parse_discovery_output` (Bug BB site)
- `src/homelab_mcp/sitemap.py:410-463` — `discover_and_store` (Bug AA + BB site)
- `src/homelab_mcp/database.py:267-383` — SQLite `store_device` upsert (Phase 35 D-01a degenerate-row fallback)
- `src/homelab_mcp/database.py:440-452` — `find_devices_by_hostname_or_ip` (the lookup primitive)
- `src/homelab_mcp/drift_detection.py:455-561` — `_bulk_universal_core_probes` and `_probe_one` (Bug AA reference impl)
- `src/homelab_mcp/drift_detection.py:564-1000` — `scan_drift` row loop (Bug V site at lines 759-763)
- `src/homelab_mcp/proxmox_api.py:443-543` — `get_proxmox_client` (env-var bypass at lines 494-516; Bug V's Proxmox-side fix point)
- `src/homelab_mcp/error_handling.py:229-317` — `ssh_connection_wrapper` (Bug BB envelope shape)
- `tests/test_ast_regression.py:758-845` — `TestPhase381CredBinding` (D-15/D-17 AST guard pattern)
- `tests/test_ast_regression.py:853-989` — `TestPhase39_1NoSkipInDriftEnum` (function-scoped AST guard pattern)
- `tests/test_ast_regression.py:1072-1196` — `TestPhase41_1KeyringHygiene` (allowlist + ast.walk pattern)
- `tests/conftest.py:1-80` — existing test fixtures (freeze_now, mock probe responses)
- `pyproject.toml` — verified asyncssh>=2.14.0, aiohttp>=3.9.0, pytest>=8.3.5, pytest-asyncio>=0.23.0, pytest-mock>=3.14.0

### Secondary (MEDIUM confidence) — planning docs
- `.planning/STATE.md` — milestone v1.7 progress and phase ordering constraints
- `.planning/ROADMAP.md` — Phase 41 declaration with Success Criteria 1-4
- `.planning/REQUIREMENTS.md` — coverage map (Phase 41 closes UAT bugs AA, BB, V; no new REQ-IDs)
- `.planning/phases/41.1-test-isolation-keyring-hygiene/41.1-RESEARCH.md` — sibling AST guard precedent

### Tertiary (LOW confidence) — none used
- No external documentation lookups required; this is a closed-system refactor against well-understood internal APIs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in `pyproject.toml`, no new deps.
- Architecture: HIGH — call graph verified by reading 8 source files end-to-end; bug surfaces traced to specific line ranges.
- Pitfalls: HIGH — 5 of 6 pitfalls are codebase-verified (read the source); Pitfall 4 (connection_ip semantics) is reasoned-from-source-but-not-runtime-verified, marked HIGH because the data flow is mechanical.
- AST guard pattern: HIGH — 5 prior phases (33.1, 35, 36, 38.1, 39.1, 41.1) have successfully shipped this pattern; mechanics are well understood.
- Multi-match policy + helper naming: MEDIUM — proposed by researcher, requires discuss-phase confirmation.

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days; codebase is stable, no in-flight refactors of the affected files at time of research)

## RESEARCH COMPLETE
