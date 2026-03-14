# Phase 17: Credential Store Foundation - Research

**Researched:** 2026-03-14
**Domain:** Python `keyring` library, headless Linux fallback, lazy import patterns
**Confidence:** HIGH

## Summary

Phase 17 creates `credential_store.py` — the single module that wraps the OS keyring and exposes `store_credential`, `get_credential`, and `delete_credential` functions to the rest of v1.3. The primary challenge is not the happy path (keyring works fine on desktops) but the headless path: this server's primary deployment target is a headless Linux box where no D-Bus session is running. On such hosts, `keyring` raises `keyring.errors.NoKeyringError` (or in older versions a plain `RuntimeError`) on every call. Every public function in `credential_store.py` must catch all three exception types — `NoKeyringError`, `RuntimeError`, and the base `Exception` — and return a safe fallback value rather than propagating the exception.

The second key constraint from the project's accumulated decisions (STATE.md) is that `keyring` must never be imported at module level or called at server startup. Doing so would cause the D-Bus probing delay or warning to appear before any credential lookup is attempted, violating success criterion 3. The correct pattern is a lazy import inside each function body.

The `keyring` package is already referenced in `pyproject.toml` under `[project.optional-dependencies].security`. Phase 17 promotes it to `[project.dependencies]` at `>=25.6.0`. The 25.6.0 milestone was chosen because that release stopped logging warnings when no backend specification is present (confirmed via changelog), making it the minimum safe version for this use case.

**Primary recommendation:** Create `credential_store.py` with lazy `import keyring` inside each function, catch `(keyring.errors.NoKeyringError, RuntimeError, Exception)` on every call path, log warnings via standard `logging` only (no print to stderr), and return `None` / `False` as fallbacks. Never import `credential_store` in module-level code of other homelab_mcp modules (avoids circular imports and avoids early keyring probing).

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CRED-07 | Server warns and falls back gracefully to env-var-only mode when OS keyring is unavailable (headless Linux, no D-Bus) | Covered by: lazy import pattern, broad exception catching in every function, warning logged at first lookup attempt (not at import or startup), `keyring>=25.6.0` in `[project.dependencies]` |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| keyring | >=25.6.0 | OS keyring abstraction (GNOME Keyring, macOS Keychain, Windows Credential Locker) | Official Python keyring standard; used by pip, poetry, and most credential-aware tools |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging (stdlib) | built-in | Emit `logger.warning(...)` on headless fallback | Always — no third-party deps needed |
| `keyring.errors` | same as keyring | Exception classes `NoKeyringError`, `KeyringError`, `InitError` | Import inside function body only |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| keyring | keyrings.alt (encrypted file) | Requires `pycryptodomex` extra dep; CRED-F01 in future requirements — not scope for Phase 17 |
| keyring | secretstorage directly | Platform-specific; keyring abstracts all platforms |
| Lazy function-body import | Top-level `try/except ImportError` | Top-level import triggers D-Bus probing at startup — violates success criterion 3 |

**Installation (pyproject.toml change only — keyring already in optional deps):**

Move `keyring>=25.6.0` from `[project.optional-dependencies].security` to `[project.dependencies]`. No `uv add` command needed — edit `pyproject.toml` directly, then run `uv sync`.

---

## Architecture Patterns

### Recommended Module Structure

```
src/homelab_mcp/
└── credential_store.py    # New — no homelab_mcp imports (circular import prevention)

tests/
└── test_credential_store.py  # New — unit tests with keyring mocked
```

`credential_store.py` must have **no imports from `homelab_mcp`** — mirrors the constraint established for `prompt_registry.py` (STATE.md decision log). It may import `logging` and `keyring` (lazily inside functions).

### Pattern 1: Lazy Import with Broad Exception Catch

**What:** Import `keyring` inside each function body, not at module level. Catch `NoKeyringError`, `RuntimeError`, and `Exception`.

**When to use:** Every public function in `credential_store.py`.

**Example:**
```python
# Source: accumulated project constraints (STATE.md) + keyring.errors API (keyring docs)
import logging

logger = logging.getLogger(__name__)

_SERVICE_NAME = "homelab-mcp"


def store_credential(hostname: str, username: str, password: str) -> bool:
    """Store a credential in the OS keyring. Returns False on headless fallback."""
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        keyring.set_password(_SERVICE_NAME, f"{username}@{hostname}", password)
        return True
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — credential not stored for %s", hostname)
        return False
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — credential not stored for %s: %s", hostname, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — credential not stored for %s: %s", hostname, exc)
        return False


def get_credential(hostname: str, username: str) -> str | None:
    """Retrieve a credential from the OS keyring. Returns None on headless fallback."""
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        return keyring.get_password(_SERVICE_NAME, f"{username}@{hostname}")
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — no credential for %s", hostname)
        return None
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — returning None for %s: %s", hostname, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — returning None for %s: %s", hostname, exc)
        return None


def delete_credential(hostname: str, username: str) -> bool:
    """Delete a credential from the OS keyring. Returns False on headless fallback."""
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415
        from keyring.errors import PasswordDeleteError  # noqa: PLC0415

        keyring.delete_password(_SERVICE_NAME, f"{username}@{hostname}")
        return True
    except PasswordDeleteError:
        return False  # credential didn't exist — not an error for callers
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — delete skipped for %s", hostname)
        return False
    except RuntimeError as exc:
        logger.warning("OS keyring runtime error — delete skipped for %s: %s", hostname, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected keyring error — delete skipped for %s: %s", hostname, exc)
        return False
```

### Pattern 2: Key Naming Convention

The keyring key must encode both hostname and username to support multiple users per host. Use `f"{username}@{hostname}"` as the `username` field in `keyring.set/get/delete_password`. The `service_name` is the constant `"homelab-mcp"`.

**Why this matters:** keyring's `get_password(service, username)` is a two-part lookup. Hosts can have multiple credential entries (e.g., `root@192.168.1.1` and `admin@192.168.1.1`).

### Anti-Patterns to Avoid

- **Module-level `import keyring`:** Triggers D-Bus probing on Linux at import time, which can introduce a delay or warning before the server finishes starting up. Violates success criterion 3.
- **Catching only `NoKeyringError`:** On some headless hosts the fail backend raises `RuntimeError` instead (pre-25.x behavior observed in issue tracker). Catch both.
- **Importing from `homelab_mcp` inside `credential_store.py`:** Circular import risk. This module must be self-contained.
- **`sanitize_error(e)` import from `log_filter`:** Would require a homelab_mcp import. Instead, cast `str(exc)` directly in warning messages — credential values are not in the exception messages from keyring.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS keyring integration | Custom encrypted file store | `keyring>=25.6.0` | OS keyring provides platform-native encryption, ACL, and unlock flows; custom store has no encryption without pycryptodomex (CRED-F01 future work) |
| Backend detection | `os.environ` or D-Bus probing | `keyring.errors.NoKeyringError` catch | keyring already probes and raises the correct exception — re-probing is redundant and fragile |
| Key namespacing | Separate database table for key lookup | `f"{username}@{hostname}"` in keyring username field | Keyring's two-field (service, username) API is the correct scope boundary |

**Key insight:** The entire headless-safety problem is solved by catching the right exceptions in the right order, not by building detection infrastructure.

---

## Common Pitfalls

### Pitfall 1: Import at Module Level Causes Startup Warning/Delay

**What goes wrong:** `import keyring` at the top of `credential_store.py` causes D-Bus probing immediately when the server starts, even if no credential operations are ever performed. On headless hosts this may produce a warning before the MCP handshake completes.

**Why it happens:** The keyring library probes available backends during import (backend discovery via entry points).

**How to avoid:** Import `keyring` and `keyring.errors` inside each function body only.

**Warning signs:** Any keyring-related log output before "Server lifespan started" in startup logs.

### Pitfall 2: Only Catching `NoKeyringError` Misses Older Behavior

**What goes wrong:** On some headless Linux environments and older keyring versions, `RuntimeError("No recommended backend was available.")` is raised rather than `NoKeyringError`. Catching only `NoKeyringError` lets the `RuntimeError` propagate.

**Why it happens:** `NoKeyringError` was added as a specific subclass to allow targeted catching, but the underlying fail backend still raises `RuntimeError` in some code paths.

**How to avoid:** Always catch `(keyring.errors.NoKeyringError, RuntimeError, Exception)` — in that order.

**Warning signs:** `RuntimeError` appearing in test output when keyring is mocked to raise it.

### Pitfall 3: mypy Errors on Lazy Imports

**What goes wrong:** mypy's strict mode (`disallow_untyped_defs`, `warn_unused_ignores`) may flag `import keyring` inside function bodies, or may not find keyring's type stubs.

**Why it happens:** keyring ships inline types (py.typed marker) in recent versions — this should resolve cleanly. However, the `# noqa: PLC0415` ruff annotation is needed to silence "import not at top of file" (PLC0415).

**How to avoid:** Add `# noqa: PLC0415` to each in-function import. Verify mypy resolves keyring types once it is in `[project.dependencies]` and `uv sync` has run.

**Warning signs:** `mypy: error: Cannot find implementation or library stub for module named "keyring"` — resolve by ensuring `uv sync` has been run after moving keyring to core deps.

### Pitfall 4: `PasswordDeleteError` Must Be Caught Before Generic Fallback

**What goes wrong:** Deleting a credential that does not exist raises `keyring.errors.PasswordDeleteError`. If callers treat this as an error, they will show false failure messages.

**Why it happens:** keyring's `delete_password` raises `PasswordDeleteError` for missing entries — it does not silently succeed.

**How to avoid:** Catch `PasswordDeleteError` first and return `False` (or optionally `True` if "already gone" is acceptable). Document the semantic to callers.

### Pitfall 5: bandit `B110` on Broad `except Exception`

**What goes wrong:** `bandit` flags broad `except Exception: pass` patterns as B110 (try_except_pass).

**Why it happens:** bandit's B110 triggers on empty or overly broad except blocks.

**How to avoid:** The `except Exception` block in `credential_store.py` should always have a `logger.warning(...)` body — never `pass`. This satisfies bandit's intent and the project's `nosec` annotation policy (use specific B-codes with justification only when truly needed).

---

## Code Examples

Verified patterns from project codebase and keyring documentation:

### Existing Pattern: Local Import in Function Body (from server.py)
```python
# Source: src/homelab_mcp/server.py lines 544-546
def main() -> None:
    import argparse  # noqa: PLC0415
    import asyncio   # noqa: PLC0415
    ...
    import uvicorn   # noqa: PLC0415
    from homelab_mcp.http_app import create_http_app  # noqa: PLC0415
```
This is the established project pattern for deferred imports — apply identically in `credential_store.py`.

### Existing Pattern: `sanitize_error` in except blocks (from error_handling.py)
```python
# Source: src/homelab_mcp/error_handling.py
from .log_filter import sanitize_error
...
logger.error(f"...: {sanitize_error(e)}")
```
`credential_store.py` CANNOT use this pattern (no homelab_mcp imports). Use `str(exc)` directly — keyring exception messages do not contain credentials.

### keyring Core API (from official docs, keyring 25.7.0)
```python
# Source: https://keyring.readthedocs.io/en/latest/
keyring.set_password(service_name: str, username: str, password: str) -> None
keyring.get_password(service_name: str, username: str) -> str | None
keyring.delete_password(service_name: str, username: str) -> None
```

### Exception Hierarchy (from keyring.errors, confirmed via issue #566)
```python
# keyring.errors module contents (verified via issue tracker):
keyring.errors.KeyringError          # base
keyring.errors.InitError             # initialization failure
keyring.errors.PasswordSetError      # set_password failure
keyring.errors.PasswordDeleteError   # delete_password on missing entry
keyring.errors.NoKeyringError        # no backend available (headless / no D-Bus)
# RuntimeError also raised by fail backend in some environments
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `try/except RuntimeError` only | Also catch `NoKeyringError` (subclass of `KeyringError`) | keyring ~24.x added `NoKeyringError` | More precise error handling; `RuntimeError` catch still needed as belt-and-suspenders |
| `keyring` in optional deps | `keyring` in core deps (`[project.dependencies]`) | Phase 17 | All installs get keyring; no "security" extra needed |
| No fallback behavior documented | CRED-07: explicit warning + fallback to None/False | Phase 17 | Headless hosts work without crashing |

**Deprecated/outdated:**
- `keyrings.alt`: Third-party encrypted file backend — out of scope for Phase 17 (tracked as CRED-F01 future requirement). Do not reference or depend on it in this phase.
- `secretstorage` direct import: Platform-specific Python D-Bus binding; keyring wraps it. Never call directly.

---

## Open Questions

1. **Does `keyring>=25.6.0` cleanly install on headless Linux without pulling in D-Bus packages?**
   - What we know: keyring 25.x uses optional entry-point backend discovery; `secretstorage` (D-Bus backend) is a separate optional package not in keyring's core deps.
   - What's unclear: Whether `uv sync` on a headless CI runner will auto-install `secretstorage` as a transitive dep.
   - Recommendation: The Wave 0 test suite should verify `import keyring` succeeds in a clean `uv` environment without triggering dbus errors. The integration test for headless should mock `keyring.get_password` to raise `NoKeyringError`.

2. **Should `credential_store.py` expose a `is_keyring_available() -> bool` probe function?**
   - What we know: Phase 18 (CLI) will need to surface a status message to users. Phase 19 (inject) will need to know whether to attempt a lookup at all.
   - What's unclear: Whether a probe call (which itself would need the same try/except) adds value over just letting `get_credential` return `None`.
   - Recommendation: Defer to Phase 18 planning. Phase 17 only needs the three CRUD functions. A probe can be added in Phase 18 if the CLI needs it.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_credential_store.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-07 | `get_credential` returns `None` when `NoKeyringError` is raised | unit | `uv run pytest tests/test_credential_store.py::test_get_credential_headless_no_keyring_error -x` | Wave 0 |
| CRED-07 | `store_credential` returns `False` when `NoKeyringError` is raised | unit | `uv run pytest tests/test_credential_store.py::test_store_credential_headless_no_keyring_error -x` | Wave 0 |
| CRED-07 | `delete_credential` returns `False` when `NoKeyringError` is raised | unit | `uv run pytest tests/test_credential_store.py::test_delete_credential_headless_no_keyring_error -x` | Wave 0 |
| CRED-07 | `get_credential` returns `None` when `RuntimeError` is raised | unit | `uv run pytest tests/test_credential_store.py::test_get_credential_headless_runtime_error -x` | Wave 0 |
| CRED-07 | `store_credential` returns `True` when keyring succeeds | unit | `uv run pytest tests/test_credential_store.py::test_store_credential_success -x` | Wave 0 |
| CRED-07 | `get_credential` returns password string when keyring succeeds | unit | `uv run pytest tests/test_credential_store.py::test_get_credential_success -x` | Wave 0 |
| CRED-07 | `delete_credential` returns `False` on `PasswordDeleteError` (missing entry) | unit | `uv run pytest tests/test_credential_store.py::test_delete_credential_not_found -x` | Wave 0 |
| CRED-07 | No keyring import at `credential_store` module level | unit | `uv run pytest tests/test_credential_store.py::test_no_module_level_keyring_import -x` | Wave 0 |
| CRED-07 | `keyring>=25.6.0` in `[project.dependencies]` in `pyproject.toml` | unit | `uv run pytest tests/test_credential_store.py::test_keyring_in_core_dependencies -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_credential_store.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_credential_store.py` — covers all CRED-07 behaviors above (new file, does not exist)

*(All other test infrastructure already exists — pytest, pytest-mock, pyproject.toml config)*

---

## Sources

### Primary (HIGH confidence)
- Official keyring docs (https://keyring.readthedocs.io/en/latest/) — API signatures, exception classes, headless configuration
- keyring changelog (https://keyring.readthedocs.io/en/latest/history.html) — version 25.6.0 "avoids logging warnings when backend absent"
- Project codebase (`src/homelab_mcp/server.py`) — established lazy import pattern (`import argparse` inside `main()`)
- Project STATE.md — locked constraints: no homelab_mcp imports in credential_store.py, catch NoKeyringError + RuntimeError + Exception, no keyring at import/startup time

### Secondary (MEDIUM confidence)
- GitHub issue jaraco/keyring#566 — confirms `keyring.errors.NoKeyringError` is the correct exception class and import path for headless Linux scenarios
- keyring PyPI page / README — null backend via `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` (alternative disable mechanism)

### Tertiary (LOW confidence)
- Community reports that `RuntimeError` is also raised by fail backend in some environments — belt-and-suspenders catch, not formally documented in official API

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — keyring is the unambiguous standard; version pinned from changelog
- Architecture: HIGH — lazy import pattern is already established in server.py; exception hierarchy confirmed from official docs + issue tracker
- Pitfalls: HIGH for pitfalls 1-4; MEDIUM for pitfall 5 (bandit behavior confirmed from project Phase 16 decisions)

**Research date:** 2026-03-14
**Valid until:** 2026-09-14 (keyring is a stable library; 6-month window appropriate)
