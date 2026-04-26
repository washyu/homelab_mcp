# Phase 38: Sitemap Fingerprint Schema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 38-sitemap-fingerprint-schema
**Areas discussed:** Capability probes (set + error semantics), Package fingerprint shape, Storage shape, Cross-OS coverage

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Capability probes (set + error semantics) | What to probe + how to mark absent tools | ✓ |
| Package fingerprint shape | Opaque digest vs named subset vs both | ✓ |
| Storage shape | Per-field columns vs JSON blob | ✓ |
| Cross-OS coverage | Debian-only vs OS-detection branching vs distro-tagged structure | ✓ |

**User's choice:** All four areas.

---

## User-Driven Reframe (early in Area 1)

After the initial gray-area presentation for capability probes, user clarified the architectural approach:

> "I think it would be hard for this to be generalized to a single database schema since each system might have a different role. One could be a gateway, or a storage server, or a Ollama server — could we just specify a json object schema and give instructions to the agent to ask the user what is important to track per system?"

This reshaped Phase 38 from "fixed capability schema with universal probes for all" to "single freeform `fingerprint` JSON column + universal core probes (kernel/OS/packages) + agent-driven per-host capability Q&A via a new MCP prompt."

The original four area questions were re-formulated against the new architecture rather than answered against the old one.

---

## Area: Per-Host Workflow Topology (clarifying re-ask)

**Question:** Where does the 'agent asks user what to track per host' workflow live?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 38 ships interactive workflow at every touchpoint | Phase 38 wires VM creation, LXC creation, scripts, AND discovery |  |
| Phase 38 ships substrate; v1.7.2 ships workflow | Schema only; v1.7.2 layers role tags + workflow |  |
| Hybrid: Phase 38 substrate + manual JSON edit path | Schema + low-friction edit; no agent-driven Q&A |  |

**User's clarification (free-text):** "the obvious places would be create vm/lxc, or when a users ask to do the ssh_discover call, as for the proxmox scripts the user will already be asking for a service so that one is obvious."

**Interpretation locked:** The natural touchpoints are VM/LXC create, SSH discovery, and Proxmox script onboarding. Of those, VM/LXC create and Proxmox scripts are already in v1.7.1's locked scope (LIFE-01..04, LIFE-09, LIFE-10). Phase 38 owns only the discovery-time path. v1.7.1 will reuse Phase 38's `update_device_fingerprint` tool from the other touchpoints.

---

## Area: Ask-Flow Mechanism

**Question:** How should the 'agent asks user what to track' behavior be delivered in Phase 38?

| Option | Description | Selected |
|--------|-------------|----------|
| Static instruction in MCP prompt / tool description (Recommended) | New prompt template; agent follows instructions in conversation | ✓ |
| Wired post-discovery prompt callback | discover_and_map handler returns a structured 'configure-fingerprint' question; new tool persists |  |
| Substrate only — ask flow deferred | Phase 38 ships only schema + universal probes; ask flow waits for v1.7.2 |  |

**User's choice:** Static instruction in MCP prompt / tool description.

---

## Area: Storage Shape

**Question:** Does the fingerprint JSON separate 'what to track' from 'last captured values'?

| Option | Description | Selected |
|--------|-------------|----------|
| One blob — store whatever the agent populated (Recommended) | Single `fingerprint` JSON column; "what to track" implicit as "what's been populated" | ✓ |
| Two fields: `tracking_config` + `fingerprint_values` | Separate user intent from captured values |  |
| Three fields: kernel_version + package_fingerprint columns + capabilities JSON | Hybrid: typed columns for universal core + JSON for capabilities |  |

**User's choice:** One blob — store whatever the agent populated.

---

## Area: Universal Core Depth

**Question:** How deep is the 'universal core' that Phase 38 probes on every host?

| Option | Description | Selected |
|--------|-------------|----------|
| Kernel + package fingerprint (Recommended) | Always probe `uname -r` + a package digest; capabilities 100% per-host opt-in | ✓ |
| Kernel only | Only `uname -r` is universal; packages move into per-host capability JSON |  |
| Kernel + packages + opportunistic capability sniff | Universal core also runs short opportunistic probe for vulkaninfo/nvidia-smi/zpool |  |

**User's choice:** Kernel + package fingerprint.

---

## Area: Package Fingerprint Algorithm

**Question:** When the package fingerprint runs on a dpkg/rpm host, what does it actually capture?

| Option | Description | Selected |
|--------|-------------|----------|
| Opaque digest of full package list (Recommended) | sha256(`dpkg -l`) — change-detection only, no per-package detail in default report | ✓ |
| Named-subset of interesting packages with versions | Probe pve-kernel, proxmox-ve, nvidia-driver, libvulkan1, etc., store as map |  |
| Both — digest + named subset | Universal core captures both an opaque digest and a named subset |  |

**User's choice:** Opaque digest of full package list.

---

## Area: Cross-OS Handling (clarifying re-ask)

**Question (initial):** Cross-OS handling for the universal core — what runs on TrueNAS Core (FreeBSD), RHEL, or Alpine?

| Option | Description |
|--------|-------------|
| Debian/Proxmox happy path; NULL elsewhere (Recommended) | Probe code attempts dpkg only; non-Debian hosts get fields absent |
| OS-detection branching | Read /etc/os-release; branch by distro family (dpkg → rpm → apk → pkg) |
| Distro-tagged fingerprint structure | `package_fingerprint = {distro, digest, package_count}` — diff gated on same-distro |

**User's clarification (free-text):** "For this we could leve it up to the agent to use the ssh tool to make a call and figure it out we dont' need explizitly for a os or assume a defautl os. So we can do a uname call but if failes then tell the agent to use the ssh tool to get the data we are just looking for two strings at athis point OS namea and version."

**Interpretation locked:** Probe code does the Linux/Debian happy path. Universal core captures: `uname -s` (kernel_name), `uname -r` (kernel_version), `/etc/os-release` (os_name + os_version), `dpkg -l | sha256sum` (package_fingerprint). On non-Debian hosts, missing fields trigger Phase 35's `partial: True` flag and stay absent. Cross-OS coverage is delivered by the agent at runtime via `ssh_execute_command` — no distro branching in code.

---

## Area: Universal-Core OS-String Probe

**Question:** What does discovery code try (before any agent gap-fill)?

| Option | Description | Selected |
|--------|-------------|----------|
| `/etc/os-release` PRETTY_NAME + uname (Recommended) | Probe os-release for os_name + os_version; uname -s/-r for kernel_name + kernel_version | ✓ |
| Just `uname -s -r` | Universal core stores only kernel; os_name/os_version 100% agent-driven |  |
| `/etc/os-release` only — drop uname | Reuse existing os_info path; pull kernel from BUILD_ID with fallback |  |

**User's choice:** `/etc/os-release` PRETTY_NAME + uname.

---

## Area: Persistence Path

**Question:** How does the agent persist the gap-fill data it collects via `ssh_execute_command`?

| Option | Description | Selected |
|--------|-------------|----------|
| New `update_device_fingerprint` MCP tool (Recommended) | Phase 38 ships a new tool; agent calls after ssh_execute_command; deep-merge on capabilities | ✓ |
| Extend `discover_and_map` with `extra_fingerprint` param | Agent makes follow-up discover_and_map call with extra data |  |
| No persistence path — agent gap-fill stays in-conversation | Phase 38 ships only universal core capture; per-host capability tracking deferred |  |

**User's choice:** New `update_device_fingerprint` MCP tool.

---

## Area: Instruction Location

**Question:** Where does the 'agent asks per host what to track + uses ssh_execute_command for gap-fill' instruction live in the codebase?

| Option | Description | Selected |
|--------|-------------|----------|
| New MCP prompt template (Recommended if persistence is wired) | Add `configure_host_fingerprint` to prompt_registry.py; mirrors Phase 14 pattern | ✓ |
| Extend `connect_to_device` prompt | Add fingerprint-config steps to existing onboarding prompt |  |
| Tool description text only | Add instruction to tool descriptions; no prompt template |  |

**User's choice:** New MCP prompt template.

---

## Claude's Discretion

Captured in CONTEXT.md §Implementation Decisions §Claude's Discretion:
- Exact column / tool / prompt naming.
- Whether `update_device_fingerprint_preview` ships in Phase 38 (recommended) or follow-up.
- Adapter strategy for `update_device_fingerprint` (dedicated method vs piggyback on store_device).
- Exact role-hint inference rules in the prompt body.
- Whether `parse_discovery_output` stores `fingerprint` as JSON string (recommended) or already-deserialized dict.
- Whether `os_info` is deprecated alongside the new `fingerprint.os_name` / `fingerprint.os_version` (recommended: keep indefinitely).
- Test class naming conventions.

---

## Deferred Ideas

Captured in CONTEXT.md §Deferred Ideas:
- Per-VM / per-LXC fingerprints (v1.7.1 LIFE-*).
- Lifecycle-hook integration at VM/LXC/Proxmox-script touchpoints (v1.7.1).
- Role tags + role-driven default probe profiles (v1.7.2 TAGS-* / ROLE-*).
- Auto-detect drift via background polling (already out of scope at milestone level).
- CVE / pending-update advisory lookup (backlog 999.9).
- Auto-update sitemap when drift detected (out of scope at milestone level).
- `unsupported` sentinel for absent tools (chose simpler `partial: True` path).
- Cross-distro probe branching in code (chose agent-driven gap-fill).
- Per-package version tracking inside `package_fingerprint` (chose opaque digest).
- Deprecating `os_info` once new fields stabilize (back-compat indefinitely in Phase 38).
- SQL convenience views over `fingerprint` JSON.
- Schema validation for `capabilities` sub-keys (freeform in Phase 38).
- Agent retry / backoff on `update_device_fingerprint` failures.
