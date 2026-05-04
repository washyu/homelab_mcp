# Phase 33: Keyring Single Source of Truth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `33-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 33-keyring-single-source-of-truth
**Areas discussed:** DB table removal strategy, `register_server`'s new role, `mcp_admin` default SSH key fallback

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| DB table removal strategy | Active `DROP TABLE` migration vs passive abandon | ✓ |
| `register_server`'s new role | Remove / keep as write wrapper / verify-only | ✓ |
| `mcp_admin` default SSH key fallback | Remove entirely / keep file but drop fallback / delete key-gen | ✓ |
| `connect_to_device` prompt rewrite | CLI-only / hybrid on-device bootstrap / minimal passthrough | (Skipped — decided downstream of other answers) |

**User's choice:** First three areas. Prompt rewrite handled as a forced consequence in CONTEXT.md.

---

## DB Table Removal Strategy

### Q1: Should the server actively drop `ssh_credentials` on startup, or just abandon it?

| Option | Description | Selected |
|--------|-------------|----------|
| Active DROP on startup (Recommended) | `migration.py` runs `DROP TABLE IF EXISTS ssh_credentials` once. Clean state. | ✓ |
| Passive abandon | Delete code references; don't touch existing DBs. Table orphaned. | |
| Active DROP, gated by config flag | Drop only on opt-in via env var / CLI. | |

**User's choice:** Active DROP on startup.
**Notes:** Matches CRED-04 wording "no parallel credential storage exists" — passive abandon would technically still leave the table.

### Q2: What happens to the credential-specific database adapter methods?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove from `database.py` entirely (Recommended) | Delete `add_credential`, `get_credential_by_hostname`, `update_credential`, `delete_credential`, etc. | ✓ |
| Keep but mark deprecated | Leave methods with deprecation-warning logs. | |
| Keep only generic helpers | Remove credential-specific methods; keep any generic row helpers used elsewhere. | |

**User's choice:** Remove entirely.
**Notes:** Highest revert cost is desirable — any future "put SSH back in DB" attempt has to rebuild the method surface from scratch.

---

## `register_server`'s New Role

### Q1: What happens to `register_server` after keyring-only?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as keyring-write wrapper + verify (Recommended) | Tool stores credential in keyring, then verifies. | |
| Remove MCP tool entirely | Onboarding is CLI-only. | |
| Retain verify-only | Becomes read-only: resolves from keyring, verifies, returns OK/fail. | ✓ |

**User's choice:** Retain verify-only.
**Notes (user-provided):** "I don't really want password to be typed in chat with the agent; it should redirect to the CLI to do CRUD actions on the keyring." This overrides the "keyring-write wrapper" option entirely — no MCP tool writes credentials. Promoted to a phase-level guiding principle.

### Q2: Bootstrap of a fresh device's `mcp_admin` user — how does it happen now?

| Option | Description | Selected |
|--------|-------------|----------|
| User bootstraps manually out-of-band (Recommended) | User SSHs in, creates `mcp_admin`, installs pubkey. Docs describe path. | |
| CLI subcommand does it | `homelab-mcp bootstrap <host> --admin-user <existing-user>` prompts via terminal. | |
| Ship a provisioning script | `scripts/bootstrap-mcp-admin.sh` run by user locally or remotely. | |

**User's choice:** Out-of-band / documented.
**Notes (user-provided):** "Since the keyring is source of truth, if agent is asked to take an action on a server with hostname, it should fail if there isn't a keyring entry and fall back to asking user to use the CLI." — Fresh-device bootstrap is explicitly out of Phase 33 scope. Deferred to v1.7+.

---

## `mcp_admin` Default SSH Key Fallback

### Q1: What happens to the auto-injected `~/.ssh/mcp/mcp_admin_key` fallback?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove the fallback entirely (Recommended) | Delete lines 128-138 of `ssh_tools.py`. Keyring entry mandatory. | ✓ |
| Keep key generation, drop implicit fallback | Key still auto-generated but never auto-injected. | |
| Delete key generation entirely | Remove `~/.ssh/mcp/` directory and gen code. | |

**User's choice:** Remove the fallback entirely.
**Notes:** Key file generation itself stays (used for pubkey distribution to remote hosts); only the *implicit fallback* in `resolve_ssh_credentials` is deleted. The key can still be used if a user explicitly attaches it via the CLI.

### Q2 (reformulated after clarification): For SSH key-auth users, where does the hostname → key_path mapping live after the DB is gone?

**Original framing was too broad — user asked for clarification on what the keyring stores. Reframed:**

| Option | Description | Selected |
|--------|-------------|----------|
| Extend CLI: `credentials add <host> <user> --key-path <path>` (Recommended) | CLI gains `--key-path` flag. Keyring stores the path string. Parity with password auth. | ✓ |
| Key auth bypasses keyring | Users pass `key_path=` on every tool call. No central mapping. | |
| Defer key-auth support to v1.7 | Phase 33 handles password-auth only. Key-auth users pass `key_path=` until v1.7. | |

**User's choice:** Extend CLI with `--key-path` flag.
**Notes:** Registry gains an `auth_type: "password" | "key"` field (D-09). Backward-compat default for missing field is `"password"`.

---

## Claude's Discretion

- Exact file-layout of the DROP TABLE migration (inline in `init_schema` vs separate migration module).
- Error-message wording polish for `CredentialNotFoundError` variants.
- Docs layout for the manual `mcp_admin` bootstrap description.
- Strictness of `--key-path` validation (file exists? permissions? readable?).
- `connect_to_device` prompt exact wording — structure constrained by D-13; polish is planner's.

---

## Deferred Ideas

- Fresh-device bootstrap CLI (`homelab-mcp bootstrap <host>`) — v1.7+ candidate.
- One-shot `homelab-mcp migrate-credentials` that walks a legacy DB and emits `credentials add` commands to stdout.
- Provisioning script (`scripts/bootstrap-mcp-admin.sh`) as a simpler alternative to the bootstrap CLI.
- Encrypted keyring backups / export — permanently out of scope (homelab user manages their own keyring).

---

## Guiding Principles Promoted from This Discussion

1. **No passwords in chat.** All credential CRUD runs through the `homelab-mcp credentials` CLI. The MCP tool surface has zero write paths for credentials after this phase.
2. **Keyring is the source of truth.** If the keyring has no entry for a hostname that a tool needs credentials for, the tool fails with an actionable error pointing to `credentials add`. No silent defaults, no DB fallback, no `mcp_admin` auto-fill.
