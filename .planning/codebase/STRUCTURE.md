# STRUCTURE - Directory Layout & Organization

## Directory Tree

```
mcp_python_server/
├── src/homelab_mcp/                 # Main package (~11.9K LOC)
│   ├── server.py                    # MCP server main entry (311 lines)
│   ├── tools.py                     # Tool registry and execution
│   ├── error_handling.py            # Timeout/retry decorators (351 lines)
│   ├── http_transport.py            # HTTP/WebSocket transport layer (439 lines)
│   ├── auth.py                      # API key auth middleware
│   ├── config.py                    # Configuration management
│   ├── __init__.py
│   │
│   ├── ssh_tools.py                 # SSH discovery & hardware detection (1,126 lines)
│   ├── shell_session.py             # Interactive shell sessions
│   │
│   ├── database.py                  # SQLite/PostgreSQL adapters (1,122 lines)
│   ├── migration.py                 # Database schema migrations (462 lines)
│   │
│   ├── sitemap.py                   # Network device tracking (367 lines)
│   ├── infrastructure_crud.py       # CRUD lifecycle management (1,513 lines)
│   │
│   ├── vm_operations.py             # VM management across platforms
│   ├── vm_providers/                # VM platform plugins
│   │   ├── base.py                  # Abstract base class
│   │   ├── docker_provider.py       # Docker provider
│   │   └── lxd_provider.py          # LXD provider (306 lines)
│   │
│   ├── service_installer.py         # Service installation (1,497 lines)
│   ├── service_templates/           # YAML service configs (10 templates)
│   │   ├── homeassistant.yaml
│   │   ├── k3s.yaml
│   │   ├── ollama.yaml
│   │   ├── pihole.yaml
│   │   ├── jellyfin.yaml
│   │   ├── truenas.yaml
│   │   ├── docker_terraform.yaml
│   │   ├── pihole_terraform.yaml
│   │   ├── ollama_ansible.yaml
│   │   └── ai_homelab_stack_ansible.yaml
│   │
│   ├── proxmox_api.py               # Proxmox REST API client (642 lines)
│   ├── proxmox_scripts.py           # Script management (338 lines)
│   │
│   ├── tool_handlers/               # Handler implementations
│   │   ├── __init__.py              # Handler registry (142 lines)
│   │   ├── ssh_handlers.py
│   │   ├── network_handlers.py
│   │   ├── vm_handlers.py
│   │   ├── service_handlers.py
│   │   ├── infrastructure_handlers.py
│   │   ├── credential_handlers.py
│   │   └── proxmox_handlers.py
│   │
│   └── tool_schemas/                # Tool JSON schema definitions
│       ├── __init__.py              # Schema registry
│       ├── ssh_tools_schema.py
│       ├── network_tools_schema.py
│       ├── vm_tools_schema.py
│       ├── service_tools_schema.py
│       ├── infrastructure_tools_schema.py
│       ├── credential_tools_schema.py
│       └── proxmox_tools_schema.py
│
├── tests/                           # Test suite (~9K LOC, 386 tests)
│   ├── test_*.py                    # 20 unit test files
│   └── integration/                 # Integration tests (Docker required)
│       ├── conftest.py              # Fixtures and Docker setup
│       ├── docker_client_factory.py
│       ├── test_ssh_integration.py
│       ├── test_full_stack_integration.py
│       ├── test_sitemap_integration.py
│       └── test_proxmox_integration.py
│
├── scripts/                         # Utility scripts
│   ├── quality-check.sh             # Code quality runner
│   ├── run_tests.py                 # Test runner
│   ├── run-integration-tests.sh
│   ├── db_manager.py                # Database management
│   └── check_vscode_environment.py
│
├── docker/                          # Docker configs
│   └── test-ubuntu/                 # Test container definitions
│
├── systemd/                         # systemd service files
├── certs/                           # SSL certificates
├── docs/                            # Documentation
│
├── pyproject.toml                   # uv/pytest/mypy/ruff config
├── pytest.ini                       # Pytest markers
├── docker-compose.yml
├── docker-compose.test.yml
├── Dockerfile
├── .pre-commit-config.yaml
├── .env.example
├── CLAUDE.md                        # Project guidelines
└── CONTRIBUTING.md
```

## Key File Locations

### Entry Points
- `run_server.py` - Server startup script
- `src/homelab_mcp/server.py` - MCP server with JSON-RPC protocol handling

### Tool System
- `src/homelab_mcp/tool_schemas/` - Tool definitions with JSON schema
- `src/homelab_mcp/tool_handlers/` - Handler implementations per domain
- `src/homelab_mcp/tools.py` - Registry and execution dispatcher

### Core Business Logic
- `src/homelab_mcp/ssh_tools.py` - SSH discovery, hardware detection, key management
- `src/homelab_mcp/infrastructure_crud.py` - Full infrastructure lifecycle (deploy/update/decommission)
- `src/homelab_mcp/service_installer.py` - Service installation via Terraform/Ansible/Docker
- `src/homelab_mcp/vm_operations.py` - VM management across providers

### Data Layer
- `src/homelab_mcp/database.py` - Abstract adapter + SQLite/PostgreSQL implementations
- `src/homelab_mcp/migration.py` - Schema versioning and migrations
- `src/homelab_mcp/sitemap.py` - Network device mapping and topology

### Configuration & Cross-cutting
- `src/homelab_mcp/config.py` - Environment-based config classes
- `src/homelab_mcp/error_handling.py` - Timeout/retry decorators, JSON error responses
- `src/homelab_mcp/auth.py` - API key authentication middleware

## Naming Conventions

| Element | Convention | Examples |
|---------|-----------|----------|
| Files/modules | snake_case | `ssh_tools.py`, `vm_operations.py` |
| Classes | PascalCase | `HomelabMCPServer`, `NetworkSiteMap`, `DatabaseAdapter` |
| Functions | snake_case | `ssh_discover_system()`, `deploy_infrastructure()` |
| Handler functions | `handle_` prefix | `handle_ssh_discover()`, `handle_deploy_vm()` |
| Constants | SCREAMING_SNAKE_CASE | `SSH_KEY_DIR`, `TOOL_HANDLERS` |
| Tool names | snake_case | `ssh_discover`, `setup_mcp_admin`, `get_network_sitemap` |
| Test files | `test_` prefix | `test_ssh_tools.py`, `test_database.py` |

## Adding New Components

### Adding a New Tool
1. Define schema in `src/homelab_mcp/tool_schemas/{category}_tools_schema.py`
2. Implement handler in `src/homelab_mcp/tool_handlers/{category}_handlers.py`
3. Register in handler `__init__.py` and schema `__init__.py`
4. Write tests in `tests/test_{module}.py`

### Adding a VM Provider
1. Create `src/homelab_mcp/vm_providers/{name}_provider.py`
2. Extend `VMProviderBase` from `base.py`
3. Implement all abstract methods
4. Register in `vm_operations.py`

### Adding a Service Template
1. Create YAML file in `src/homelab_mcp/service_templates/{name}.yaml`
2. Define installation method (terraform/ansible/docker)
3. Include required variables and configuration
