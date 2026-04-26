---
status: partial
phase: 38-sitemap-fingerprint-schema
source: [38-VERIFICATION.md]
started: 2026-04-26T18:31:55Z
updated: 2026-04-26T18:31:55Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Agent invocation of `configure_host_fingerprint` prompt produces a coherent per-host conversation
expected: Agent reads sitemap, infers role hints (Proxmox VE → gpu_passthrough; NVIDIA → cuda; AMD VGA → vulkan; TrueNAS/ZFS → zfs), asks user, runs `ssh_execute_command` for follow-ups, and persists via `update_device_fingerprint`. Re-running `get_network_sitemap` shows `fingerprint.capabilities` populated with the agreed entries.
result: [pending]

### 2. End-to-end Docker integration test (`test_discover_populates_fingerprint_against_docker_phase38`)
expected: Test passes when run against a live Docker daemon (CI environment). Discovery → parse → store → get round-trip populates `fingerprint.kernel_name='Linux'`, non-empty `kernel_version`, non-empty `os_name`, `package_fingerprint` with `sha256:` prefix and 64-char lowercase hex digest.
result: [pending]

### 3. Cross-distro probe behavior (RHEL / Alpine / BSD)
expected: On Alpine (no dpkg), `partial:True` fires and `fingerprint.package_fingerprint` is absent (not stale). Other fingerprint keys (`kernel_name`, `kernel_version`, `os_name`) populate where the probe succeeds, OR are absent without partial enrollment (see WR-01 in 38-REVIEW.md — same pre-existing pattern as the legacy probes).
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
