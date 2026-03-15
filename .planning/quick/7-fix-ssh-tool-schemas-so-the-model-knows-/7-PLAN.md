---
phase: quick-7
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/homelab_mcp/tool_schemas/ssh_tools_schema.py
  - src/homelab_mcp/ssh_tools.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "ssh_discover and ssh_execute_command do not list username as required"
    - "Tool descriptions tell the model to omit username when credentials are stored via credentials add"
    - "Fallback error messages do not mention register_server"
  artifacts:
    - path: "src/homelab_mcp/tool_schemas/ssh_tools_schema.py"
      provides: "Updated schemas for ssh_discover and ssh_execute_command"
    - path: "src/homelab_mcp/ssh_tools.py"
      provides: "Updated fallback error messages"
  key_links:
    - from: "ssh_tools_schema.py required arrays"
      to: "MCP client tool call validation"
      via: "JSON schema required field"
      pattern: '"required".*"username"'
---

<objective>
Fix SSH tool schemas so LLM clients (Claude Desktop) stop steering toward setup_mcp_admin/register_server flows and instead use ssh_discover/ssh_execute_command with keyring-stored credentials.

Purpose: The model reads tool descriptions and required fields to decide what parameters to supply. Currently username is required and descriptions say nothing about auto-injection, so the model asks the user for credentials even when they are already stored via `credentials add`.

Output: Updated schema file with username optional + keyring-aware descriptions; updated error messages in ssh_tools.py.
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/homelab_mcp/tool_schemas/ssh_tools_schema.py
@src/homelab_mcp/ssh_tools.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Make username optional and add keyring descriptions in ssh_tools_schema.py</name>
  <files>src/homelab_mcp/tool_schemas/ssh_tools_schema.py</files>
  <action>
Edit the SSH_TOOLS dict in ssh_tools_schema.py. Make two targeted changes:

1. ssh_discover:
   - Change top-level "description" to: "SSH into a system and gather hardware/system information. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them."
   - Change "username" field description to: "SSH username. Omit if credentials were stored with `credentials add` — they are auto-injected."
   - Change "password" field description to: "SSH password. Omit if credentials were stored with `credentials add` — they are auto-injected."
   - Change "required" from ["hostname", "username"] to ["hostname"]

2. ssh_execute_command:
   - Change top-level "description" to: "Execute a command on a remote system via SSH. If credentials were stored with `credentials add`, username and password are auto-injected from the keyring — omit them."
   - Change "username" field description to: "SSH username. Omit if credentials were stored with `credentials add` — they are auto-injected."
   - Change "password" field description to: "SSH password. Omit if credentials were stored with `credentials add` — they are auto-injected."
   - Change "required" from ["hostname", "username", "command"] to ["hostname", "command"]

Do NOT touch setup_mcp_admin, verify_mcp_admin, start_interactive_shell, or update_mcp_admin_groups.
  </action>
  <verify>
    <automated>grep -n '"required"' /home/shaun/projects/mcp_python_server/src/homelab_mcp/tool_schemas/ssh_tools_schema.py</automated>
  </verify>
  <done>ssh_discover required=["hostname"], ssh_execute_command required=["hostname","command"], both descriptions mention auto-inject from keyring</done>
</task>

<task type="auto">
  <name>Task 2: Fix misleading fallback error messages in ssh_tools.py</name>
  <files>src/homelab_mcp/ssh_tools.py</files>
  <action>
There are two error messages that tell the model to use register_server. Replace both with messages that point to `credentials add` instead.

Line ~416 (inside ssh_discover logic):
  FROM: "Register the server first with register_server or provide password/key_path."
  TO:   "No credentials found for {hostname}. Store them with `credentials add` or pass password/key_path explicitly."

Line ~639 (inside ssh_execute_command logic):
  FROM: "Register the server first with register_server or provide password."
  TO:   "No credentials found for {hostname}. Store them with `credentials add` or pass password explicitly."

Use the Read tool to verify line numbers before editing, then apply minimal edits to those two string literals only. Do not change any surrounding logic.
  </action>
  <verify>
    <automated>grep -n "register_server\|credentials add" /home/shaun/projects/mcp_python_server/src/homelab_mcp/ssh_tools.py</automated>
  </verify>
  <done>Neither error message string contains "register_server"; both mention "credentials add"</done>
</task>

<task type="auto">
  <name>Task 3: Verify quality gates pass</name>
  <files></files>
  <action>
Run ruff and mypy to confirm no regressions were introduced by the schema and string edits.

Commands to run in order:
  uv run ruff check src/homelab_mcp/tool_schemas/ssh_tools_schema.py src/homelab_mcp/ssh_tools.py
  uv run mypy src/homelab_mcp/tool_schemas/ssh_tools_schema.py src/homelab_mcp/ssh_tools.py

If either fails, fix before proceeding. Schema changes are pure dict literals so type errors are unlikely; the string replacements in ssh_tools.py are local to existing f-string/string expressions.
  </action>
  <verify>
    <automated>uv run ruff check src/homelab_mcp/tool_schemas/ssh_tools_schema.py src/homelab_mcp/ssh_tools.py && uv run mypy src/homelab_mcp/tool_schemas/ssh_tools_schema.py src/homelab_mcp/ssh_tools.py</automated>
  </verify>
  <done>ruff and mypy both exit 0 for the two modified files</done>
</task>

</tasks>

<verification>
grep -n '"required"' src/homelab_mcp/tool_schemas/ssh_tools_schema.py
# Expected: ssh_discover has ["hostname"], ssh_execute_command has ["hostname","command"]

grep -n "register_server" src/homelab_mcp/ssh_tools.py
# Expected: only the function definition line (def register_server), no error message strings
</verification>

<success_criteria>
- ssh_discover.required = ["hostname"] (username removed)
- ssh_execute_command.required = ["hostname", "command"] (username removed)
- Both tool descriptions and username/password field descriptions mention keyring auto-inject
- Error messages in ssh_tools.py reference "credentials add", not "register_server"
- ruff and mypy pass on modified files
</success_criteria>

<output>
After completion, create `.planning/quick/7-fix-ssh-tool-schemas-so-the-model-knows-/7-SUMMARY.md`
</output>
