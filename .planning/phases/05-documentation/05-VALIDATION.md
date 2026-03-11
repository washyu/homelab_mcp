---
phase: 5
slug: documentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5+ with pytest-asyncio |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/test_tools.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Verify markdown renders (no broken links, proper formatting)
- **After every plan wave:** Cross-check tool names in docs against tool_schemas
- **Before `/gsd:verify-work`:** Full suite must be green + manual review of all three documents
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | DOCS-01 | manual-only | N/A - documentation content review | N/A | ⬜ pending |
| 05-02-01 | 02 | 1 | DOCS-02 | smoke | `uv run python -c "from src.homelab_mcp.tool_schemas import get_all_tool_schemas; schemas=get_all_tool_schemas(); print(f'{len(schemas)} tools'); assert len(schemas) >= 49"` | No dedicated test | ⬜ pending |
| 05-03-01 | 03 | 1 | DOCS-03 | manual-only | N/A - documentation content review | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No test infrastructure changes needed — this is a documentation-only phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Setup guide covers clone through first tool call | DOCS-01 | Documentation prose quality and completeness cannot be automated | Follow the guide step-by-step on a clean environment; verify each step works |
| Tool reference documents all tools with args, returns, examples | DOCS-02 | While tool names can be cross-checked, example quality requires human review | Verify each tool entry has arguments, return format, and at least one example |
| Config reference lists all env vars with defaults | DOCS-03 | Completeness verifiable by cross-checking config.py, but description quality is manual | Compare documented vars against config.py; verify defaults match |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
