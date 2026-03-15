---
phase: quick
plan: 5
type: execute
wave: 1
depends_on: []
files_modified:
  - src/homelab_mcp/server.py
  - tests/test_credentials_cli.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "`homelab-mcp --help` output includes credential subcommand examples"
    - "A test asserts the help epilog contains the word 'credentials'"
  artifacts:
    - path: "src/homelab_mcp/server.py"
      provides: "Updated epilog showing credentials add/list/remove usage"
    - path: "tests/test_credentials_cli.py"
      provides: "Test asserting credentials appears in --help output"
  key_links:
    - from: "argparse epilog in main()"
      to: "user running homelab-mcp --help"
      via: "argparse --help formatting"
      pattern: "epilog=.*credentials"
---

<objective>
Add credential subcommand examples to the `homelab-mcp --help` epilog so users
discover the keystore CLI without reading source code.

Purpose: The credentials subcommand (add/list/remove) was implemented in Phase 18
but never added to the help epilog — it is invisible to users running --help.

Output: Updated epilog in server.py + a test asserting the help text mentions credentials.
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/5-we-are-missing-the-new-cli-arguments-for/5-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add credentials examples to --help epilog</name>
  <files>src/homelab_mcp/server.py</files>
  <action>
In `main()` (around line 579), update the `epilog` string passed to `argparse.ArgumentParser`.
The current epilog only shows stdio and HTTP examples. Append credential management examples.

Replace the current epilog:
```python
epilog="""
Examples:
  uvx homelab-mcp                        # stdio mode (Claude Desktop)
  uvx homelab-mcp --http --port 8080     # HTTP mode (OpenWebUI)
""",
```

With:
```python
epilog="""
Examples:
  uvx homelab-mcp                        # stdio mode (Claude Desktop)
  uvx homelab-mcp --http --port 8080     # HTTP mode (OpenWebUI)

Credential management (OS keyring):
  uvx homelab-mcp credentials add <hostname> <username>           # store SSH credential
  uvx homelab-mcp credentials add <hostname> <username> --type proxmox  # store Proxmox credential
  uvx homelab-mcp credentials list                                # list stored SSH credentials
  uvx homelab-mcp credentials list --type proxmox                 # list stored Proxmox credentials
  uvx homelab-mcp credentials remove <hostname>                   # remove SSH credential
  uvx homelab-mcp credentials remove <hostname> --type proxmox    # remove Proxmox credential
""",
```

No other changes to server.py.
  </action>
  <verify>
    <automated>uv run pytest tests/test_credentials_cli.py tests/test_packaging.py -x -q</automated>
  </verify>
  <done>
The epilog string in main() contains credential add/list/remove examples. Existing tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add test asserting credentials appears in --help output</name>
  <files>tests/test_credentials_cli.py</files>
  <action>
Add a new test function at the bottom of `tests/test_credentials_cli.py` that verifies
the --help output includes the credentials subcommand.

Follow the local-import pattern already used throughout this file (import inside function body).
Follow the pattern from `tests/test_packaging.py::test_main_help` for capturing --help output.

Add this test:

```python
def test_help_output_includes_credentials(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """--help output must mention credentials subcommand so users can discover it."""
    import sys  # noqa: PLC0415

    from homelab_mcp.server import main  # noqa: PLC0415

    monkeypatch.setattr(sys, "argv", ["homelab-mcp", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    combined = capsys.readouterr().out + capsys.readouterr().err
    assert "credentials" in combined, "Expected 'credentials' in --help output"
```

Place it after the last existing test function. Do not alter any existing tests.
  </action>
  <verify>
    <automated>uv run pytest tests/test_credentials_cli.py::test_help_output_includes_credentials -v</automated>
  </verify>
  <done>
New test passes green. `uv run pytest tests/test_credentials_cli.py -q` shows all tests pass.
  </done>
</task>

</tasks>

<verification>
uv run pytest tests/test_credentials_cli.py tests/test_packaging.py -q
uv run ruff check src/homelab_mcp/server.py tests/test_credentials_cli.py
</verification>

<success_criteria>
- `homelab-mcp --help` (or `python -m homelab_mcp --help`) shows credential add/list/remove examples in the epilog
- All existing credential CLI tests still pass
- New test `test_help_output_includes_credentials` passes green
- No ruff lint errors introduced
</success_criteria>

<output>
After completion, create `.planning/quick/5-we-are-missing-the-new-cli-arguments-for/5-SUMMARY.md`
</output>
