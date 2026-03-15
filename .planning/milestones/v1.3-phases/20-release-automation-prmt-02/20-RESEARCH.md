# Phase 20: Release Automation + PRMT-02 - Research

**Researched:** 2026-03-14
**Domain:** GitHub Actions OIDC publishing + MCP prompt text repair
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CICD-01 | PyPI publish triggered automatically when a `v*` git tag is pushed to main | Tag filter `startsWith(github.ref, 'refs/tags/v')` on existing `main.yml` publish job; existing workflow already triggers on `tags: ['v*']` |
| CICD-02 | Publish uses OIDC trusted publishing — no API tokens stored in GitHub secrets | `pypa/gh-action-pypi-publish@release/v1` with `permissions: id-token: write`; manual one-time PyPI trusted publisher registration required before first tag push |
| CICD-03 | Publish job only runs after the test-and-quality job passes | `needs: [test-and-quality]` on publish job; GitHub Actions enforces this ordering |
| CLI-02 | `decommission_device_workflow` prompt instructs AI to resolve hostname to device_id before calling `decommission_device` | `_build_decommission_result()` in `prompt_registry.py` currently passes `hostname` directly to `decommission_device`, which requires `device_id` (integer); fix is to insert a `get_network_sitemap` call step before the final decommission call |
</phase_requirements>

---

## Summary

Phase 20 has two independent workstreams that share a single wave structure: (1) adding a PyPI publish job to the existing GitHub Actions workflow using OIDC trusted publishing, and (2) fixing the `decommission_device_workflow` prompt so AI clients stop hitting schema validation errors.

The CI/CD work is additive — a new `publish-to-pypi` job appended to the existing `main.yml`. The existing workflow already triggers on `tags: ['v*']`, already has a `release` job gated on `test-and-quality`, and already uses `actions/checkout@v6` and `astral-sh/setup-uv@v4`. The new publish job slots in beside `release`, uses `needs: [test-and-quality]`, and a tag-only `if` guard. The critical prerequisite — PyPI trusted publisher registration — must happen manually at pypi.org before the first `v1.3.0` tag is pushed. The project name is `homelab-mcp` (matches `pyproject.toml`).

The PRMT-02 fix is a single-function edit in `prompt_registry.py`. The root bug is that `_build_decommission_result()` tells the AI to call `decommission_device` with `hostname="{hostname}"`, but `decommission_device` requires `device_id` (integer, schema-required). The fix inserts a `get_network_sitemap` call as Step 1 to resolve hostname to `device_id`, then uses `device_id` in subsequent steps. No schema changes needed; the prompt is plain text.

**Primary recommendation:** Add the `publish-to-pypi` job to `main.yml` (tag-only, needs test-and-quality, OIDC permissions), register the trusted publisher manually at pypi.org, and rewrite `_build_decommission_result()` to instruct the AI to call `get_network_sitemap` first.

---

## Standard Stack

### Core
| Library / Action | Version | Purpose | Why Standard |
|-----------------|---------|---------|--------------|
| `pypa/gh-action-pypi-publish` | `release/v1` (latest: v1.13.0) | Upload wheel/sdist to PyPI | Official PyPA action; built-in OIDC support; used by most Python projects |
| `actions/upload-artifact` | v7 (already in workflow) | Pass dist/ between jobs | Already pinned in this repo |
| `actions/download-artifact` | v7 | Retrieve dist/ in publish job | Matches upload pin |
| `python -m build` OR `uv build` | — | Produce wheel + sdist | `uv build` is the idiomatic choice given `uv` is already the package manager |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| GitHub Environment `pypi` | OIDC audience scoping, deployment protection rules | Required — PyPI trusted publisher configuration references the environment name |
| `hatchling` (already in pyproject.toml) | Build backend | Already configured; no change needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `uv build` | `python -m build` | Both produce identical artifacts; `uv build` faster and consistent with rest of workflow |
| Separate `publish.yml` workflow file | Add job to existing `main.yml` | REQUIREMENTS.md Out of Scope table explicitly rules out a separate file — must use `main.yml` |

**Installation / no new dependencies:** The publish job uses only GitHub Actions actions — no new Python packages required.

---

## Architecture Patterns

### CI/CD: Publish Job Structure

The publish job follows the standard PyPA two-job pattern (build → publish) but adapted to the existing single-job test workflow:

1. `test-and-quality` (existing) — runs always
2. `publish-to-pypi` (new) — runs only on `v*` tags AND only after `test-and-quality` passes

The build artifact is produced in a separate build step inside the publish job (simpler than a dedicated build job given this is a pure-Python project with no native extensions).

```yaml
# Source: https://docs.pypi.org/trusted-publishers/using-a-publisher/
publish-to-pypi:
  name: Publish to PyPI
  runs-on: ubuntu-latest
  needs: [test-and-quality]
  if: startsWith(github.ref, 'refs/tags/v')
  environment:
    name: pypi
    url: https://pypi.org/p/homelab-mcp
  permissions:
    id-token: write
  steps:
    - uses: actions/checkout@v6
    - uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: "pyproject.toml"
    - run: uv python install 3.12
    - run: uv build
    - uses: pypa/gh-action-pypi-publish@release/v1
```

Key properties:
- `needs: [test-and-quality]` — satisfies CICD-03
- `if: startsWith(github.ref, 'refs/tags/v')` — satisfies CICD-01 (non-tag pushes skip this job)
- `permissions: id-token: write` — satisfies CICD-02 (OIDC, no stored secrets)
- `environment: pypi` — required for OIDC audience matching

### PRMT-02 Fix: Prompt Text Rewrite

Root cause: `_build_decommission_result()` instructs the AI to call `decommission_device` with `hostname="{hostname}"`. The tool schema for `decommission_device` has `required: ["device_id"]` where `device_id` is an integer. The AI passes `hostname` (a string), and JSON schema validation rejects it.

Fix: Update the prompt text to include a `get_network_sitemap` call at Step 0 that returns the device list with `device_id` values. Then use `device_id` in the `decommission_device_preview` and `decommission_device` calls.

```python
# Source: src/homelab_mcp/prompt_registry.py _build_decommission_result()
# CURRENT (broken):
# 1. Call decommission_device_preview with hostname="{hostname}"
# 3. Call decommission_device with hostname="{hostname}"

# FIXED pattern:
text = f"""Follow these steps to safely decommission {hostname}:

1. Call get_network_sitemap to retrieve all devices. Find the entry where hostname \
matches "{hostname}" and note its device_id (integer).
2. Call decommission_device_preview with device_id=<device_id from step 1> to \
preview the operation.
3. Present the preview result to the user and ask for explicit confirmation before \
proceeding.
4. Only if the user confirms: call decommission_device with device_id=<device_id \
from step 1>.
5. Report the result to the user.

Do not proceed to step 4 without explicit user confirmation."""
```

### Anti-Patterns to Avoid

- **Storing PYPI_API_TOKEN in GitHub secrets**: CICD-02 explicitly prohibits this. OIDC replaces it entirely.
- **Triggering publish on every push**: The `if: startsWith(github.ref, 'refs/tags/v')` guard ensures publish only runs on version tags.
- **Using `needs: [release]`**: The existing `release` job creates GitHub Releases; PyPI publish should depend on `test-and-quality` directly, not chain through `release`.
- **Passing `hostname` to `decommission_device`**: The schema requires `device_id` (integer). No amount of prompt engineering will fix a schema validation error if the wrong parameter type is passed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PyPI upload auth | Custom token management / GitHub secret rotation | `pypa/gh-action-pypi-publish@release/v1` with OIDC | Handles token exchange, retries, attestations; official PyPA tool |
| Wheel/sdist creation | Custom build scripts | `uv build` | Already the project's package manager; produces correct hatchling artifacts |
| Tag-only job filtering | Complex `if` expressions with multiple conditions | `if: startsWith(github.ref, 'refs/tags/v')` | Single, readable, standard pattern |

---

## Common Pitfalls

### Pitfall 1: PyPI Trusted Publisher Not Registered Before First Tag
**What goes wrong:** The `publish-to-pypi` job runs on the first `v1.3.0` tag push and gets a 403 from PyPI because no trusted publisher is configured for the repo+workflow combination.
**Why it happens:** The PyPI trusted publisher configuration is a one-time manual step at `https://pypi.org/manage/project/homelab-mcp/settings/publishing/`. It cannot be done via the workflow itself.
**How to avoid:** Register the trusted publisher BEFORE pushing the first production tag. Fields required:
  - Owner: GitHub org/user
  - Repository: repo name
  - Workflow filename: `main.yml`
  - Environment: `pypi`
**Warning signs:** 403 HTTP response in the `pypa/gh-action-pypi-publish` step output.

### Pitfall 2: `environment:` Name Must Match PyPI Registration
**What goes wrong:** The workflow specifies `environment: name: release` but PyPI is configured for `pypi` (or vice versa). OIDC token exchange fails.
**Why it happens:** The environment name is embedded in the OIDC token claims that PyPI validates.
**How to avoid:** Use `pypi` as the environment name (the PyPI docs default and the name used in the registration form).

### Pitfall 3: `permissions: id-token: write` at Wrong Scope
**What goes wrong:** The permission is set at the workflow level instead of the job level. This grants all jobs excessive permissions.
**Why it happens:** Misplacing the permissions block.
**How to avoid:** Place `permissions: id-token: write` inside the `publish-to-pypi` job block, not at the top-level `permissions:` key.

### Pitfall 4: Version in pyproject.toml Not Updated Before Tagging
**What goes wrong:** The wheel uploaded to PyPI has version `1.2.0` but the git tag is `v1.3.0`. PyPI rejects a re-upload of an existing version if `1.2.0` was already published.
**Why it happens:** `pyproject.toml` version is static (not git-tag-derived). Must be manually bumped.
**How to avoid:** Update `pyproject.toml` version to `1.3.0` and commit before pushing the `v1.3.0` tag. (CICD-F01 hatch-vcs would eliminate this but is deferred.)

### Pitfall 5: Existing `release` Job vs New `publish-to-pypi` Job
**What goes wrong:** Both jobs have `needs: [test-and-quality]` and `if: startsWith(github.ref, 'refs/tags/')`. They run in parallel, which is fine — but developer confusion about which does what.
**How to avoid:** Keep them clearly named. `release` creates the GitHub Release (already exists). `publish-to-pypi` uploads to PyPI (new).

### Pitfall 6: `decommission_device_workflow` Still References `hostname` After Fix
**What goes wrong:** The test `test_decommission_workflow_prompt` checks for `decommission_device_preview` in the text and `confirm`. A refactored prompt that removes those words would break the existing test.
**How to avoid:** The test requirements are minimal — keep `decommission_device_preview` and `confirm` in the prompt text. The fix adds a `get_network_sitemap` step; it does not remove the existing confirmation step.

---

## Code Examples

### Complete Publish Job (verified pattern)
```yaml
# Source: https://docs.pypi.org/trusted-publishers/using-a-publisher/
# Adapted for this project's uv + hatchling stack
publish-to-pypi:
  name: Publish to PyPI
  runs-on: ubuntu-latest
  needs: [test-and-quality]
  if: startsWith(github.ref, 'refs/tags/v')
  environment:
    name: pypi
    url: https://pypi.org/p/homelab-mcp
  permissions:
    id-token: write
  steps:
    - uses: actions/checkout@v6
    - uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: "pyproject.toml"
    - name: Set up Python
      run: uv python install 3.12
    - name: Build distributions
      run: uv build
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
```

### Decommission Prompt Fix (verified against schema)
```python
# Source: src/homelab_mcp/prompt_registry.py
# decommission_device requires: device_id (integer) — NOT hostname
def _build_decommission_result(args: dict[str, str]) -> types.GetPromptResult:
    hostname = args.get("hostname", "<hostname>")
    text = f"""Follow these steps to safely decommission {hostname}:

1. Call get_network_sitemap to retrieve all tracked devices. Find the entry \
where hostname matches "{hostname}" and note its device_id (integer).
2. Call decommission_device_preview with device_id=<device_id from step 1> to \
preview the operation.
3. Present the preview result to the user and ask for explicit confirmation \
before proceeding.
4. Only if the user confirms: call decommission_device with \
device_id=<device_id from step 1>.
5. Report the result to the user.

Do not proceed to step 4 without explicit user confirmation."""
    return types.GetPromptResult(
        description="Safe device decommission workflow",
        messages=[_make_user_message(text)],
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `PYPI_API_TOKEN` in GitHub secrets | OIDC trusted publishing (`id-token: write`) | PyPI enabled OIDC ~2023; now the standard | No secrets to rotate; short-lived tokens only |
| `pypa/gh-action-pypi-publish@master` | `@release/v1` | master branch deprecated in 2024 | Must use `@release/v1` or a pinned tag |
| Separate `publish.yml` file | Single `main.yml` with tag-gated job | Project convention (see REQUIREMENTS.md Out of Scope) | Simpler, single point of truth |

**Deprecated/outdated:**
- `PYPI_API_TOKEN` secret: replaced by OIDC. Do not add to GitHub secrets.
- `pypa/gh-action-pypi-publish@master`: deprecated, use `@release/v1`.

---

## Open Questions

1. **`uv build` vs `python -m build`**
   - What we know: Both produce compatible artifacts for hatchling projects. The rest of the CI uses `uv`.
   - What's unclear: Whether `uv build` is available in the `astral-sh/setup-uv@v4` environment without a separate `pip install build`.
   - Recommendation: Use `uv build` — it's part of `uv` v0.4+ and setup-uv installs uv, not just pip. If it fails, fall back to `pip install build && python -m build`.

2. **Version bump timing**
   - What we know: `pyproject.toml` version is currently `1.2.0`. Must be `1.3.0` before pushing the tag.
   - What's unclear: Whether bumping the version is in scope for this phase or is a pre-tag manual step.
   - Recommendation: The plan should include a task to bump `pyproject.toml` version to `1.3.0` as part of this phase, since the publish job will fail if the version is not updated.

3. **GitHub environment `pypi` existence**
   - What we know: The workflow will reference `environment: name: pypi`. GitHub creates the environment automatically on first use, but it must match the PyPI trusted publisher registration.
   - What's unclear: Whether the repo already has a `pypi` environment configured in GitHub settings.
   - Recommendation: The plan should note this as a manual verification step (the environment can be created automatically by GitHub Actions on first run).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_mcp_prompts.py -v -m "not integration"` |
| Full suite command | `uv run pytest -v -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CICD-01 | Publish job has `if: startsWith(github.ref, 'refs/tags/v')` guard | structural (YAML lint/check) | manual review of `.github/workflows/main.yml` | ❌ Wave 0 |
| CICD-02 | Publish job has `permissions: id-token: write` and no stored secrets | structural (YAML check) | manual review of `.github/workflows/main.yml` | ❌ Wave 0 |
| CICD-03 | Publish job has `needs: [test-and-quality]` | structural (YAML check) | manual review of `.github/workflows/main.yml` | ❌ Wave 0 |
| CLI-02 | Decommission prompt instructs AI to call `get_network_sitemap` first to get `device_id` | unit | `uv run pytest tests/test_mcp_prompts.py::test_decommission_workflow_prompt -v` | ✅ (needs update) |

Note: CICD-01/02/03 are workflow file changes. The most meaningful automated test is a string assertion on the YAML content; alternatively these are verified by a successful dry-run against TestPyPI or the real tag push. The existing `test_decommission_workflow_prompt` test checks for `decommission_device_preview` and `confirm` in the prompt text — these must still be present after the fix.

### Additional test needed for CLI-02
The existing `test_decommission_workflow_prompt` does NOT check that `device_id` is used (it only checks for `decommission_device_preview` and `confirm`). A new assertion should verify that the prompt text contains `get_network_sitemap` and `device_id`.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_mcp_prompts.py -v -m "not integration"`
- **Per wave merge:** `uv run pytest -v -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_mcp_prompts.py` needs new assertions for CLI-02: `get_network_sitemap` and `device_id` in decommission prompt text (file exists but needs new test or extended assertion)
- [ ] No automated test for CICD-01/02/03 — workflow YAML is validated by manual inspection and by the first successful tag push

---

## Sources

### Primary (HIGH confidence)
- https://docs.pypi.org/trusted-publishers/using-a-publisher/ — OIDC workflow steps, permissions, environment config
- https://github.com/pypa/gh-action-pypi-publish — action version (v1.13.0), `@release/v1` pin, required permissions
- https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/ — complete workflow YAML pattern
- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` — `decommission_device` schema, confirms `device_id` (integer) is required, not `hostname`
- `src/homelab_mcp/prompt_registry.py` — current broken prompt text confirmed
- `.github/workflows/main.yml` — existing workflow structure confirmed

### Secondary (MEDIUM confidence)
- https://docs.github.com/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-pypi — GitHub's OIDC docs; consistent with PyPI docs

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyPI docs + official pypa action README verified directly
- Architecture: HIGH — existing workflow read; publish job pattern is standard PyPA
- Pitfalls: HIGH — PRMT-02 root cause verified from source code (schema requires `device_id`); OIDC pitfalls from official docs

**Research date:** 2026-03-14
**Valid until:** 2026-09-14 (PyPI OIDC and gh-action-pypi-publish are stable; prompt fix is purely internal)
