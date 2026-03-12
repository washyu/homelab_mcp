---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/homelab_mcp/tool_handlers/credential_handlers.py
  - src/homelab_mcp/tool_handlers/vm_handlers.py
  - tests/test_dry_run.py
  - tests/test_mcp_resources.py
  - tests/test_proxmox_api.py
autonomous: true
requirements: [QUICK-1]

must_haves:
  truths:
    - "uv run ruff format --check src/ tests/ exits 0"
    - "uv run ruff check src/ tests/ exits 0"
    - "CI pipeline lint step passes"
  artifacts:
    - path: "src/homelab_mcp/tool_handlers/credential_handlers.py"
      provides: "ruff-formatted source"
    - path: "src/homelab_mcp/tool_handlers/vm_handlers.py"
      provides: "ruff-formatted source"
    - path: "tests/test_dry_run.py"
      provides: "ruff-formatted test"
    - path: "tests/test_mcp_resources.py"
      provides: "ruff-formatted test"
    - path: "tests/test_proxmox_api.py"
      provides: "ruff-formatted test"
  key_links:
    - from: ".github/workflows/main.yml"
      to: "ruff format --check src tests"
      via: "Lint with ruff step"
      pattern: "ruff format --check"
---

<objective>
Fix CI/CD pipeline failure caused by 5 files failing ruff format check.

Purpose: The GitHub Actions "Lint with ruff" step runs `uv run ruff format --check src tests` which exits non-zero because 5 files have formatting drift. `ruff check` already passes — only the format check is broken.
Output: All 5 files reformatted to satisfy ruff's style rules, CI lint step passes.
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Auto-format all failing files with ruff</name>
  <files>
    src/homelab_mcp/tool_handlers/credential_handlers.py
    src/homelab_mcp/tool_handlers/vm_handlers.py
    tests/test_dry_run.py
    tests/test_mcp_resources.py
    tests/test_proxmox_api.py
  </files>
  <action>
    Run ruff format to fix the 5 files that fail the format check:

    ```
    uv run ruff format src/homelab_mcp/tool_handlers/credential_handlers.py \
      src/homelab_mcp/tool_handlers/vm_handlers.py \
      tests/test_dry_run.py \
      tests/test_mcp_resources.py \
      tests/test_proxmox_api.py
    ```

    The changes are whitespace/line-wrapping only — ruff is collapsing multi-line dict literals and assert statements to single lines per its line-length rules. No logic changes occur.

    After formatting, verify both ruff steps pass:
    ```
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/
    ```
  </action>
  <verify>
    <automated>uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/</automated>
  </verify>
  <done>Both ruff commands exit 0. No files reported as "would reformat".</done>
</task>

</tasks>

<verification>
Run the exact CI lint commands:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
```

Both must exit 0 with no output (or "All checks passed!" / "N files already formatted").
</verification>

<success_criteria>
- `uv run ruff format --check src/ tests/` exits 0 (was exit 1)
- `uv run ruff check src/ tests/` exits 0 (unchanged, already passing)
- The 5 previously-failing files are committed with formatting applied
</success_criteria>

<output>
After completion, create `.planning/quick/1-fix-ruff-ci-cd-pipeline-failures/1-SUMMARY.md`
</output>
