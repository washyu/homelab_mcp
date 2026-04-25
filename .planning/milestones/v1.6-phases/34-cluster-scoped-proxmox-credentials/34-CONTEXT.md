# Phase 34: Cluster-Scoped Proxmox Credentials - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a cluster-scope storage tier for Proxmox API tokens so one credential stored at cluster scope automatically serves all N nodes in the same Proxmox datacenter. Per-node tokens from v1.3/v1.4 remain supported and take precedence when both exist. The mechanism extends the existing keyring + JSON registry pattern with new fields; it does not introduce a separate credential backend.

Scope anchor: CRED-08.

Out of this phase: SSH cluster-scope credentials (Proxmox only); automatic multi-cluster disambiguation beyond single-match on `/cluster/status`; persisting the node→cluster cache across server restarts; any MCP write path for cluster credentials (all CRUD is CLI per Phase 33 D-06).

</domain>

<decisions>
## Implementation Decisions

### Storage Model

- **D-01:** The credential registry entry gains two new fields: `scope: "node" | "cluster"` and `cluster_name: str`. Existing entries missing the `scope` field are treated as `scope="node"` by readers — back-compat for v1.3/v1.4 per-node Proxmox entries and for every SSH entry (SSH entries never carry cluster scope). Registry schema change is backward-readable; writers emit the new fields on every new entry.
- **D-02:** Cluster entries set `hostname: ""`. Readers that need to address a cluster entry branch on `scope == "cluster"` and use `cluster_name`, not `hostname`. Per-node entries continue to use `hostname` as the node's DNS name (unchanged).
- **D-03:** Cluster entries store the API token in the OS keyring under the key `f"{username}@cluster:{cluster_name}"` (e.g. `root@pam!mcp_cluster_tok@cluster:homelab-prod`). Per-node entries continue to use `f"{username}@{hostname}"` unchanged. The `:` literal in the cluster key form is collision-safe because `:` is invalid in DNS hostnames. Both key shapes live in the same `_SERVICE_NAMES["proxmox"] = "homelab-mcp-proxmox"` keyring service — no third namespace.

### Node → Cluster Discovery

- **D-04:** Cluster membership is discovered lazily at resolve time. On the first call to `resolve_proxmox_credentials(host)` where no per-node entry exists for `host`, the resolver iterates cluster entries and calls `/cluster/status` on `host` using each entry's API token. A match is: call authenticates (200 response) AND the returned cluster-name row equals that entry's `cluster_name` field. First match wins. The successful `host → cluster_name` mapping is cached in a module-level dict for the lifetime of the server process.
- **D-05:** Standalone (non-clustered) Proxmox nodes have no `/cluster/status` row of `type=cluster`. When the resolver walks cluster entries and no call returns a matching cluster row, the resolver raises `CredentialNotFoundError` naming the cluster entries that were tried and pointing to `homelab-mcp credentials add --type proxmox <hostname> <username>` as the fix (explicit per-node credential). No silent success and no default-host behavior.
- **D-05a (cache scope):** In-memory only. The cache is rebuilt per process start. A future phase may add a persistence layer; keeping it in-memory for v1.6 keeps the surface area minimal and avoids introducing a second credential-adjacent storage file.
- **D-05b (multi-cluster behavior):** When 2+ cluster entries exist and none has been matched against `host` yet, the resolver probes each in registry order. The first /cluster/status response whose returned cluster name equals an entry's `cluster_name` wins. Entries whose call fails (auth error, network error) are logged at DEBUG and skipped; they do not abort the loop.

### CLI Surface

- **D-06 (add):** `homelab-mcp credentials add --type proxmox --scope cluster:<cluster_name> <token_id>` — matches Success Criterion 1 verbatim. When `--scope cluster:*` is present, the positional `<hostname>` is dropped and only `<username>` / `<token_id>` is positional. `<token_id>` format remains Proxmox-standard (`user@realm!tokenname`). The CLI prompts for the token secret via `getpass` (TTY echo suppressed) — secrets never pass through argv or MCP. Per-node add shape is unchanged: `credentials add --type proxmox <hostname> <username>`.
- **D-07 (remove):** `homelab-mcp credentials remove --type proxmox --scope cluster:<cluster_name>` — mirrors the add shape exactly. When `--scope cluster:*` is present, no positional argument. Per-node remove shape is unchanged: `credentials remove <hostname> [--type ...]`.
- **D-08 (list):** `homelab-mcp credentials list --type proxmox` output uses grouped sections with headers:
  ```
  Stored proxmox credentials:
    Per-node:
      root@pam!tok1@pve1.home
      root@pam!tok2@pve2.home
    Cluster-scoped:
      root@pam!cluster_tok@cluster:homelab-prod
  ```
  When only one scope has entries, only that section renders. Satisfies Success Criterion 4.
- **D-08a (upsert semantics):** `credentials add` for a cluster entry is upsert by `(cluster_name, username, credential_type="proxmox")` — same idempotency rule as per-node entries. Re-running replaces both the keyring secret and the registry `auth_type`.

### Resolution & Observability

- **D-09:** A new async function `resolve_proxmox_credentials(host: str) -> tuple[str, Literal["node", "cluster"], str | None]` is introduced, parallel to the SSH-side `resolve_ssh_credentials()`. Returns `(api_token, scope, cluster_name)` where `cluster_name` is `None` for node-scope results. Raises `CredentialNotFoundError` with an actionable CLI-pointing message on miss. `get_proxmox_client` becomes `async def` and awaits this resolver.
- **D-10 (precedence):** Tier order inside `resolve_proxmox_credentials`:
  1. Per-node registry entry for `host` exists → return its token + `scope="node"`; `/cluster/status` is NEVER called in this path (Success Criterion 5 back-compat requires this short-circuit).
  2. Per-node miss → walk cluster entries, probe `/cluster/status` per D-04, match → return token + `scope="cluster"` + `cluster_name`.
  3. No match → raise `CredentialNotFoundError`.
- **D-11 (debug log):** One log record per tier attempt at `DEBUG` level. Format (indicative — wording is Claude's discretion):
  ```
  DEBUG: proxmox resolve host=pve1.home — tier=node
  DEBUG: proxmox resolve host=pve1.home — tier=node MISS
  DEBUG: proxmox resolve host=pve1.home — tier=cluster entries=[homelab-prod, staging]
  DEBUG: proxmox resolve host=pve1.home — tier=cluster MATCH cluster=homelab-prod
  ```
  Terminal record always names the winning `source=node|cluster`. Satisfies Success Criterion 2.
- **D-12 (shortcut removal):** Delete the "first registry entry" shortcut at `proxmox_api.py:227-242` entirely (the `registry_entries = list_credentials(...)` / `entry = registry_entries[0]` block). Callers of `get_proxmox_client()` must either pass `host=` explicitly or set `PROXMOX_HOST`. The shortcut was a v1.3 single-homelab assumption (INJECT-03) that's structurally incompatible with cluster-scope entries (a cluster entry has `hostname: ""` and is not meaningfully "first"). Users relying on the zero-arg shortcut migrate by setting `PROXMOX_HOST` — error message on the new error path names this exact env var.

### Tests (functional + unit, no AST meta-tests)

Regression guard class is intentionally excluded for Phase 34. These are new capabilities, not known footguns being repaired — the Phase 32/33/33.1 AST meta-test pattern does not apply (see `memory/feedback_regression_test_scope.md`). Standard functional + unit coverage is sufficient.

- **D-13:** Unit test — cluster-only match. No per-node entry for `pve1`, one cluster entry for `homelab-prod`, `/cluster/status` mocked via aiohttp test util to return the cluster-name row. Assert `resolve_proxmox_credentials("pve1")` returns `(token, "cluster", "homelab-prod")`.
- **D-14:** Unit test — per-node overrides cluster (Success Criterion 5). Both a per-node entry for `pve1` and a cluster entry for `homelab-prod` exist. Assert `resolve_proxmox_credentials("pve1")` returns `(per_node_token, "node", None)` AND that the `/cluster/status` mock was never called (spy on the aiohttp call).
- **D-15:** Unit test — standalone node error. No per-node entry for `pve-standalone`; one cluster entry exists; `/cluster/status` mocked to return no cluster-type row. Assert `CredentialNotFoundError` is raised with a message that (a) names the cluster entries that were tried and (b) includes `credentials add --type proxmox`.
- **D-16:** Debug-log assertion (Success Criterion 2). Use pytest `caplog` at `DEBUG` level; assert the log stream from D-13 contains at least one record per tier attempted and that the terminal record names `source=cluster`. Assert D-14's log stream contains a `source=node` terminal record and NO cluster-tier record (short-circuit proof).
- **D-16a:** No AST meta-test for the shortcut removal (D-12). Standard tests cover the behavior: if someone re-introduces `registry_entries[0]` logic, the zero-arg `get_proxmox_client()` call would start returning "first entry" again and the new discipline breaks — but guarding that via source scan is out of scope for this greenfield phase per the feedback rule above.

### MCP Tool Surface

- **D-17:** No MCP tool schema changes in Phase 34. Cluster credential CRUD lives entirely on the CLI (consistent with Phase 33 D-06). Discovery is lazy inside `resolve_proxmox_credentials` — no `discover_cluster` MCP tool, no `scope` filter on `list_keyring_credentials`, no new `list_proxmox_clusters` tool. MCP clients continue to see the same tool list as post-Phase-33.1.
- **D-17a (display tweak, not schema):** `list_keyring_credentials` MCP handler's return shape may gain a small display-level tweak so cluster entries render with their `cluster:<name>` address form — this is a handler-internal string-format change, not a schema property change, and does NOT require lock-step schema/annotation/openapi updates. Planner confirms during implementation whether the current handler return already distinguishes them via the stored `hostname=""` field; if not, a one-line branch in the handler covers it.

### Claude's Discretion

- Exact wording of the `CredentialNotFoundError` messages for missed-lookup vs standalone-node cases — must name `credentials add` and the tried cluster entries per D-05; beyond that, wording is planner's call.
- Exact debug-log string format per D-11 — the intent is "one line per tier attempt + terminal line naming winner"; minor phrasing variations acceptable.
- Whether `resolve_proxmox_credentials` lives in `proxmox_api.py` (alongside `get_proxmox_client`) or in its own module — planner picks; parallelism with `ssh_tools.resolve_ssh_credentials` suggests staying in the consumer module.
- Which cluster entry is tried first when multiple exist — registry-order is fine; no deterministic sort required beyond "stable order per JSON file".
- Exact argparse structure for the conditional positional (dropping `<hostname>` when `--scope cluster:*` is present) — planner picks; subparsers vs post-parse validation both acceptable.
- Whether the in-memory cache (D-05a) uses a plain `dict` or a `functools.lru_cache` wrapper — either works.
- Whether `get_proxmox_client` internally exposes a sync fallback for the env-var-only path (no registry lookup) or goes fully async across all callers — planner picks; the awaited callers are already in async code.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 34 Scope

- `.planning/ROADMAP.md` §Phase 34 — Phase goal + 5 Success Criteria (SC-1 through SC-5).
- `.planning/REQUIREMENTS.md` §v1.6 Requirements — CRED-08 definition; Out of Scope table (no auto-migration, no per-request overrides).
- `.planning/PROJECT.md` §Key Decisions — `credential_store.py` no-homelab_mcp-imports constraint, keyring lazy-import pattern, JSON hostname registry decision, `_SERVICE_NAMES` namespacing.

### Prior Phase Decisions (locked, inherited)

- `.planning/phases/33-keyring-single-source-of-truth/33-CONTEXT.md` — Phase 33 decisions D-01…D-25 that this phase builds on. Critical for Phase 34: D-06 (passwords never enter chat), D-08 (two-tier resolver pattern), D-18 (keyring is registry source of truth), D-23 (required-username convention).
- `.planning/phases/33-keyring-single-source-of-truth/33-0{1..5}-SUMMARY.md` — Actual shipped code from Phase 33. Planner reads before proposing edits.
- `.planning/phases/33.1-ssh-tool-family-keyring-uniformity-drop-hardcoded-mcp-admin-/33.1-CONTEXT.md` — Phase 33.1 decisions D-01…D-13. Relevant for Phase 34: D-04 (resolver registry-scan pattern when username is None; the cluster-entry-walk in D-04/D-10 is the analog for Proxmox), D-09 (schema-scan meta-test exists and guards D-06 at the MCP boundary — still holds for Phase 34 even though Phase 34 adds no new meta-test).
- `.planning/phases/33.1-ssh-tool-family-keyring-uniformity-drop-hardcoded-mcp-admin-/33.1-0{1..5}-SUMMARY.md` — Shipped 33.1 code.

### Keyring / Credential Store Foundation

- `.planning/milestones/v1.3-phases/17-credential-store-foundation/17-01-SUMMARY.md` — `credential_store.py` original contract and registry shape.
- `.planning/milestones/v1.3-phases/19-credential-auto-inject/19-01-SUMMARY.md`, `.planning/milestones/v1.3-phases/19-credential-auto-inject/19-02-SUMMARY.md` — v1.3 auto-inject patterns (the `INJECT-03` single-entry shortcut D-12 is deleting originates here).

### Source Files Affected

- `src/homelab_mcp/credential_store.py` (~lines 116–171) — `register_credential()` signature extension to accept `scope` and `cluster_name`; `list_credentials()` return shape gains the two new fields (backward-readable default for legacy entries).
- `src/homelab_mcp/proxmox_api.py` — `get_proxmox_client()` (~lines 190-260) becomes async; the `registry_entries[0]` shortcut block (~lines 224-242) is deleted (D-12); new `resolve_proxmox_credentials()` function lands alongside; all existing call sites inside async functions `list_proxmox_resources`, `get_proxmox_node_status`, `get_proxmox_vm_status`, `manage_proxmox_vm`, etc. (~lines 263-740) propagate the `await`.
- `src/homelab_mcp/server.py` — CLI handlers `_cmd_credentials_add` (~lines 491-548), `_cmd_credentials_list` (~lines 551-560), `_cmd_credentials_remove` (~lines 563-579); argparse setup (~lines 696-731) gains `--scope` flag; epilog help text (~lines 627-638) updated for cluster-scope examples.
- `src/homelab_mcp/tool_handlers/credential_handlers.py` — `list_keyring_credentials` handler (check current return shape to see whether the D-17a display tweak is needed).
- `tests/test_proxmox_api.py` (or a new `tests/test_proxmox_resolver.py`) — D-13/D-14/D-15/D-16 unit tests.
- `tests/test_credentials_cli.py` (or existing CLI test file) — cluster add/list/remove flow coverage.

### External / Proxmox API

- Proxmox VE API: `GET /cluster/status` — returns a list; a `type=cluster` row carries `name` (the cluster name). On standalone hosts this row is absent. This is the single external API contract Phase 34 depends on.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `credential_store.register_credential()` / `list_credentials()` / `get_credential()` / `store_credential()` / `delete_credential()` already handle the keyring+registry read/write path with headless-safe fallbacks. Phase 34 extends the registry entry shape but does not need new module-level helpers.
- `CredentialNotFoundError` already exists on the SSH side — Phase 34 uses the same class for Proxmox misses (or adds a Proxmox-specific subclass if planner prefers). Message shape (name the fix) is the established convention.
- `aiohttp.ClientSession` is already threaded through `get_proxmox_client` via the `session=` parameter. The new resolver's `/cluster/status` probes reuse the shared session when available; otherwise fall back to the per-request session pattern already in `proxmox_api.py:125-128`.
- `getpass.getpass` + `_cmd_credentials_add` — the existing TTY-echo-suppressed secret prompt is reused unchanged for cluster entries.

### Established Patterns

- **Lazy keyring import** inside each function body — must be preserved in any new D-04 cluster-walk code (headless-Linux D-Bus safety).
- **Backward-readable JSON registry** — new fields (D-01) follow the `auth_type` precedent (Phase 33 D-09): readers use `.get("scope", "node")` so legacy entries remain loadable without migration.
- **Two-tier resolver**: explicit args → keyring. Phase 34 adds a cluster-match sub-step inside the keyring tier (analog of Phase 33.1 D-04's registry-scan sub-step). Resolver contract stays two-tier; no third tier introduced.
- **Async throughout the Proxmox call chain** — all public `proxmox_api.py` functions are already `async def`. Making `get_proxmox_client` async is a natural extension; no sync/async boundary is crossed newly.

### Integration Points

- `resolve_proxmox_credentials` is the single funnel for Proxmox credentials — every Proxmox-touching async function flows through `get_proxmox_client()` which awaits it. Change the resolver and everything downstream follows.
- The Proxmox CLI subparser in `server.py` (~lines 696-731) is the only CLI surface the cluster work touches — SSH subcommands are unchanged.
- `list_keyring_credentials` MCP handler is the only tool surface that may need a one-line display tweak (D-17a). No other MCP handler reads Proxmox credentials directly — they all go through `get_proxmox_client`.
- Removal of the `registry_entries[0]` shortcut (D-12) is a minor breaking change to the zero-arg `get_proxmox_client()` pattern. The concrete callers that rely on it are small in number (grep for `get_proxmox_client()` with no args); most production call sites already pass `host=` explicitly.

</code_context>

<specifics>
## Specific Ideas

- **SC-1 literal shape preserved.** User chose to keep the success-criterion-verbatim `--scope cluster:<name>` CLI form rather than rephrase to `--cluster <name>`. Drives D-06, D-07.
- **Regression-test discipline boundary.** User explicitly classified Phase 34 as new-feature work (an "oversight being filled"), not bug-fix work. Saved to memory as `feedback_regression_test_scope.md`: AST meta-tests / source-scan regression guards are reserved for footgun-removal phases (Phase 32/33/33.1 pattern), not greenfield. Phase 34 uses functional + unit tests only. Drives D-13…D-16 scope and the explicit exclusion of any AST meta-test.
- **Cluster-walk matching model (D-04).** Resolver walks cluster entries in registry order, probes `/cluster/status` on the target host using each entry's token, matches when auth succeeds AND returned cluster name equals the entry's `cluster_name`. First match wins and is cached in memory for the process lifetime. Standalone hosts naturally error because no match is ever found.

</specifics>

<deferred>
## Deferred Ideas

- **Persisting the `host → cluster_name` cache across server restarts** — kept in-memory for v1.6 per D-05a. A future phase could write to `cluster_membership_cache.json` or extend the `devices` SQLite table with a `cluster_name` column; either is mechanical and additive.
- **New `list_proxmox_clusters` read-only MCP tool** — D-17 explicitly rejects adding this in Phase 34. Would help the agent self-disambiguate multi-cluster setups but is orthogonal to CRED-08. Candidate for a v1.7 polish phase if the multi-cluster user experience needs it.
- **Automatic multi-cluster disambiguation beyond first-match** — current D-04/D-05b design picks the first cluster entry whose call authenticates and matches. A pathological case with two clusters both containing a node of the same hostname on different networks would resolve nondeterministically based on registry order. Deferred because it requires no user to have reported hitting it.
- **SSH cluster-scope credentials** — Phase 34 is Proxmox-only. SSH has no analog of "one credential serves N hosts at the API layer." If a future need emerges (e.g., shared bastion credential), it would warrant its own phase.
- **Auto-migration from an existing per-node entry to a cluster entry** — not supported; if a user wants to consolidate N per-node entries into one cluster entry, they run `credentials add --scope cluster:<name>` then optionally `credentials remove` for the per-node entries. Mirrors Phase 33's "no auto-migration" stance.

</deferred>

---

*Phase: 34-cluster-scoped-proxmox-credentials*
*Context gathered: 2026-04-22*
