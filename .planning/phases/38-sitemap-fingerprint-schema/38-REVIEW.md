---
phase: 38-sitemap-fingerprint-schema
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - docs/tool-reference.md
  - src/homelab_mcp/database.py
  - src/homelab_mcp/migration.py
  - src/homelab_mcp/prompt_registry.py
  - src/homelab_mcp/server.py
  - src/homelab_mcp/sitemap.py
  - src/homelab_mcp/ssh_tools.py
  - src/homelab_mcp/tool_annotations.py
  - src/homelab_mcp/tool_handlers/__init__.py
  - src/homelab_mcp/tool_handlers/network_handlers.py
  - src/homelab_mcp/tool_schemas/network_tools_schema.py
  - src/homelab_mcp/tool_schemas/ssh_tools_schema.py
  - tests/integration/test_sitemap_integration.py
  - tests/test_database.py
  - tests/test_mcp_prompts.py
  - tests/test_mcp_resources.py
  - tests/test_sitemap.py
  - tests/test_ssh_tools.py
  - tests/test_tools.py
findings:
  critical: 0
  warning: 4
  info: 6
  total: 10
status: issues_found
---

# Phase 38: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 38 introduces a per-host capability fingerprint substrate (kernel/OS/package digest +
freeform `capabilities` sub-dict), a `merge_fingerprint` Python helper for SQLite/Postgres
parity, two new MCP tools (`update_device_fingerprint` + `_preview`), and a
`configure_host_fingerprint` MCP prompt. Implementation broadly tracks RESEARCH.md and
the phase's Pitfall mitigations (especially Pitfall 1 locale pinning and Pitfall 4
Python-side merge for adapter parity).

The four focus areas requested by the orchestrator each work as advertised, but several
defects and consistency gaps deserve attention before phase sign-off:

- The `dpkg-fingerprint` partial-flag enrollment is correct, but the rest of the new
  fingerprint probes silently lose data on transient `_run_with_timeout` failure without
  enrolling those probes in `timed_out_commands` — leaving the response without a
  `partial: true` marker. (WR-01)
- `_READ_ONLY_TOOLS` lists `list_keyring_credentials` twice, suggesting an in-progress
  rebase mistake. Harmless today (set-like dict overwrite) but a correctness liability
  if the entries ever diverge. (WR-02)
- `tool-reference.md` claims Phase 38 added new tools but is missing a docs entry for
  the long-standing `connect_to_device` MCP prompt — unrelated to Phase 38's work but
  surfaced because the same docs file was edited. (IN-04)
- The `configure_host_fingerprint` prompt body uses contraction punctuation (`I'd`,
  `here are`) that is technically valid but inconsistent with the more declarative style
  of the other workflow prompts; minor stylistic note. (IN-05)
- Several test mock fixtures hardcode the parameter list of internal helpers
  (`_run_with_timeout`); if the helper signature drifts, tests fail with cryptic mock
  errors rather than the underlying type mismatch. (IN-06)

No critical security issues, injection vulnerabilities, or correctness defects were
found in the new fingerprint code path. The merge semantics, locale pinning, and
adapter parity all match RESEARCH.md's recommendations.

## Warnings

### WR-01: Per-probe non-zero exit-status branches do not enroll in `timed_out_commands`

**File:** `src/homelab_mcp/ssh_tools.py:404-433`
**Issue:** The new fingerprint probes (`uname -s`, `uname -r`, `cat /etc/os-release`)
silently drop their result when the remote command fails (`exit_status != 0`) — they
only consult `result and result.exit_status == 0 and result.stdout` to populate the
field, with no `else` branch to enroll the probe in `timed_out_commands`. Compare with
the `dpkg-fingerprint` branch immediately below at lines 451-459 which DOES enroll on
non-zero exit. The result is an asymmetric contract: a host where `dpkg` is missing
returns `partial: true`, but a host where `/etc/os-release` is unreadable (e.g., a
locked-down minimal image, or chroot) returns NO partial marker even though the
fingerprint is incomplete. Phase 39's drift detector reading this will treat "kernel
probe failed silently" the same as "kernel field genuinely empty" — false negatives on
drift.

The same pattern exists for the legacy probes (cpuinfo, free, df, lsusb, lspci, lsblk),
so this is arguably pre-existing behavior. But Phase 38 added three new probes to the
list and the comment at lines 386-401 explicitly asserts "the existing partial:True
flag fires automatically because we explicitly append to timed_out_commands when dpkg
returns a non-zero exit status" — which is true for dpkg but not for the three sibling
fingerprint probes added in the same block.

**Fix:** Add explicit `elif <result> is not None and <result>.exit_status != 0:`
branches that enroll the cmd_name in `timed_out_commands`. Mirror the dpkg-fingerprint
pattern exactly (lines 451-459) for the three new fingerprint probes:

```python
uname_s_result = await _run_with_timeout(conn, "uname -s", cmd_name="uname-s", timed_out=timed_out_commands)
if uname_s_result and uname_s_result.exit_status == 0 and uname_s_result.stdout:
    fingerprint_info["kernel_name"] = cast(str, uname_s_result.stdout).strip()
elif uname_s_result is not None and uname_s_result.exit_status != 0:
    if "uname-s" not in timed_out_commands:
        timed_out_commands.append("uname-s")
# (repeat for uname-r and os-release-full)
```

If the per-probe `partial` enrollment is intentionally limited to dpkg (cost/value
trade-off: only dpkg failure is a known-distro-specific signal), that intent should be
written into the comment at line 386 instead of the current claim that all three new
probes are equivalently partial-aware.

### WR-02: `list_keyring_credentials` listed twice in `_READ_ONLY_TOOLS`

**File:** `src/homelab_mcp/tool_annotations.py:37,46`
**Issue:** The `_READ_ONLY_TOOLS` list contains `"list_keyring_credentials"` at both
line 37 and line 46. This is harmless at runtime (the for-loop at line 193 just sets
the same key in `TOOL_ANNOTATIONS` twice with the same value), but the duplication
indicates either a rebase artifact or a copy-paste mistake. If anyone ever diverges the
two entries (e.g., adds a third state to one annotation set), only the second one wins
silently — a sneaky regression vector.

This is unrelated to Phase 38's diff but is in scope for review since
`tool_annotations.py` was edited this phase.

**Fix:** Delete the duplicate entry. Suggested keep is line 37 (alphabetical neighborhood
of `list_registered_servers`); the line 46 entry sits between `validate_infrastructure_changes`
and the new Phase 38 `decommission_device_preview` and looks like the rebase remnant.

```python
# Delete line 46:
    "list_keyring_credentials",
```

### WR-03: `update_device_fingerprint_preview` does not return `last_seen` parity with the persistent path

**File:** `src/homelab_mcp/tool_handlers/network_handlers.py:198-206`
**Issue:** The preview wrapper computes the merge result and returns
`{"status": "success", "hostname": ..., "fingerprint": merged, "preview": true}`. The
non-preview path at lines 130-138 returns the same shape minus `preview`. But the
adapter's `update_device_fingerprint` method (database.py:316-348 SQLite, lines 723-762
Postgres) silently bumps `last_seen` and `updated_at` on persist, which the preview does
NOT report. An agent comparing the preview shape to the persisted shape sees no
`last_seen` change in the preview — but the moment they call the real tool, the row's
`last_seen` is overwritten with `datetime.now().isoformat()` (an unrelated side effect
on a dict-merge call).

Two possible defects:
1. The preview is misleading by omission — agents won't know `last_seen` is mutated.
2. The persist path mutates `last_seen` at all — `update_device_fingerprint` is not a
   "discovery", and bumping `last_seen` on a fingerprint merge confuses
   `analyze_network_topology` (which uses `last_seen` indirectly via the row order in
   `ORDER BY hostname, connection_ip` queries).

The plan documents `update_device_fingerprint` as `[Idempotent]` (annotation
`idempotentHint=True`), but identical inputs produce different `last_seen` outputs on
each call — strictly the merge result is idempotent but the row state is not. Worth a
sanity check before Phase 39 builds drift logic on top of `last_seen`.

**Fix:** Decide which side wins. If the `last_seen` bump is wanted, add a hint or
metadata field to the preview output flagging that fact. If it's not wanted, drop the
`last_seen = ?` clause from the SQL UPDATE statements at database.py:344 and database.py:758
— `updated_at` already covers "this row was touched"; `last_seen` should mean "we last
heard from the device".

```sql
-- SQLite (database.py:344): drop the last_seen update, keep updated_at
UPDATE devices SET fingerprint = ?, updated_at = ? WHERE hostname = ?
-- Postgres (database.py:758): same
UPDATE devices SET system_info = %s, updated_at = NOW() WHERE hostname = %s
```

### WR-04: Postgres `update_device_fingerprint` writes back the entire `system_info` blob

**File:** `src/homelab_mcp/database.py:723-762`
**Issue:** The Postgres adapter's `update_device_fingerprint` reads the full
`system_info` JSONB column, mutates only the `fingerprint` sub-key in Python, and writes
back the entire blob via `json.dumps(system_info)` (line 759). If a concurrent
`store_device` call lands between the SELECT (line 739-742) and the UPDATE (line
757-760), the second writer wins and the first writer's mutations to other sub-keys of
`system_info` (cpu, memory, disk, network, etc.) are silently lost. There's no row-level
lock (no `SELECT ... FOR UPDATE`), no autocommit, no transaction guard.

In the homelab's typical "single human + Claude" usage, race windows are small. But a
realistic scenario that triggers this: agent runs `discover_and_map` in one MCP session
(fills `system_info.cpu` etc.), and in parallel a different MCP client runs
`update_device_fingerprint(capabilities={...})` based on a stale view. The fingerprint
write blows away the discovery refresh.

The SQLite path (lines 316-348) has the same theoretical race window but is much less
exposed because SQLite serializes writers at the connection level.

**Fix:** Two paths, depending on how serious you take this:
1. (Lightweight) Wrap the SELECT + UPDATE in an explicit transaction:
```python
cursor.execute("BEGIN")
cursor.execute("SELECT system_info FROM devices WHERE hostname = %s FOR UPDATE", (hostname,))
# ... merge ...
cursor.execute("UPDATE devices SET system_info = %s, updated_at = NOW() WHERE hostname = %s",
               (json.dumps(system_info), hostname))
self.connection.commit()
```
2. (Cleaner) Use Postgres native JSONB merge for just the fingerprint sub-key, accepting
   the Pitfall 4 SQLite/Postgres divergence as the price of correctness:
```sql
UPDATE devices
SET system_info = jsonb_set(system_info, '{fingerprint}', %s::jsonb),
    updated_at = NOW()
WHERE hostname = %s
```
The first option preserves Pitfall 4 parity. The second option drops parity but is
race-safe by construction. RESEARCH.md picked the parity choice; this finding flags
that the parity choice has a price worth documenting.

## Info

### IN-01: `_run_with_timeout` accesses private `conn._host` attribute

**File:** `src/homelab_mcp/ssh_tools.py:592`
**Issue:** Diagnostic logging uses `conn._host if hasattr(conn, "_host") else "?"` —
reaching into asyncssh's private API. `_host` is not part of asyncssh's public
contract; if asyncssh renames or removes it, the log message silently degrades to "?".
Today the `hasattr` guard prevents an exception, so this is a "log clarity" issue, not a
correctness one.

**Fix:** Pass the hostname explicitly into `_run_with_timeout` (the caller already has
it via `creds.hostname`):

```python
async def _run_with_timeout(
    conn: asyncssh.SSHClientConnection,
    command: str,
    *,
    cmd_name: str,
    timed_out: list[str],
    hostname: str = "?",   # NEW
    timeout: float = 10.0,
) -> "asyncssh.SSHCompletedProcess | None":
    ...
    logger.debug("SSH discovery probe %r exceeded %.1fs on %s; field skipped",
                 cmd_name, timeout, hostname)
```

### IN-02: `_maybe_json_load` silently swallows JSON decode errors

**File:** `src/homelab_mcp/database.py:942-960`
**Issue:** When `_maybe_json_load` receives a string that fails to decode, it returns
`None` rather than logging or raising. This is consistent with the doc-block's stated
"Passes ... decode error ... through as None" contract, but the silent loss means a
corrupted JSON column (e.g., from a partial write or external DB tampering) becomes
indistinguishable from "no data was ever written here". Operators investigating "why
did fingerprint go missing?" have no log signal to find.

**Fix:** Add a debug-level log on the decode-error path:

```python
try:
    return json.loads(value)
except json.JSONDecodeError:
    logger.debug("_maybe_json_load: failed to decode JSON value (truncated): %r", value[:100])
    return None
```

### IN-03: `merge_fingerprint` is "deep-merge" only one level deep

**File:** `src/homelab_mcp/database.py:963-983`
**Issue:** The docstring says "`capabilities` sub-dict deep-merges (incoming sub-keys
overwrite, missing sub-keys preserve)" — which is technically accurate, but
"deep-merge" implies recursive merging. The implementation uses `existing_caps.update(value)`
which is one level deep: `capabilities.vulkan = {"available": True}` followed by
`capabilities.vulkan = {"loader_version": "1.3.275"}` REPLACES the vulkan dict entirely
rather than merging. Documented at tool-reference.md:360 ("`capabilities` sub-dict
deep-merges") and the prompt body (`prompt_registry.py:208`).

This is probably the intended behavior (a 2-deep generic merge would have to choose
"overwrite vs merge" semantics for nested dicts and confuse agents), but the term
"deep-merge" is misleading. The Phase 39 drift detection should use either
`stored.capabilities.vulkan == incoming.capabilities.vulkan` (whole-dict comparison)
or trust agents to always pass the full vulkan dict when updating one of its fields.

**Fix:** Replace "deep-merge" with "shallow per-capability replace" in the docstrings
and tool-reference, OR document that callers must always pass the full per-capability
dict:

```python
"""Phase 38 D-05 merge contract: top-level overwrite, capabilities one-level overwrite.

- Top-level keys (kernel/os/package_*) overwrite (last-write-wins).
- ``capabilities`` sub-dict updates one level deep: incoming top-level capability keys
  REPLACE the stored entry entirely (e.g., passing capabilities={"vulkan": {"x": 1}}
  does NOT merge into the existing vulkan dict — it replaces it). Pass the full
  capability dict when updating any field within a capability.
"""
```

### IN-04: `connect_to_device` MCP prompt is undocumented in `tool-reference.md`

**File:** `docs/tool-reference.md:1632-1652`
**Issue:** The MCP Prompts section at lines 1632-1651 documents only
`configure_host_fingerprint` (Phase 38's new prompt). The other four registered prompts
(`decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`,
`connect_to_device`) are absent from the docs, even though they have been in the
codebase since earlier phases.

This is unrelated to Phase 38's diff but the same docs file was modified, and a reader
arriving at the prompts section will assume Phase 38 added the only documented prompt.

**Fix:** Add documentation entries for the four pre-existing prompts. At minimum, list
them with name + description + arguments, mirroring the format of
`configure_host_fingerprint`. This can be a follow-up PR.

### IN-05: `configure_host_fingerprint` prompt body has stylistic inconsistency

**File:** `src/homelab_mcp/prompt_registry.py:180-215`
**Issue:** The prompt body uses conversational phrasing ("Based on what I see on
{hostname}, here are signals I'd suggest tracking...") that doesn't match the more
declarative tone of the other prompt bodies. Compare to `_build_decommission_result`
(lines 99-118) which is plain imperatives. Mixing styles is a minor consistency issue
that surfaces when agents see the prompt; some MCP clients render the text directly to
the user.

**Fix:** Optional — rephrase to match. Example:

```text
3. Suggest the inferred signals to the user as a tracking proposal: list them, and ask
   the user to confirm, modify, or extend the list before probing.
```

### IN-06: Test mocks hardcode `_run_with_timeout` keyword args

**File:** `tests/test_ssh_tools.py:98,199-204,303,762,836`
**Issue:** Multiple test fixtures define their own `_run_with_timeout` mock with the
exact keyword-argument signature `(conn, command, *, cmd_name, timed_out, timeout=10.0)`.
If the helper's signature changes (e.g., `hostname` parameter from IN-01 above), every
mock site has to be updated in lockstep, and pytest will fail with a `TypeError:
unexpected keyword argument` rather than a clear "mock signature stale" message.

**Fix:** Either accept this as the price of mock fidelity, or extract a shared mock
factory to one place:

```python
# tests/conftest.py (or a helpers module)
def make_timeout_mock(stdout_by_cmd):
    async def _mock(conn, command, **kwargs):  # accept any kwargs
        cmd_name = kwargs["cmd_name"]
        timed_out = kwargs["timed_out"]
        # ... existing per-test logic ...
    return _mock
```

This is a minor test-maintenance concern, not a bug.

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
