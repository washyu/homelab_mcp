# Feature Landscape

**Domain:** Homelab infrastructure management via MCP server (Proxmox-focused)
**Researched:** 2026-03-08
**Confidence:** MEDIUM-HIGH (based on MCP specification 2025-06-18, current codebase analysis, homelab ecosystem knowledge)

## Table Stakes

Features users expect. Missing = product feels incomplete or untrustworthy for a 1.0 release.

### Security Fundamentals

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| SSH host key verification | Users managing real infrastructure cannot accept MITM risk. 19 instances of `known_hosts=None` is a ship-blocker. | Med | Need known_hosts file management, first-connect trust-on-first-use (TOFU) pattern, and per-host key storage. Already identified in CONCERNS.md. |
| Proxmox SSL verification enabled by default | Self-signed certs are common in homelabs, but default should be secure with a documented override. | Low | Flip default to `True`, add `PROXMOX_VERIFY_SSL=false` env var for self-signed certs. Document clearly. |
| Input validation for hostnames, IPs, ports | An MCP tool that accepts `'; rm -rf /` as a hostname is a liability. Infrastructure tools operating over SSH must validate inputs. | Med | Validate hostnames (RFC 952), IPv4/IPv6 addresses, port ranges (1-65535), and CIDR notation. Add a validation module. |
| Secrets not logged | SSH passwords, API tokens, and Proxmox credentials must never appear in log output or error messages. | Low | Audit all logging paths. Redact sensitive fields in error responses. |

### MCP Protocol Compliance

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Tool annotations (readOnlyHint, destructiveHint) | MCP spec 2025-06-18 defines tool annotations. Clients use these to prompt for confirmation on destructive operations. A server managing VMs and infrastructure MUST annotate destructive tools. | Low | Add `annotations` dict to each tool schema. Read-only: `get_*`, `list_*`, `search_*`. Destructive: `delete_*`, `remove_*`, `decommission_*`, `destroy_*`. Mutating: `deploy_*`, `create_*`, `install_*`, `update_*`, `control_*`. |
| isError flag on tool execution errors | MCP spec requires `isError: true` in tool results for execution errors. Ensures clients distinguish between success and failure. | Low | Verify all error responses include `isError: true`. Currently returns error JSON but may not set this flag. |
| Proper JSON-RPC error codes | Use standard codes: `-32602` for invalid params, `-32603` for internal errors, `-32002` for resource not found. | Low | Audit `handle_request()` error paths. |
| Streamable HTTP transport | The MCP spec deprecated HTTP+SSE in favor of Streamable HTTP (single endpoint, POST for requests, GET for SSE). The current HTTP transport appears to implement this already. Verify compliance with session management (`Mcp-Session-Id`), `MCP-Protocol-Version` header, and `Origin` header validation. | Med | Current implementation uses Starlette with `/mcp` endpoint. Verify session ID handling, protocol version header, and DNS rebinding protection (Origin validation). |
| MCP logging capability | MCP spec defines `notifications/message` for structured log delivery to clients. Allows clients to see what the server is doing (SSH connections, deployments). | Med | Declare `logging` capability. Emit `notifications/message` for tool execution progress. Critical for infrastructure tools where operations take time. |

### All Tools Actually Work

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Stub functions implemented | `_update_sitemap_after_deployment()`, `_rediscover_device_after_config()`, and `_install_with_script()` are called but do nothing. A tool that silently skips its post-action is a bug. | Med | Three stubs identified in CONCERNS.md. Implement or remove the call sites. |
| Silent exception handlers replaced | 9 instances of `except: pass` swallowing errors. Users will see mysterious "nothing happened" responses. | Low | Add debug/warning-level logging to all silent handlers. |
| HTTP connection pooling for Proxmox | Creating a new TCP connection per API call is not acceptable for a 1.0. Users running multiple Proxmox queries will hit timeout issues. | Low | Store `aiohttp.ClientSession` as instance variable on `ProxmoxAPIClient`. |

### Documentation and Onboarding

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Setup guide (clone to first tool call) | Users must be able to go from zero to working in under 10 minutes. No documentation = no users. | Med | Cover: prerequisites, clone, uv sync, configure env vars, connect to MCP client, verify with a simple tool call. |
| Tool reference documentation | 44 tools is a lot. Users need to know what each tool does, what arguments it takes, and what it returns. | Med | Can auto-generate from tool schemas. Add examples for key workflows. |
| Configuration reference | Which env vars exist, what they do, what the defaults are. | Low | Single page listing all env vars with descriptions and defaults. |
| Error message quality | When a tool fails, the error message should tell the user what went wrong and what to do about it. | Med | Audit error messages across all handlers. Replace generic "Operation failed" with actionable messages. |

### Operational Reliability

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Graceful shutdown | Server must clean up SSH connections, close database, and stop cleanly on SIGTERM/SIGINT. | Low | Verify signal handlers exist. Clean up `ShellSessionManager` sessions. |
| Health endpoint accuracy | `/health` currently tracks error rates. Should also report Proxmox connectivity, database accessibility, and SSH key availability. | Low | Extend `HealthChecker` to include subsystem status. |
| Database migration safety | Migrations must not lose data on upgrade. | Low | Already has migration system. Verify it handles version skips. |

## Differentiators

Features that set this product apart. Not expected for 1.0 but add significant value.

### MCP-Native Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| MCP Resources for infrastructure state | Expose network sitemap, device inventory, and Proxmox cluster state as MCP Resources (not just tools). Clients can subscribe to changes. When a VM is created, the sitemap resource updates and clients see it without polling. | High | Implement `resources/list`, `resources/read`, `resources/subscribe`. Resource URIs: `homelab://sitemap`, `homelab://devices/{hostname}`, `homelab://proxmox/nodes/{node}`. Major value for AI context. |
| MCP Prompts for common workflows | Pre-built prompt templates: "Deploy a new service", "Diagnose connectivity issue", "Plan infrastructure changes". Users invoke via slash commands. | Med | Implement `prompts/list`, `prompts/get`. 5-8 prompts covering common workflows. Prompts embed relevant resources. |
| Structured output schemas | Add `outputSchema` to tools so clients can parse results programmatically. Enables better AI reasoning about tool results. | Med | Define JSON schemas for tool outputs. Return `structuredContent` alongside text. Backwards compatible. |
| Progress notifications during long operations | SSH discovery of a /24 subnet, bulk deployments, and Ansible playbook runs take time. Send progress via MCP logging notifications so the user knows something is happening. | Med | Use `notifications/message` with progress data. "Discovering 192.168.1.0/24: 45/254 hosts scanned". |

### Homelab-Specific Value

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Proxmox community script integration | Integrate with Proxmox community scripts (tteck/community-scripts or successors). "Install Pi-hole" should use a tested community script, not a custom Ansible playbook. Already has `search_proxmox_scripts` and `get_proxmox_script_info`. Verify these actually work end-to-end. | Med | Already partially implemented. Need E2E validation. |
| Infrastructure drift detection | Compare current device state against last known state. "Your Pi-hole server has a new package installed" or "disk usage jumped from 40% to 85%". | High | Schedule periodic re-discovery. Diff against stored state. Surface via `get_device_changes` (already exists) but make it richer. |
| Backup verification | After `create_infrastructure_backup`, verify the backup is restorable. Most backup tools never verify. | High | Requires spinning up test restore. Defer to post-1.0. |
| Network diagram generation | Generate visual network topology from sitemap data. Return as SVG or ASCII art in tool response. | Med | Use graphviz or ASCII art library. The `analyze_network_topology` tool exists; enhance output format. |

### Developer/Operator Experience

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dry-run mode for destructive operations | `deploy_infrastructure(dry_run=true)` shows what would happen without doing it. Critical for AI-driven operations where the model might make mistakes. | Med | Add `dry_run` parameter to destructive tools. Return planned actions as text. |
| Configuration validation on startup | Validate all env vars, check Proxmox connectivity, verify SSH key existence, test database access. Report all issues at once, not one at a time. | Med | Run validation suite on server start. Log results. Fail fast with actionable errors. |
| PyPI distribution | `pip install homelab-mcp` instead of clone + uv sync. Lowers barrier to adoption. | Med | Already has pyproject.toml. Need to verify package build, entry points, and publish workflow. Defer to post-1.0 per PROJECT.md. |

## Anti-Features

Features to explicitly NOT build for this project.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Web UI / Dashboard | MCP clients ARE the UI. Building a dashboard duplicates what Claude Desktop, OpenWebUI, and other clients already provide. It would become the maintenance burden that kills the project. | Invest in better tool output formatting so AI clients can present information well. |
| Multi-user / RBAC | Homelabs are single-operator. Multi-user support adds authentication complexity, permission matrices, and testing burden for a use case that does not exist. | Document that this is a single-operator tool. If someone needs multi-user, they should put it behind a reverse proxy with auth. |
| Plugin system / extension API | 44 tools is already a lot. A plugin system adds API stability guarantees, versioning complexity, and support burden. Let people fork instead. | Keep tool registry simple. Document how to add tools in CONTRIBUTING.md (already done). |
| Real-time monitoring / alerting | This is an MCP server, not Prometheus. Continuous monitoring requires a daemon, persistent state, alert routing, and integration with notification systems. All of this already exists as mature tools. | Expose point-in-time status queries. Let users set up Prometheus/Grafana/Uptime Kuma for monitoring. |
| Kubernetes management | K8s is a fundamentally different operational model from Proxmox VMs and LXC containers. Supporting it well requires a massive surface area (pods, services, ingress, storage classes, CRDs). | Keep the `k3s` service template for installing k3s, but do not try to manage k8s resources. Point users to existing k8s MCP servers. |
| PostgreSQL as default database | SQLite is correct for single-user homelab. PostgreSQL adds an installation dependency, connection management complexity, and zero benefit for the target user. | Keep PostgreSQL adapter for users who want it. Default to SQLite. Document when to switch. |
| Session persistence across server restarts | Interactive shell sessions are ephemeral by nature. Persisting them adds complexity (re-establishing SSH connections, PTY state) for minimal value. | Document that shell sessions are lost on restart. This is acceptable for 1.0. |
| Rate limiting | Homelabbers managing their own infrastructure will not overwhelm it with AI queries. Rate limiting adds complexity and user frustration for a non-problem. | If SSH connection storms become an issue, add connection pooling/queuing, not rate limiting. |
| Audit logging | Valuable for enterprises, overkill for a homelab. Standard logging is sufficient for a single operator who can read server logs. | Use MCP logging capability to surface operations to the client. The AI conversation itself serves as an audit trail. |

## Feature Dependencies

```
SSH Host Key Verification ── (no dependencies, foundational)
Input Validation ── (no dependencies, foundational)
Proxmox SSL Verification ── (no dependencies, foundational)

Stub Implementation ── depends on ── SSH Host Key Verification (stubs use SSH)
Silent Exception Fixes ── (no dependencies)
HTTP Connection Pooling ── (no dependencies)

Tool Annotations ── depends on ── Tool schema understanding
isError Flag ── (no dependencies)
Structured Output Schemas ── depends on ── Stable tool output formats

MCP Logging Capability ── (no dependencies, but should precede Progress Notifications)
Progress Notifications ── depends on ── MCP Logging Capability

MCP Resources ── depends on ── Stable database schema, working sitemap
MCP Prompts ── depends on ── Working tools (all stubs implemented)

Setup Guide ── depends on ── Configuration validation, working tools
Tool Reference Docs ── depends on ── Tool annotations, stable schemas

Dry-run Mode ── depends on ── Working destructive tools
Drift Detection ── depends on ── Working SSH discovery, stable sitemap
```

## MVP Recommendation

For a credible 1.0 release, prioritize in this order:

### Must Ship (blockers for 1.0)

1. **SSH host key verification** - Security blocker. Cannot ship infrastructure management tools that are vulnerable to MITM.
2. **Proxmox SSL verification default** - Same reasoning. Flip the default, document the override.
3. **Input validation** - Cannot ship tools that accept arbitrary strings as hostnames and pass them to SSH.
4. **Stub functions implemented** - Tools that silently do nothing are bugs.
5. **Tool annotations** - Low effort, high value. Clients need to know which tools are destructive.
6. **isError flag audit** - Protocol compliance. Low effort.
7. **Silent exception handlers fixed** - Replace `pass` with logging.
8. **HTTP connection pooling** - Performance baseline.
9. **Setup guide** - No docs = no users.

### Should Ship (strong 1.0 but not blockers)

10. **MCP logging capability** - Enables progress visibility for long operations.
11. **Tool reference documentation** - Auto-generate from schemas.
12. **Configuration reference** - List all env vars.
13. **Error message quality audit** - Actionable error messages.
14. **Configuration validation on startup** - Fail fast with clear errors.
15. **Graceful shutdown** - Clean cleanup on SIGTERM.
16. **Streamable HTTP compliance audit** - Verify session management, Origin validation.

### Defer to Post-1.0

- MCP Resources (high complexity, high value but not required for 1.0)
- MCP Prompts (nice-to-have, not expected)
- Structured output schemas (backwards compatible, can add incrementally)
- Dry-run mode (valuable but large surface area)
- Infrastructure drift detection (complex, needs reliable base first)
- PyPI distribution (explicit decision to defer per PROJECT.md)
- Network diagram generation (nice-to-have)
- Backup verification (very complex)

## Sources

- MCP Specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18/ (HIGH confidence - official spec)
- MCP Tools documentation: https://modelcontextprotocol.io/docs/concepts/tools (HIGH confidence)
- MCP Resources documentation: https://modelcontextprotocol.io/docs/concepts/resources (HIGH confidence)
- MCP Prompts documentation: https://modelcontextprotocol.io/docs/concepts/prompts (HIGH confidence)
- MCP Logging specification: https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging (HIGH confidence)
- MCP Security Best Practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices (HIGH confidence)
- MCP Transports (Streamable HTTP): https://modelcontextprotocol.io/docs/concepts/transports (HIGH confidence)
- Codebase analysis: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md` (HIGH confidence - direct inspection)
- PROJECT.md scope decisions (HIGH confidence - project owner decisions)
- Homelab ecosystem knowledge (MEDIUM confidence - training data, not verified against current ecosystem)
