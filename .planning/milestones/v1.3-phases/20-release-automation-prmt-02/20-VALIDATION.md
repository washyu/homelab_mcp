---
phase: 20
slug: release-automation-prmt-02
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_mcp_prompts.py -v -m "not integration"` |
| **Full suite command** | `uv run pytest -v -m "not integration"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_prompts.py -v -m "not integration"`
- **After every plan wave:** Run `uv run pytest -v -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | CICD-01, CICD-02, CICD-03 | structural (YAML review) | manual review of `.github/workflows/main.yml` | ❌ W0 | ⬜ pending |
| 20-01-02 | 01 | 1 | CLI-02 | unit | `uv run pytest tests/test_mcp_prompts.py::test_decommission_workflow_prompt -v` | ✅ (needs update) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mcp_prompts.py` — add assertions for `get_network_sitemap` and `device_id` in decommission prompt text (file exists but needs new assertions for CLI-02)

*Note: No automated tests exist for CICD-01/02/03 — workflow YAML structure is validated by manual inspection and by the first successful tag push.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Publish job triggers on `v*` tag push only | CICD-01 | GitHub Actions workflow — no unit test harness | Review `main.yml` publish job `if:` guard; push a test tag to verify |
| OIDC trusted publishing, no secrets stored | CICD-02 | Requires live PyPI registration and tag push | Verify `permissions: id-token: write` in workflow; verify no `PYPI_API_TOKEN` secret in repo settings |
| Publish job fails if tests fail | CICD-03 | Requires GitHub Actions environment | Verify `needs: [test-and-quality]` in workflow YAML |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
