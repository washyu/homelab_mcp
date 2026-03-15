---
phase: quick-6
plan: 6
type: execute
wave: 1
depends_on: []
files_modified:
  - README.md
  - docs/configuration.md
  - docs/setup-guide.md
autonomous: true
requirements: []
must_haves:
  truths:
    - README reflects v1.3 (PyPI-published, Python 3.12+, credentials CLI, accurate project structure)
    - configuration.md documents the credentials subcommand (add/list/remove with --type flag)
    - setup-guide.md shows the uvx install path alongside the git clone path
  artifacts:
    - path: README.md
      provides: Updated quick-start, project structure, MCP config with uvx, credentials section
    - path: docs/configuration.md
      provides: Credentials CLI reference table
    - path: docs/setup-guide.md
      provides: PyPI/uvx install option in section 2
  key_links:
    - from: README.md
      to: docs/configuration.md
      via: "credentials CLI docs link"
---

<objective>
Update README.md, docs/configuration.md, and docs/setup-guide.md to accurately reflect the v1.3 state of the project: Python 3.12+ requirement, PyPI package (uvx homelab-mcp), credentials CLI subcommand, and accurate module listing.

Purpose: The package is published to PyPI and has a full credential management CLI. Docs still describe v1.1-era clone-only setup with no mention of uvx, the credentials commands, or the correct Python version.
Output: Three updated docs files committed to git.
</objective>

<execution_context>
@/home/shaun/.claude/get-shit-done/workflows/execute-plan.md
@/home/shaun/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/home/shaun/projects/mcp_python_server/README.md
@/home/shaun/projects/mcp_python_server/docs/configuration.md
@/home/shaun/projects/mcp_python_server/docs/setup-guide.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Update README.md for v1.3</name>
  <files>README.md</files>
  <action>
Make the following targeted changes to README.md:

1. **Python badge** — change `python-3.10+-blue` to `python-3.12+-blue` (line 4, the badge URL).

2. **Quick Start section** — add a PyPI install option BEFORE the git clone block. The PyPI install is the recommended one-liner:

```bash
# Install from PyPI (recommended — no clone needed)
uvx homelab-mcp

# Or clone and run from source
git clone https://github.com/washyu/homelab_mcp.git
cd homelab_mcp
uv sync && uv run python run_server.py
```

3. **MCP Client Configuration section** — add a second config block showing the uvx form (no cwd needed) alongside the existing run_server.py form:

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uvx",
      "args": ["homelab-mcp"]
    }
  }
}
```
Label the first block "From source clone" and the new block "From PyPI (uvx)".

4. **Project Structure section** — the `tool_schemas/` entry is correct. Add these missing modules to the listing (after `error_handling.py`):
```
  credential_store.py    # OS keyring credential storage
  log_filter.py          # Credential redaction for log output
  prompt_registry.py     # MCP prompts registry
  resource_readers.py    # MCP resource read handlers
```
Remove the orphaned `tool_schemas/` note ("7 schema files") — the count is now 8 schema files in that directory.

5. **Add a Credential Management section** between "How It Works" and "MCP Client Configuration":

```markdown
## Credential Management

Store SSH and Proxmox credentials once so the server auto-injects them on every connection:

```bash
# Store an SSH credential
homelab-mcp credentials add 192.168.1.10 admin

# Store a Proxmox API credential
homelab-mcp credentials add 192.168.1.200 root@pam --type proxmox

# List stored credentials
homelab-mcp credentials list
homelab-mcp credentials list --type proxmox

# Remove a credential
homelab-mcp credentials remove 192.168.1.10
```

Credentials are stored in the OS keyring (libsecret on Linux, Keychain on macOS). When the OS keyring is unavailable (headless servers), credentials fall back to environment variables.
```
  </action>
  <verify>grep -n "uvx homelab-mcp\|3.12\|credential_store\|credentials add" /home/shaun/projects/mcp_python_server/README.md</verify>
  <done>README shows Python 3.12+ badge, uvx quick-start, uvx MCP config block, updated project structure, and credentials CLI section</done>
</task>

<task type="auto">
  <name>Task 2: Update docs/configuration.md and docs/setup-guide.md</name>
  <files>docs/configuration.md, docs/setup-guide.md</files>
  <action>
**docs/configuration.md** — Append a new top-level section after the existing CLI Arguments section:

```markdown
## Credentials CLI

The `credentials` subcommand manages stored credentials in the OS keyring. These are separate from environment variables and take precedence when the server connects to a host.

```bash
homelab-mcp credentials <subcommand> [options]
```

| Subcommand | Arguments | Description |
|------------|-----------|-------------|
| `add` | `<hostname> <username> [--type ssh\|proxmox]` | Prompt for password/token and store in OS keyring |
| `list` | `[--type ssh\|proxmox]` | List hostnames with stored credentials |
| `remove` | `<hostname> [--type ssh\|proxmox]` | Delete stored credential for a host |

**--type flag:**

| Value | Default | Use For |
|-------|---------|---------|
| `ssh` | yes | SSH password authentication |
| `proxmox` | no | Proxmox API token or password |

**Examples:**

```bash
# Add SSH credential (prompts for password)
homelab-mcp credentials add 192.168.1.10 admin

# Add Proxmox credential (prompts for API token or password)
homelab-mcp credentials add 192.168.1.200 root@pam --type proxmox

# List all SSH credentials
homelab-mcp credentials list

# List Proxmox credentials only
homelab-mcp credentials list --type proxmox

# Remove SSH credential for a host
homelab-mcp credentials remove 192.168.1.10

# Remove Proxmox credential for a host
homelab-mcp credentials remove 192.168.1.200 --type proxmox
```

> **Headless servers:** If the OS keyring is unavailable (no D-Bus session), `credentials add` will warn that the credential was not persisted. In that case, use environment variables (`PROXMOX_PASSWORD`, `PROXMOX_API_TOKEN`) as a fallback.
```

---

**docs/setup-guide.md** — In section "2. Clone and Install", prepend a PyPI option before the git clone block:

```markdown
## 2. Install

### Option A: Install from PyPI (recommended)

If you have `uv` installed, run the server directly from PyPI with no clone needed:

```bash
uvx homelab-mcp
```

`uvx` downloads and caches the package on first run. Subsequent runs start immediately.

For MCP client configuration with uvx, see section 5.

### Option B: Clone and run from source
```

Then keep the existing git clone block as the Option B body.

In section "5. Connect to MCP Client", under "Claude Desktop", add a second JSON block for the uvx form before the existing source-clone block, labelled "Using PyPI (uvx) — recommended":

```json
{
  "mcpServers": {
    "homelab": {
      "command": "uvx",
      "args": ["homelab-mcp"]
    }
  }
}
```

Label the existing block "Using source clone".

Do the same for the "Claude Code" section — add the uvx `.mcp.json` form first.
  </action>
  <verify>grep -n "credentials\|uvx homelab-mcp\|Option A\|Option B" /home/shaun/projects/mcp_python_server/docs/configuration.md /home/shaun/projects/mcp_python_server/docs/setup-guide.md</verify>
  <done>configuration.md has a full Credentials CLI section with add/list/remove reference table; setup-guide.md offers PyPI/uvx as Option A with uvx MCP config blocks</done>
</task>

</tasks>

<verification>
After both tasks:
- grep -c "uvx homelab-mcp" README.md docs/setup-guide.md  # should be >0 in each
- grep -c "credentials add" README.md docs/configuration.md  # should be >0 in each
- grep "3.12" README.md  # badge line
- uv run ruff check README.md docs/ 2>/dev/null || true  # markdown not linted, just confirm no obvious issues
</verification>

<success_criteria>
- README.md: Python 3.12+ badge, uvx quick-start, credential management section, accurate module list
- docs/configuration.md: Full credentials CLI reference with subcommand table and examples
- docs/setup-guide.md: PyPI/uvx install as Option A, uvx MCP config blocks in section 5
- All three files committed
</success_criteria>

<output>
After completion, create `.planning/quick/6-update-readme-and-setup-docs-to-reflect-/6-SUMMARY.md` with what was changed.
</output>
