# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-11
**Phases:** 5 | **Plans:** 15 | **Tasks:** 30

### What Was Built
- MCP SDK migration with ResourceManager lifecycle and graceful shutdown
- Security hardening: SSH TOFU, Proxmox SSL, input validation, credential redaction
- Functional completeness: stub implementations, silent exception elimination, tool annotations (49 tools)
- MCP protocol compliance: logging notifications, Origin validation, localhost bind
- Full documentation: setup guide, tool reference, configuration reference

### What Worked
- Phase ordering (architecture → security → functionality → compliance → docs) was correct — each phase built cleanly on prior
- Gap closure pattern (02-04, 02-05) caught real wiring gaps that initial plans missed — verification loop works
- Defense-in-depth approach for input validation (centralized in ssh_connect + handler-level) covered more attack surface
- Schema files as source of truth for tool documentation prevented drift
- AST-based regression test for silent exception handlers prevents future regressions

### What Was Inefficient
- ResourceManager.proxmox_session was built but never wired to consumers — last-mile wiring missed across Phase 1
- Some ROADMAP.md plan checkboxes not consistently updated (mix of [x] and [ ] despite all being complete)
- Nyquist VALIDATION.md frontmatter never flipped to compliant=true post-execution — bookkeeping gap

### Patterns Established
- ToolError exception pattern for MCP isError compliance (leverages SDK auto-behavior)
- CredentialFilter on root logger + sanitize_error() at error response boundaries
- Pure ASGI middleware pattern for HTTP middleware (vs BaseHTTPMiddleware)
- progress.py module pattern to break circular imports in server → handler → module chains

### Key Lessons
1. Verification loops catch real gaps — Phase 2 needed two additional gap closure plans after initial verification found missing wiring
2. "Build infrastructure, wire it later" creates orphaned exports — FUNC-05 Proxmox session pooling infrastructure exists but was never consumed
3. Documentation phases benefit from parallel execution — no dependencies between docs files, both plans ran in Wave 1

### Cost Observations
- Model mix: orchestrator on opus, researchers/planners/executors/verifiers on sonnet
- Timeline: 3 days from project init to milestone completion
- Notable: 15 plans executed across 5 phases with minimal rework (only 2 gap closure plans needed)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 15 | Initial milestone — established verification loop, gap closure, and documentation patterns |

### Cumulative Quality

| Milestone | Tests | Key Metric |
|-----------|-------|------------|
| v1.0 | 479 | 19/19 requirements satisfied, 5/5 E2E flows verified |

### Top Lessons (Verified Across Milestones)

1. Verification loops are essential — they caught 2 real gaps that would have shipped as bugs
2. Phase ordering matters — security after architecture allowed centralized enforcement points
