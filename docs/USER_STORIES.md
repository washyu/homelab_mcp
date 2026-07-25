# Homelab MCP Server: User Stories

**Status:** Draft for review
**Date:** 2026-06-27
**Scope:** Homelab focused user stories covering all 57 registered MCP tools, plus a list of
capability gaps for the risk and recommendation features we want but do not fully have yet.

## Who this is for

This is for one person running a homelab, not a company. Picture a setup like:

- A **router / firewall** (OPNsense, pfSense, or a UniFi box).
- A **Pi-hole** on a Raspberry Pi for DNS and ad blocking.
- A **TrueNAS** box for storage.
- A **Proxmox** server running a handful of LXC containers and VMs (Home Assistant, a media
  stack, an Arr stack, a small database, that sort of thing).

These are mostly pets, set up by hand over time, half remembered, and rarely all healthy at
once. The whole point of this tool is to let an AI agent log into everything, figure out
what is there, write it down, and then tell you what is wrong or missing.

There are two situations the same owner is in at different times:

- **Existing homelab:** "I have a pile of boxes. Go look at all of them, tell me what I have
  and what I should worry about."
- **New build:** "I just set up a fresh machine (or a fresh Proxmox node). Help me see what
  I have and suggest what to put on it."

Throughout, "the owner" or "I" means that one person. Stories use real homelab examples
rather than abstract roles.

## The core loop

Most of the value is one loop, and the epics below follow it:

1. **Survey** every box and Proxmox guest, however it is reachable.
2. **Catalog** what was found into a single inventory.
3. **Assess** health and risk: out of date, exposed to the internet, drifted, or down.
4. **Recommend** what is missing and where new things should go.
5. **Act** safely: provision, install, change, and recover.

## Epic index

1. Survey and Catalog the Whole Homelab
2. Get the Agent Access to Each Box
3. Health and Risk Review (the advisor)
4. Recommendations: What Is Missing and Where It Should Go
5. Provision and Install
6. Everyday Operation and Troubleshooting
7. Change Safely and Recover

A cross-cutting theme, **Look before you wreck it (previews)**, applies to every
destructive action and is summarized before the appendix.

---

## Epic 1: Survey and Catalog the Whole Homelab

**Goal:** point the agent at the homelab and end up with one honest inventory of every box
and every Proxmox guest, with current state.

### SURVEY-1: Look at a standalone box and learn what it is
**As** the owner, **I want** the agent to SSH into a single machine (the Pi-hole, the
TrueNAS box, the router if it allows it) and report its hardware, OS, and basics, **so
that** I know what that box actually is without logging in myself.

Acceptance criteria:
- Given a hostname and credentials (or stored credentials), it returns CPU, memory, disk,
  OS, and network details.
- If it cannot reach the box, it says so clearly with host and port, and does not hang.
- It works on a plain Linux box, not just Proxmox.

Backing tool: `ssh_discover`

### SURVEY-2: Add each box to the inventory
**As** the owner, **I want** each discovered box saved into a single catalog, **so that**
the homelab is written down in one place instead of in my head.

Acceptance criteria:
- A discovered box is fingerprinted and stored.
- Re-running on the same box updates its record instead of creating a duplicate.

Backing tool: `discover_and_map`

### SURVEY-3: Catalog several boxes in one go
**As** the owner, **I want** to hand the agent a list of hosts (or a subnet) and have it
discover and catalog all of them at once, **so that** I can survey the whole homelab in one
request instead of one box at a time.

Acceptance criteria:
- Each host is handled independently; one unreachable box does not abort the rest.
- The result summarizes what was found and what failed, per host.

Backing tool: `bulk_discover_and_map`

### SURVEY-4: See the whole catalog at once
**As** the owner, **I want** to pull up everything that has been discovered, **so that** I
have a single view of the homelab: the router, the Pi, the NAS, the Proxmox node, and its
guests.

Acceptance criteria:
- It lists every cataloged box with its key attributes.
- An empty catalog returns an explicit empty result, not an error.

Backing tool: `get_network_sitemap`

### SURVEY-5: See everything running on the Proxmox node
**As** the owner, **I want** the agent to enumerate the Proxmox node and all its VMs,
containers, and storage, **so that** the half dozen guests I forgot about show up in the
inventory too.

Acceptance criteria:
- It lists VMs, containers, nodes, and storage on the cluster.
- It uses the configured `PROXMOX_HOST` when I do not pass one.

Backing tools: `list_proxmox_resources`, `get_proxmox_node_status`, `get_proxmox_vm_status`,
`list_vms`, `get_vm_status`

### SURVEY-6: Know which boxes the agent already has on file
**As** the owner, **I want** to see which servers are already registered and whether they
are reachable right now, **so that** I know what the agent can get to before it tries.

Backing tool: `list_registered_servers`

---

## Epic 2: Get the Agent Access to Each Box

**Goal:** set up access once, store it safely, and not retype passwords. Casual homelab
reality: mixed credentials, some boxes with key auth, some with a password I set two years
ago.

### ACCESS-1: Save a box's login once
**As** the owner, **I want** to register a box with its SSH login a single time, **so that**
the agent reconnects later without me pasting the password again.

Acceptance criteria:
- The login is stored in the OS keyring, not in a plaintext file.
- The secret value is never echoed back in any listing.

Backing tool: `register_server`

### ACCESS-2: Set up a consistent admin login on a box
**As** the owner, **I want** the agent to create an `mcp_admin` user with sudo and key based
SSH on a box, **so that** future automation uses one clean key based identity instead of my
personal password.

Acceptance criteria:
- It creates `mcp_admin`, installs the key, and grants admin rights.
- Running it again on an already set up box is safe and reports the existing state.

Backing tool: `setup_mcp_admin`

### ACCESS-3: Confirm the agent can still get in
**As** the owner, **I want** to verify key based `mcp_admin` access works on a box, **so
that** I find out access is broken before I rely on it during a change.

Backing tool: `verify_mcp_admin`

### ACCESS-4: Give the admin the group access a service needs
**As** the owner, **I want** `mcp_admin` added to the right groups (docker, lxd, libvirt,
kvm) when I install something, **so that** service automation has the permissions it needs
without me editing groups by hand.

Backing tool: `update_mcp_admin_groups`

### ACCESS-5: Rotate or fix a saved login
**As** the owner, **I want** to update the stored credentials for a box, **so that** when I
change a password the agent does not get locked out.

Backing tool: `update_server_credentials`

### ACCESS-6: Clean up access for a box I got rid of
**As** the owner, **I want** to remove a box and its stored login, with a preview of what
will be removed, **so that** a decommissioned Pi does not leave a stale secret behind.

Backing tools: `remove_server`, `remove_server_preview`

### ACCESS-7: See what secrets are stored
**As** the owner, **I want** to list the credentials held in the keyring, **so that** I can
audit what the agent has and clear out stale entries.

Backing tool: `list_keyring_credentials`

---

## Epic 3: Health and Risk Review (the advisor)

**Goal:** this is the part you most asked for. After surveying, the agent should tell me
what is wrong: boxes that need updates, things exposed to the internet, configuration that
has drifted, and guests that are down.

Note: some of these checks are not backed by a dedicated tool yet. Where that is the case
the story still belongs here, and the gap is recorded in Appendix B so we can decide whether
to build a real tool or keep doing it through `ssh_execute_command`.

### RISK-1: Flag boxes that need updates
**As** the owner, **I want** the agent to check each box for pending OS and package updates,
**so that** I get a list like "the Pi-hole has 14 updates including a kernel, TrueNAS is
current, the Proxmox node has updates pending."

Acceptance criteria:
- For each reachable box it reports whether updates are pending and, ideally, how many and
  whether a reboot is implied.
- It is honest about boxes it could not check.

Backing tool: `ssh_execute_command` (runs the per-OS update check today).
Gap: there is no dedicated "check updates" tool that normalizes this across Debian, TrueNAS,
and Proxmox. See Appendix B.

### RISK-2: Flag anything exposed to the internet
**As** the owner, **I want** the agent to point out services or boxes that look reachable
from the internet or are listening on risky ports, **so that** I do not accidentally leave
something open.

Acceptance criteria:
- It reports listening services and open ports per box.
- It calls out high risk exposure (for example SSH, a database, or an admin UI on a WAN
  facing interface).

Backing tool: `ssh_execute_command` (port and listener checks today).
Gap: no dedicated exposure or port scan tool, and no external "what does the internet see"
check. See Appendix B.

### RISK-3: Detect configuration drift
**As** the owner, **I want** the agent to notice when a Proxmox guest's CPU, memory, or
network changed outside this tool, or when a guest that should be running is off, **so that**
surprises do not pile up silently.

Acceptance criteria:
- Findings separate config drift (resources changed) from state drift (a guest is off that
  should be on).
- Each finding includes what was expected, what is actual, and when it was seen.
- I can scan one node or everything.

Backing tool: `scan_infrastructure_drift`

### RISK-4: Notice service level drift
**As** the owner, **I want** the agent to tell me when a Terraform or Ansible managed
service no longer matches its declared config, **so that** hand edits on a box get caught.

Backing tools: `refresh_terraform_service`, `check_ansible_service`

### RISK-5: Check whether a service is actually up
**As** the owner, **I want** to ask whether an installed service is running, **so that** I
can confirm Pi-hole or Home Assistant is actually serving and not quietly dead.

Backing tool: `get_service_status`

### RISK-6: See what changed on a box and when
**As** the owner, **I want** the change history for a specific box, **so that** when
something breaks I can see what changed recently.

Backing tool: `get_device_changes`

### RISK-7: Read logs from a guest that is misbehaving
**As** the owner, **I want** to pull logs from a VM or container, **so that** I can see why
it is unhealthy without opening a shell.

Backing tools: `get_vm_logs`, `get_vm_status`

---

## Epic 4: Recommendations: What Is Missing and Where It Should Go

**Goal:** the other half of what you asked for. Once the homelab is cataloged, the agent
should suggest useful things I do not have and tell me which box should host them.

### REC-1: Summarize the homelab and spot gaps
**As** the owner, **I want** the agent to analyze the whole catalog and give me insights,
**so that** I get observations like "you have no off-site backup," "nothing is doing
monitoring," or "the Proxmox node is the single point of failure for DNS."

Acceptance criteria:
- The analysis summarizes capacity and roles across the cataloged boxes.
- It points to the boxes behind each observation.

Backing tool: `analyze_network_topology`
Gap: the "you are missing service X" framing leans on analysis and on the service catalog;
how opinionated the suggestions are is something to define. See Appendix B.

### REC-2: Suggest where to put a new workload
**As** the owner, **I want** placement suggestions for something new (say a new LXC for
Jellyfin), **so that** I put it on a box that actually has the room and the right role.

Acceptance criteria:
- Suggestions are based on the current catalog and each box's capabilities.
- Each suggestion explains why (free memory, role fit, and so on).

Backing tool: `suggest_deployments`

### REC-3: Browse what can be installed
**As** the owner, **I want** to see the catalog of services the tool can install, **so
that** I know my options when filling a gap.

Backing tools: `list_available_services`, `get_service_info`

### REC-4: Check a box can handle a service before I commit
**As** the owner, **I want** to check whether a target box meets a service's requirements,
**so that** I do not start an install that will fail halfway.

Backing tool: `check_service_requirements`

### REC-5: Find a community script for something
**As** the owner, **I want** to search the Proxmox community scripts and read what one does,
**so that** I can use a known installer for a service on Proxmox.

Backing tools: `search_proxmox_scripts`, `get_proxmox_script_info`

---

## Epic 5: Provision and Install

**Goal:** act on the recommendations: stand up a guest and install the service.

### MAKE-1: Create an LXC container on Proxmox
**As** the owner, **I want** to create a new LXC container, **so that** I can spin up a
lightweight service quickly.

Backing tool: `create_proxmox_lxc`

### MAKE-2: Create a full VM on Proxmox
**As** the owner, **I want** to create a new QEMU VM with the cores, memory, disk, and boot
media I choose, **so that** I can run something that needs a real VM.

Backing tool: `create_proxmox_vm`

### MAKE-3: Clone from a known good template
**As** the owner, **I want** to clone an existing guest, **so that** I can reuse a setup I
already trust instead of building from scratch.

Backing tool: `clone_proxmox_vm`

### MAKE-4: Deploy a guest on a chosen box (provider neutral)
**As** the owner, **I want** to deploy a VM or container on a specific box, **so that** the
same request works whether that box is Proxmox, libvirt, or Docker based.

Backing tool: `deploy_vm`

### MAKE-5: Install a service onto a box
**As** the owner, **I want** to install a service on a target box, **so that** the gap the
advisor found actually gets filled.

Backing tools: `install_service`, `run_ansible_playbook`, `plan_terraform_service`

### MAKE-6: Stand up several things from one plan
**As** the owner, **I want** to deploy a small set of resources from one plan (mine or the
agent's recommendation), **so that** a new build does not take a dozen separate requests.

Backing tool: `deploy_infrastructure`

### MAKE-7: Give a service more (or less) room
**As** the owner, **I want** to scale a service up or down, **so that** I can react when
something is starved or oversized.

Backing tool: `scale_services`

---

## Epic 6: Everyday Operation and Troubleshooting

**Goal:** the routine stuff: turn things on and off, poke a box, look around.

### OPS-1: Power a guest on, off, or restart
**As** the owner, **I want** to start, stop, shut down, reboot, reset, suspend, or resume a
guest, **so that** I can manage runtime without opening the Proxmox UI.

Backing tools: `manage_proxmox_vm`, `control_vm`

### OPS-2: Check a single guest's status
**As** the owner, **I want** detailed status for one VM or container, **so that** I can
confirm it is healthy.

Backing tools: `get_vm_status`, `get_proxmox_vm_status`

### OPS-3: List the guests on a box
**As** the owner, **I want** to list the VMs and containers on a box, **so that** I know
what is where.

Backing tool: `list_vms`

### OPS-4: Run a quick command on a box
**As** the owner, **I want** to run a one off command on a box over SSH, **so that** I can
check or fix something fast.

Acceptance criteria:
- Stored credentials are used automatically when available.
- It returns stdout, stderr, and the exit code.

Backing tool: `ssh_execute_command`

### OPS-5: Open a real shell when I need one
**As** the owner, **I want** a browser based terminal with full TTY on a box, **so that** I
can run interactive tools that need a proper shell.

Backing tool: `start_interactive_shell`

### OPS-6: Check the node's overall health
**As** the owner, **I want** CPU, memory, and uptime for the Proxmox node, **so that** I can
see if the host itself is under strain.

Backing tool: `get_proxmox_node_status`

---

## Epic 7: Change Safely and Recover

**Goal:** make changes without fear. Back up, validate, preview destructive actions, and roll
back when I get it wrong.

### SAFE-2: Back up before a risky change
**As** the owner, **I want** to capture the current infrastructure state, **so that** I have
a point to restore to if a change goes wrong.

Backing tool: `create_infrastructure_backup`

### SAFE-3: Validate a change before applying it
**As** the owner, **I want** to validate a proposed change first, **so that** I catch
problems while they are cheap.

Backing tool: `validate_infrastructure_changes`

### SAFE-4: Adjust a box's configuration
**As** the owner, **I want** to update an existing box's config, **so that** I can change
resources or settings without rebuilding it.

Backing tool: `update_device_config`

### SAFE-5: Roll back a change that went wrong
**As** the owner, **I want** to roll back recent changes, after previewing what the rollback
will revert, **so that** I can recover quickly.

Backing tools: `rollback_infrastructure_changes`, `rollback_infrastructure_changes_preview`

### SAFE-6: Retire a box cleanly
**As** the owner, **I want** to decommission a box, after previewing what depends on it, **so
that** retiring the old NAS does not leave dangling references or orphaned workloads.

Backing tools: `decommission_device`, `decommission_device_preview`

### SAFE-7: Tear down a guest or service safely
**As** the owner, **I want** to delete a Proxmox guest, remove a VM, or destroy a Terraform
service, each with a preview first, **so that** I never nuke the wrong thing.

Backing tools: `delete_proxmox_vm`, `delete_proxmox_vm_preview`, `remove_vm`,
`remove_vm_preview`, `destroy_terraform_service`, `destroy_terraform_service_preview`

---

## Cross-cutting theme: Look before you wreck it (previews)

Every destructive action has a paired `_preview`. The shared rule: a preview makes no
changes and shows the same scope the real action will affect.

Paired tools: `remove_server` / `remove_server_preview`, `remove_vm` / `remove_vm_preview`,
`delete_proxmox_vm` / `delete_proxmox_vm_preview`, `decommission_device` /
`decommission_device_preview`, `destroy_terraform_service` /
`destroy_terraform_service_preview`, `rollback_infrastructure_changes` /
`rollback_infrastructure_changes_preview`.

**SAFE-1: Preview before any destructive action**
**As** the owner, **I want** every destructive tool to offer a no-change preview, **so that**
I can confirm scope before committing.

Acceptance criteria:
- A preview changes nothing.
- The preview output matches what the live action will affect.

---

## Appendix A: Tool to story coverage index

Every registered tool maps to at least one story.

| Tool | Story |
| --- | --- |
| ssh_discover | SURVEY-1 |
| discover_and_map | SURVEY-2 |
| bulk_discover_and_map | SURVEY-3 |
| get_network_sitemap | SURVEY-4 |
| list_proxmox_resources | SURVEY-5 |
| get_proxmox_node_status | SURVEY-5, OPS-6 |
| get_proxmox_vm_status | SURVEY-5, OPS-2 |
| list_vms | SURVEY-5, OPS-3 |
| get_vm_status | SURVEY-5, OPS-2, RISK-7 |
| list_registered_servers | SURVEY-6 |
| register_server | ACCESS-1 |
| setup_mcp_admin | ACCESS-2 |
| verify_mcp_admin | ACCESS-3 |
| update_mcp_admin_groups | ACCESS-4 |
| update_server_credentials | ACCESS-5 |
| remove_server | ACCESS-6, SAFE-1 |
| remove_server_preview | ACCESS-6, SAFE-1 |
| list_keyring_credentials | ACCESS-7 |
| ssh_execute_command | RISK-1, RISK-2, OPS-4 |
| scan_infrastructure_drift | RISK-3 |
| refresh_terraform_service | RISK-4 |
| check_ansible_service | RISK-4 |
| get_service_status | RISK-5 |
| get_device_changes | RISK-6 |
| get_vm_logs | RISK-7 |
| analyze_network_topology | REC-1 |
| suggest_deployments | REC-2 |
| list_available_services | REC-3 |
| get_service_info | REC-3 |
| check_service_requirements | REC-4 |
| search_proxmox_scripts | REC-5 |
| get_proxmox_script_info | REC-5 |
| create_proxmox_lxc | MAKE-1 |
| create_proxmox_vm | MAKE-2 |
| clone_proxmox_vm | MAKE-3 |
| deploy_vm | MAKE-4 |
| install_service | MAKE-5 |
| run_ansible_playbook | MAKE-5 |
| plan_terraform_service | MAKE-5 |
| deploy_infrastructure | MAKE-6 |
| scale_services | MAKE-7 |
| manage_proxmox_vm | OPS-1 |
| control_vm | OPS-1 |
| start_interactive_shell | OPS-5 |
| create_infrastructure_backup | SAFE-2 |
| validate_infrastructure_changes | SAFE-3 |
| update_device_config | SAFE-4 |
| rollback_infrastructure_changes | SAFE-5, SAFE-1 |
| rollback_infrastructure_changes_preview | SAFE-5, SAFE-1 |
| decommission_device | SAFE-6, SAFE-1 |
| decommission_device_preview | SAFE-6, SAFE-1 |
| delete_proxmox_vm | SAFE-7, SAFE-1 |
| delete_proxmox_vm_preview | SAFE-7, SAFE-1 |
| remove_vm | SAFE-7, SAFE-1 |
| remove_vm_preview | SAFE-7, SAFE-1 |
| destroy_terraform_service | SAFE-7, SAFE-1 |
| destroy_terraform_service_preview | SAFE-7, SAFE-1 |

## Appendix B: Capability gaps (the advisor features we do not fully have)

These are the risk and recommendation stories that no single tool fully delivers today. They
matter because they are exactly what you described as the goal. We should decide for each
whether to build a real tool, or keep doing it ad hoc through `ssh_execute_command` plus
agent reasoning.

1. **Update checking (RISK-1).** No dedicated tool that checks pending updates and normalizes
   the answer across Debian/Ubuntu, TrueNAS, Proxmox, and router OSes. Today this is raw
   commands through `ssh_execute_command`, so results are inconsistent and there is nothing
   to test against.
2. **Internet exposure / port checks (RISK-2).** No tool that enumerates listening services,
   flags WAN facing ports, or checks what is reachable from outside. This is the highest
   value safety feature and currently does not exist as a first class capability.
3. **Opinionated "missing service" recommendations (REC-1).** `analyze_network_topology`
   gives capacity insights, but the "you should add backups / monitoring / a second DNS"
   layer is undefined. We need to decide how opinionated it should be and what the catalog of
   recommended baseline services is.
4. **A single "survey my whole homelab and report" entry point.** Right now surveying is
   several calls (discover, map, list Proxmox, scan drift, check updates). A guided workflow
   or one orchestrating tool would match how the owner actually thinks about it.

## Appendix C: Open questions for review

- Does the running example (router, Pi-hole, TrueNAS, Proxmox) match your actual setup, or
  should I swap in your real boxes so the stories read true?
- For the advisor (Epic 3 and Appendix B), do you want me to spec out real tools for update
  checking and exposure scanning, or keep those as agent-driven `ssh_execute_command`
  recipes?
- Should we add a single "full homelab health report" workflow as its own story and eventual
  tool, since that is closest to how you described the goal?
