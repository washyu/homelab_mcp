# Phase 23: Workflow Completeness - Research

**Researched:** 2026-03-15
**Domain:** MCP Prompts (connect_to_device onboarding), credential desync detection
**Confidence:** HIGH

## Summary

Phase 23 has two entirely self-contained deliverables. TOFU-03 adds a `connect_to_device` MCP prompt to `prompt_registry.py` — a text-only step sequence telling the agent how to onboard a new device from scratch. TOFU-04 adds a warning log to `resolve_ssh_credentials` in `ssh_tools.py` when the credential registry has a matching entry but `get_credential()` returns `None`.

Neither requirement touches SSH connection logic, tool schemas, handlers, or the tool registry. TOFU-03 is purely additive to `prompt_registry.py` and `server.py` (HOMELAB_PROMPTS dict already drives list_prompts). TOFU-04 is a single `logger.warning()` call inserted at the already-identified gap in `resolve_ssh_credentials` (line 82 area of `ssh_tools.py`). Both changes are small, low-risk, and follow patterns already established in Phase 14 and Phase 22.

**Primary recommendation:** Two plans — one per requirement. TOFU-03: add prompt + test. TOFU-04: add warning + test. Total scope is under 60 lines of production code.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TOFU-03 | `connect_to_device` MCP prompt sequences full device onboarding workflow | prompt_registry.py pattern is established; add entry to HOMELAB_PROMPTS + builder function |
| TOFU-04 | Warning logged when registry entry exists but keyring returns None (desync detection) | `resolve_ssh_credentials` already has the gap at line 82 — insert `logger.warning()` before the `if keyring_password:` guard falls through |
</phase_requirements>

## Standard Stack

### Core
| Component | Version/Location | Purpose | Why Standard |
|-----------|-----------------|---------|--------------|
| `mcp.types.Prompt` | mcp[cli] (installed) | Prompt metadata registration | Same type used by all 3 existing prompts |
| `mcp.types.GetPromptResult` | mcp[cli] (installed) | Prompt response container | Required by `get_prompt()` handler contract |
| `mcp.types.PromptArgument` | mcp[cli] (installed) | Declares prompt input parameters | Established pattern in HOMELAB_PROMPTS |
| `logging.getLogger(__name__)` | stdlib | Server log emission | Used throughout; already imported in `ssh_tools.py` |

### No New Dependencies
Both requirements are pure code changes within the existing stack. No new packages, no new modules.

## Architecture Patterns

### Pattern 1: Adding a Prompt (TOFU-03)

**What:** Add a new entry to `HOMELAB_PROMPTS` dict and a corresponding `_build_*` function in `prompt_registry.py`. Wire into `get_prompt_result` dispatcher.

**When to use:** Any new MCP prompt follows this exact three-part pattern.

**Files touched:**
```
src/homelab_mcp/prompt_registry.py   # HOMELAB_PROMPTS entry + _build function + dispatcher case
tests/test_mcp_prompts.py             # New test class for connect_to_device
```

**Example — existing pattern to follow:**
```python
# Source: src/homelab_mcp/prompt_registry.py (existing)
HOMELAB_PROMPTS["connect_to_device"] = types.Prompt(
    name="connect_to_device",
    description="...",
    arguments=[
        types.PromptArgument(name="hostname", description="...", required=True)
    ],
)

def _build_connect_to_device_result(args: dict[str, str]) -> types.GetPromptResult:
    hostname = args.get("hostname", "<hostname>")
    text = f"""..."""
    return types.GetPromptResult(
        description="Full device onboarding workflow",
        messages=[_make_user_message(text)],
    )

# In get_prompt_result dispatcher:
elif name == "connect_to_device":
    return _build_connect_to_device_result(args)
```

**No server.py changes needed.** `handle_list_prompts` already returns `list(HOMELAB_PROMPTS.values())` and `handle_get_prompt` already calls `get_prompt_result(name, arguments)`. The server wiring is fully generic.

### Pattern 2: Adding a Warning Log for Desync (TOFU-04)

**What:** In `resolve_ssh_credentials`, after `get_credential()` returns `None` for a host that IS in the registry, emit `logger.warning(...)` before the code falls through to the DB tier.

**Files touched:**
```
src/homelab_mcp/ssh_tools.py         # One logger.warning() at the desync gap
tests/test_ssh_credentials.py        # New test for the warning emission
```

**Exact insertion point** (lines 81-89 of current `ssh_tools.py`):
```python
# Source: src/homelab_mcp/ssh_tools.py lines 76-89 (current)
if matched:
    stored_username = matched[0]["username"]
    resolved_username = username or stored_username
    keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
    if keyring_password:
        ...
        return SSHCredentials(...)
    # TOFU-04: INSERT warning here — registry entry exists but keyring returned None
    # logger.warning("Credential desync for %s: registry entry exists but keyring returned None ...", hostname)
```

The warning fires only when `matched` is non-empty AND `keyring_password` is falsy. This is exactly the desync condition: the JSON registry knows about the host but the OS keyring has no secret.

### Prompt Content for `connect_to_device` (TOFU-03)

The success criterion says: "step-by-step onboarding sequence covering setup, registration, credentials, discovery, and verification." The required steps map to existing MCP tools:

| Step | Tool to Call | Purpose |
|------|-------------|---------|
| 1. Setup MCP admin user | `setup_mcp_admin` | Create mcp_admin user + SSH key on device |
| 2. Store credentials | CLI: `credentials add` | Persist SSH credential in OS keyring + registry |
| 3. Register in server DB | `register_server` | Add device to the credential/server table |
| 4. Discover device | `ssh_discover` | Collect hardware/system info and record in DB |
| 5. Map to network sitemap | `discover_and_map` | Add device to network sitemap |
| 6. Verify access | `verify_mcp_admin` | Confirm mcp_admin can connect |

The prompt must interpolate `hostname` and produce a numbered list instructing the agent to call these tools in order. The pattern is identical to `_build_decommission_result` — a single `types.GetPromptResult` with one `_make_user_message(text)`.

### Test Pattern (Wave 0 TDD)

**Established practice:** RED tests committed first (Wave 0), then implementation makes them GREEN.

For TOFU-03, the test structure follows `test_decommission_workflow_prompt`:
```python
# Source: tests/test_mcp_prompts.py (existing pattern)
def test_connect_to_device_prompt() -> None:
    from homelab_mcp.prompt_registry import get_prompt_result
    result = get_prompt_result("connect_to_device", {"hostname": "test-host"})
    combined_text = " ".join(msg.content.text for msg in result.messages
                             if hasattr(msg.content, "text")).lower()
    assert "setup_mcp_admin" in combined_text
    assert "credentials add" in combined_text
    assert "ssh_discover" in combined_text
    assert "verify_mcp_admin" in combined_text
```

For TOFU-04, the test uses `patch` + `caplog` (or `assertLogs`):
```python
# Pattern: patch list_credentials to return a match, get_credential to return None
@patch("src.homelab_mcp.ssh_tools.list_credentials")
@patch("src.homelab_mcp.ssh_tools.get_credential")
@patch("src.homelab_mcp.ssh_tools.get_database_adapter")
@patch("src.homelab_mcp.ssh_tools.get_mcp_ssh_key_path")
def test_desync_warning_logged(self, mock_key, mock_db, mock_get_cred, mock_list_creds):
    mock_list_creds.return_value = [{"hostname": "host", "username": "alice", "credential_type": "ssh"}]
    mock_get_cred.return_value = None  # desync: registry has entry, keyring is empty
    mock_key.return_value.exists.return_value = False
    mock_db.return_value.get_credential_by_hostname.return_value = None
    with pytest.raises(...):  # or falls through to CredentialNotFoundError
        resolve_ssh_credentials("host")
    # assert warning logged
```

Use `caplog` fixture (`caplog.set_level(logging.WARNING, logger="homelab_mcp.ssh_tools")`) or `assertLogs` context manager to capture the warning.

### Anti-Patterns to Avoid

- **Adding a new module for TOFU-03:** All prompts live in `prompt_registry.py`. Do not create a separate file.
- **Importing homelab_mcp modules in prompt_registry.py:** The file header explicitly says "Only imports mcp.types and mcp.shared.exceptions — no homelab_mcp imports (circular import prevention)." The prompt text is plain string interpolation only.
- **Modifying server.py for TOFU-03:** The prompt routing is already fully generic. No changes to `handle_list_prompts` or `handle_get_prompt` are required.
- **Raising an exception in TOFU-04 desync path:** The requirement says "a warning appears in server logs." The code must continue to fall through to the DB tier or raise `CredentialNotFoundError` as today — the warning is observational, not blocking.
- **Logging at DEBUG for TOFU-04:** The requirement says "warning," which maps to `logger.warning(...)` not `logger.debug(...)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prompt registration | Custom prompt dispatch | Add to `HOMELAB_PROMPTS` + `get_prompt_result` | Three existing prompts use this pattern; server wiring is already generic |
| Log-based desync alert | Custom notification system | `logger.warning(...)` | Python stdlib logging, already imported; server streams logs to client per MCP logging protocol |
| Test log capture | Custom log handler | `pytest caplog` fixture or `assertLogs` | Standard pytest mechanism, used in `test_logging_notifications.py` |

## Common Pitfalls

### Pitfall 1: HOMELAB_PROMPTS is a dict — order matters for list_prompts
**What goes wrong:** New entry appended outside the dict literal (like `list_keyring_credentials` was appended to `CREDENTIAL_TOOLS`) works but the prompt won't appear in `list_prompts` if it's added after module initialization. Actually for `HOMELAB_PROMPTS` this is not a problem — dict mutation at module level is fine because `handle_list_prompts` reads the dict at call time.
**How to avoid:** Add `connect_to_device` inside the `HOMELAB_PROMPTS = { ... }` literal body for cleanliness, or append after like existing tool schemas do. Both work.

### Pitfall 2: Warning text must identify the desync condition clearly
**What goes wrong:** A generic "keyring returned None" message doesn't help the operator diagnose the problem.
**How to avoid:** Include hostname and username in the warning: `"Credential desync for %s (user: %s): registry entry exists but keyring returned None — run 'homelab-mcp credentials add %s %s' to re-store", hostname, stored_username, hostname, stored_username`.

### Pitfall 3: Test isolation for TOFU-04 — list_credentials is patched at the right import path
**What goes wrong:** Patching `homelab_mcp.credential_store.list_credentials` instead of `src.homelab_mcp.ssh_tools.list_credentials` means the patch doesn't intercept the call in `resolve_ssh_credentials`.
**How to avoid:** Patch the symbol as imported in `ssh_tools.py`: `@patch("src.homelab_mcp.ssh_tools.list_credentials")` — exactly as done in the existing `TestCredentialNotFoundError` tests.

### Pitfall 4: `connect_to_device` argument name must match HOMELAB_PROMPTS declaration
**What goes wrong:** Declaring argument `hostname` in `HOMELAB_PROMPTS["connect_to_device"].arguments` but then reading `args.get("host")` in the builder.
**How to avoid:** Mirror the pattern exactly — `types.PromptArgument(name="hostname", ...)` and `args.get("hostname", "<hostname>")`.

## Code Examples

### Adding a prompt entry (verified pattern)
```python
# Source: src/homelab_mcp/prompt_registry.py (existing decommission pattern)
HOMELAB_PROMPTS: dict[str, types.Prompt] = {
    "decommission_device_workflow": types.Prompt(
        name="decommission_device_workflow",
        description="Safe guided workflow for decommissioning a homelab device",
        arguments=[
            types.PromptArgument(
                name="hostname",
                description="Hostname or IP of the device to decommission",
                required=True,
            )
        ],
    ),
    # ... add "connect_to_device" here ...
}
```

### Desync warning insertion point
```python
# Source: src/homelab_mcp/ssh_tools.py lines 76-89
if matched:
    stored_username = matched[0]["username"]
    resolved_username = username or stored_username
    keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
    if keyring_password:
        logger.debug("Auto-injected keyring credential for %s", hostname)
        return SSHCredentials(...)
    # TOFU-04: registry entry exists but keyring is empty — desync condition
    logger.warning(
        "Credential desync for %s (user: %s): registry entry exists but keyring "
        "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
        hostname, stored_username, hostname, stored_username,
    )
    # fall through to DB tier
```

### caplog test pattern (verified — used in test_logging_notifications.py)
```python
import logging
def test_desync_warning_logged(self, ..., caplog):
    with caplog.at_level(logging.WARNING, logger="homelab_mcp.ssh_tools"):
        # trigger the desync path
        ...
    assert any("desync" in r.message.lower() for r in caplog.records)
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_mcp_prompts.py tests/test_ssh_credentials.py -x` |
| Full suite command | `uv run pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOFU-03 | `connect_to_device` prompt returns step-by-step onboarding covering setup, credentials, discovery, verification | unit | `uv run pytest tests/test_mcp_prompts.py -k connect_to_device -x` | Tests in existing file — add new test function |
| TOFU-03 | `connect_to_device` appears in `HOMELAB_PROMPTS` (list_prompts) | unit | `uv run pytest tests/test_mcp_prompts.py::test_list_prompts_returns_prompts -x` | Existing test — update assertion count |
| TOFU-04 | Warning logged when registry entry exists but keyring returns None | unit | `uv run pytest tests/test_ssh_credentials.py -k desync -x` | New test in existing file |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_mcp_prompts.py tests/test_ssh_credentials.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration"`
- **Phase gate:** Full unit suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mcp_prompts.py::test_connect_to_device_prompt` — covers TOFU-03 (add to existing file)
- [ ] `tests/test_mcp_prompts.py::test_list_prompts_returns_prompts` — update `>= 3` count if needed, or add specific assertion for `connect_to_device` name
- [ ] `tests/test_ssh_credentials.py::TestResolveSSHCredentials::test_desync_warning_logged` — covers TOFU-04 (add to existing class)

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/homelab_mcp/prompt_registry.py` — full prompt pattern, circular import constraint
- Direct code inspection: `src/homelab_mcp/ssh_tools.py` lines 75-135 — exact desync gap location
- Direct code inspection: `src/homelab_mcp/credential_store.py` — `list_credentials`, `get_credential` signatures
- Direct code inspection: `tests/test_mcp_prompts.py` — existing test assertions for prompt content
- Direct code inspection: `tests/test_ssh_credentials.py` — `@patch` patterns for `list_credentials`, `get_credential`
- Direct code inspection: `src/homelab_mcp/tool_annotations.py` — no changes needed here for prompts
- `.planning/REQUIREMENTS.md` — authoritative requirement text for TOFU-03 and TOFU-04

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` decisions section — confirmed `asyncio.Lock` → `threading.Lock` (already done), no open TOFU issues except TOFU-03/04

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all required types/patterns exist and are tested in the codebase
- Architecture: HIGH — both requirements are small additive changes to existing, well-understood modules
- Pitfalls: HIGH — all pitfalls are derived from direct code inspection of the implementation site and existing test patterns

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable codebase, no fast-moving external dependencies)
