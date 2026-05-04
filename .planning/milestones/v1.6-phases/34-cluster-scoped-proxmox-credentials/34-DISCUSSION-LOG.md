# Phase 34: Cluster-Scoped Proxmox Credentials - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 34-cluster-scoped-proxmox-credentials
**Areas discussed:** Cluster storage model, Node → cluster discovery, CLI surface & list output, Resolution + observability, Tests, MCP scope

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Cluster storage model | Registry JSON + keyring shape; back-compat for per-node entries | ✓ |
| Node → cluster discovery | How `cluster_name` is learned and persisted per node | ✓ |
| CLI surface & list output | `credentials add --scope cluster:*` ergonomics; list distinction | ✓ |
| Resolution + observability | Resolver location, debug-log shape, fate of `registry_entries[0]` shortcut | ✓ |

**User's choice:** All four areas.

---

## Cluster Storage Model

### Q1: Registry + keyring encoding of a cluster-scope entry

| Option | Description | Selected |
|--------|-------------|----------|
| `scope` + `cluster_name` fields | Explicit enum; missing scope → "node" back-compat | ✓ |
| Overload `hostname` with `cluster:` prefix | Zero schema change; stringly-typed | |
| `cluster_name` field only, no scope enum | Lighter schema; presence-of-field implies scope | |
| Separate `cluster_credential_registry.json` | Two sources of truth to keep in sync | |

### Q2: `hostname` field for cluster-scope entry

| Option | Description | Selected |
|--------|-------------|----------|
| Empty string | Cluster entries set `hostname: ""`; readers branch on `scope` | ✓ |
| Mirror `cluster_name` into `hostname` | Keeps `hostname` non-empty for display reuse | |
| Prefixed `cluster:<name>` in `hostname` | Belt-and-suspenders, duplication with `cluster_name` | |

### Q3: Keyring key format for cluster entry

| Option | Description | Selected |
|--------|-------------|----------|
| `f"{username}@cluster:{cluster_name}"` | Mirrors node shape with `cluster:` marker | ✓ |
| `f"cluster:{cluster_name}:{username}"` | Scope-marker-first; two parse patterns | |
| Separate keyring service namespace | Third `_SERVICE_NAMES` entry to maintain | |

---

## Node → Cluster Discovery

### Q4: Discovery mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy live-lookup + in-memory cache | First resolve call probes `/cluster/status`, caches in module dict | ✓ |
| Explicit CLI discovery step | `homelab-mcp proxmox discover-cluster <host>` writes JSON file | |
| SQLite devices column + register_server hook | `cluster_name` column populated at device registration | |
| Explicit `--cluster` on credentials-add | User provides mapping at entry time; no API call | |

### Q5: Multi-cluster match disambiguation

| Option | Description | Selected |
|--------|-------------|----------|
| Try each cluster entry, match on /cluster/status response | Probe each entry, match when auth + returned cluster name align | ✓ |
| Enumerate cluster members at credentials-add time | Bootstrap host probed immediately; full member list cached | |
| Single-cluster assumption + explicit error on multi | 1 cluster entry → use it; 2+ → error | |

---

## CLI Surface & List Output

### Q6: CLI shape for adding a cluster-scope credential

| Option | Description | Selected |
|--------|-------------|----------|
| `--scope cluster:<name> <token_id>` | Matches SC-1 verbatim; conditional positional | ✓ |
| Dedicated `--cluster <name>` flag | Cleaner; diverges from SC-1 phrasing | |
| Separate subcommand `credentials add-cluster` | Zero argparse ambiguity; divergent surface | |

### Q7: `credentials list --type proxmox` distinction

| Option | Description | Selected |
|--------|-------------|----------|
| Grouped sections | "Per-node:" + "Cluster-scoped:" headers | ✓ |
| Flat list with `[scope]` tag prefix | Script-friendly grep-able tags | |
| Keep current flat format, `cluster:<name>` in row | No sections; relies on prefix recognition | |

### Q8: CLI shape for `credentials remove` on cluster entry

| Option | Description | Selected |
|--------|-------------|----------|
| `remove --type proxmox --scope cluster:<name>` | Mirrors add exactly | ✓ |
| Positional accepts `cluster:<name>` | Shorter; inconsistent with add | |
| Require explicit `--cluster-name` flag | Divergent flag shape between add/remove | |

---

## Resolution + Observability

### Q9: Where the per-node → cluster → error logic lives

| Option | Description | Selected |
|--------|-------------|----------|
| New async `resolve_proxmox_credentials(host)` | Parallel to `resolve_ssh_credentials`; `get_proxmox_client` becomes async | ✓ |
| Keep inline in `get_proxmox_client` | Extend existing lines 224-242 in-place | |
| Eager cache populated at first use | Separate discovery coroutine; resolver stays sync | |

### Q10: Debug-log shape

| Option | Description | Selected |
|--------|-------------|----------|
| One line per tier attempt | Verbose; tier + hit/miss + winning source | ✓ |
| Single-line summary per resolve | Compact; wording-sensitive | |
| Structured log event with tier list | Machine-parseable; heavier formatter requirement | |

### Q11: Fate of `registry_entries[0]` shortcut at `proxmox_api.py:227-242`

| Option | Description | Selected |
|--------|-------------|----------|
| Remove entirely | Callers must pass `host=` or set `PROXMOX_HOST` | ✓ |
| Keep only when zero cluster entries exist | Preserve for pure-v1.3/v1.4 installs | |
| Turn into deprecation warning | Gradual removal with log warning | |

---

## Tests (Clarification Round)

**User feedback:** These cluster-scope changes are new-feature work, not bug-fix work. AST meta-tests / source-scan regression guards are reserved for footgun-removal phases (Phase 32/33/33.1 pattern). Use functional + unit tests only.

**Saved to memory:** `feedback_regression_test_scope.md` — classifies when AST meta-tests are appropriate vs when functional tests suffice.

### Q12: Mandatory functional / unit tests

| Option | Description | Selected |
|--------|-------------|----------|
| Positive resolver: cluster-only match | /cluster/status mock returns matching cluster; resolver returns cluster token | ✓ |
| Positive resolver: per-node overrides cluster (SC-5) | Both entries exist; per-node wins; /cluster/status never called | ✓ |
| Positive resolver: standalone node error | No cluster row in response; `CredentialNotFoundError` names tried entries | ✓ |
| Debug-log assertion (SC-2 coverage) | `caplog` asserts one DEBUG record per tier + winning source | ✓ |

**AST meta-tests considered but rejected** (outside the functional/unit bar user set):
- AST meta-test: no `registry_entries[0]` shortcut reintroduction
- TOOLS-dict meta-test extension for cluster schema

---

## MCP Tool Surface

### Q13: MCP schema changes required?

| Option | Description | Selected |
|--------|-------------|----------|
| Pure CLI + resolver, no MCP schema changes | Cluster CRUD is CLI-only per D-06; discovery is lazy in resolver | ✓ |
| Add `scope` filter to `list_keyring_credentials` | Optional `scope: "node"\|"cluster"\|"all"` property | |
| Add new read-only `list_proxmox_clusters` MCP tool | Lock-step new-tool addition | |

---

## Claude's Discretion

- Exact wording of `CredentialNotFoundError` messages (must name `credentials add` + tried cluster entries).
- Exact debug-log string format (intent preserved: one line per tier + terminal line naming winner).
- Location of `resolve_proxmox_credentials` (alongside `get_proxmox_client` in `proxmox_api.py` vs new module).
- Order cluster entries are tried (registry order acceptable; no deterministic sort required).
- Argparse structure for conditional positional (subparsers vs post-parse validation).
- In-memory cache shape (plain `dict` vs `functools.lru_cache`).
- Whether a sync fallback for env-var-only `get_proxmox_client` is kept or all paths go async.

## Deferred Ideas

- Persisting `host → cluster_name` cache across restarts (SQLite column or JSON file) — v1.7+ candidate.
- `list_proxmox_clusters` read-only MCP tool — polish candidate if multi-cluster UX needs it.
- Automatic multi-cluster disambiguation beyond first-match — pathological case not yet reported.
- SSH cluster-scope credentials — Phase 34 is Proxmox-only.
- Auto-migration from per-node to cluster entry — not supported; re-run `credentials add`.
