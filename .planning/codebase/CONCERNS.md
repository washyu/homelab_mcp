# CONCERNS - Technical Debt, Security & Issues

## Security Concerns

### SSH Host Key Verification Disabled (HIGH)
- **19 instances** across `ssh_tools.py`, `vm_operations.py`, `infrastructure_crud.py`, `shell_session.py`
- All SSH connections use `known_hosts=None`, disabling host key verification
- **Risk**: Vulnerable to man-in-the-middle attacks
```python
async with asyncssh.connect(hostname, username="mcp_admin", known_hosts=None) as conn:
```
- **Recommendation**: Implement known_hosts management, at minimum log host key fingerprints

### Proxmox SSL Verification Disabled by Default (MEDIUM)
- **File**: `src/homelab_mcp/proxmox_api.py:24`
- `verify_ssl: bool = False` - SSL verification off by default
- **Recommendation**: Default to `True`, override only for development

### API Key Validation Not Enforced (LOW)
- **File**: `src/homelab_mcp/auth.py:141-155`
- `validate_api_key_strength()` exists but is not called by default
- **Recommendation**: Always validate key strength on setup

## Technical Debt

### Stub Functions Not Implemented
1. **`_update_sitemap_after_deployment()`** - `infrastructure_crud.py:757`
   - Called after deployments but body is just `pass`
   - Sitemap not updated when new infrastructure is deployed

2. **`_rediscover_device_after_config()`** - `infrastructure_crud.py:952`
   - Called after config changes but body is just `pass`
   - Device info not refreshed after configuration updates

3. **`_install_with_script()`** - `service_installer.py:464`
   - Returns error: "Script-based installation not yet implemented"
   - Only Terraform and Ansible installation methods work

### Silent Exception Handling (9 instances)
- **Files**: `migration.py`, `http_transport.py`, `database.py`, `ssh_tools.py`, `sitemap.py`, `service_installer.py`
- Several `except` blocks with just `pass` - failures silently swallowed
- Most are intentional fallbacks (JSON parse errors, cleanup code)
- **Recommendation**: Add debug-level logging to aid troubleshooting

## Performance Issues

### HTTP Client Not Pooled (MEDIUM)
- **File**: `src/homelab_mcp/proxmox_api.py:113-114`
- New `aiohttp.ClientSession` + `TCPConnector` created for every Proxmox API request
- **Impact**: No connection reuse, TCP handshake overhead on each call
- **Recommendation**: Store session as instance variable, reuse across requests

### Database Connection Per Operation (LOW)
- **File**: `src/homelab_mcp/ssh_tools.py:67-70`
- Database opened, queried, and closed for each credential lookup
- **Recommendation**: Use connection pooling or persistent connections

## Fragile Areas

### `infrastructure_crud.py` (1,513 lines)
- Largest module in codebase with complex deployment logic
- Multiple stub functions that are called but do nothing
- Heavy reliance on SSH connections that could timeout

### `service_installer.py` (1,497 lines)
- Second largest module
- Supports 3 installation methods but one (script) is a stub
- Template loading depends on hardcoded directory path

### `ssh_tools.py` (1,126 lines)
- Core SSH functionality with 7 disabled host key verifications
- Complex hardware detection parsing that could break with OS variations

## Scaling Limitations

### SQLite Single-Writer
- SQLite used by default - single writer, no concurrent write support
- PostgreSQL adapter exists but less tested
- **Recommendation**: Document when to switch to PostgreSQL

### No Rate Limiting
- No rate limiting on tool execution or SSH connections
- Rapid tool calls could overwhelm target infrastructure
- **Recommendation**: Add rate limiting for SSH operations

### In-Memory Session State
- Shell sessions managed in memory (`shell_session.py`)
- Lost on server restart, no persistence
- **Recommendation**: Document limitation, consider session recovery

## Missing Features

### Input Validation
- Tool arguments validated by JSON schema but limited semantic validation
- No validation of hostnames, IP addresses, or port ranges at application level

### Audit Logging
- Standard Python logging used but no audit trail for infrastructure changes
- No record of who executed what tool and when

### Connection Cleanup
- No explicit cleanup of stale SSH connections
- No health checking of managed infrastructure

## Test Coverage Gaps
- WebSocket shell sessions - minimal testing
- Stub functions - not tested (they're just `pass`)
- Proxmox integration - limited to API mocking
- `server.py` tool dispatch - complex paths less covered

## Risk Summary

| Category | Severity | Count |
|----------|----------|-------|
| SSH host key verification disabled | HIGH | 19 instances |
| Proxmox SSL verification off by default | MEDIUM | 1 instance |
| HTTP client not pooled | MEDIUM | 1 instance |
| Stub functions not implemented | MEDIUM | 3 functions |
| Silent exception handling | LOW | 9 instances |
| Database connection not pooled | LOW | 1 pattern |
