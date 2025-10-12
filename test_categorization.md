# Test Categorization for MCP Python Server

This document categorizes all test files in the MCP Python Server project to provide a clear understanding of test organization, coverage, and purpose.

## Test Categories Overview

The tests are organized into three main categories:

1. **Unit Tests** - Test individual components in isolation with mocked dependencies
2. **Integration Tests** - Test components working together, potentially with real external dependencies
3. **End-to-End Tests** - Full workflow tests with real systems

## Test File Categories

### Unit Tests (8 files)

**Location:** `tests/`

These tests use mocking extensively to isolate components and test functionality without external dependencies.

#### 1. `test_database.py`
- **Purpose:** Tests database abstraction layer and adapters
- **Components:** SQLiteAdapter, PostgreSQLAdapter, DatabaseConfig, database factory functions
- **Mocking:** In-memory SQLite, mocked PostgreSQL connections
- **Key Features:**
  - Schema initialization
  - Device storage/retrieval
  - Discovery history management
  - Database adapter factory functionality

#### 2. `test_server.py`
- **Purpose:** Tests MCP server protocol handling and endpoint responses
- **Components:** HomelabMCPServer class
- **Mocking:** SSH key generation, tool execution, health monitoring
- **Key Features:**
  - Server initialization with SSH key setup
  - Tools listing (34 tools total)
  - JSON-RPC protocol handling
  - Error handling for unknown methods/tools
  - Health monitoring and timeout handling
  - Exception handling with structured responses

#### 3. `test_error_handling.py`
- **Purpose:** Tests error handling decorators and utilities
- **Components:** Timeout wrapper, retry decorator, SSH connection wrapper, health checker
- **Mocking:** Async operations, connection failures, timeouts
- **Key Features:**
  - Timeout wrapper with structured error responses
  - Retry mechanism with exponential backoff
  - SSH-specific error handling and suggestions
  - Health monitoring and metrics collection
  - Custom exception types (MCPTimeout, MCPConnectionError)

#### 4. `test_sitemap.py`
- **Purpose:** Tests network sitemap functionality and device management
- **Components:** NetworkSiteMap, NetworkDevice, discovery functions
- **Mocking:** In-memory database, SSH discovery data
- **Key Features:**
  - Discovery output parsing (success and error cases)
  - Device storage with duplicate detection
  - Network topology analysis
  - Deployment suggestions based on device specs
  - Change history tracking

#### 5. `test_ssh_tools.py`
- **Purpose:** Tests SSH operations and system discovery
- **Components:** SSH discovery, key management, admin setup
- **Mocking:** AsyncSSH connections, command execution results
- **Key Features:**
  - System discovery with hardware information collection
  - Authentication methods (password, SSH keys)
  - Error handling for connection failures and timeouts
  - CPU, memory, disk, network, and OS detection

#### 6. `test_tools.py`
- **Purpose:** Tests MCP tool registration and execution framework
- **Components:** Tool registry, execution dispatcher
- **Mocking:** SSH tools, sitemap operations, infrastructure functions
- **Key Features:**
  - Available tools listing (34 tools including SSH, sitemap, infrastructure, VM, service, and Ansible)
  - Tool execution with parameter validation
  - Structured error responses for unknown tools
  - Integration with various tool categories

#### 7. `test_infrastructure_crud.py`
- **Purpose:** Tests infrastructure management and CRUD operations
- **Components:** InfrastructureManager, deployment functions
- **Mocking:** Sitemap queries, SSH connections, service deployments
- **Key Features:**
  - Device connection information retrieval
  - Infrastructure plan validation and deployment
  - Configuration updates and rollback operations
  - Service scaling and decommissioning

#### 8. `test_service_installer.py`
- **Purpose:** Tests service installation and requirement checking
- **Components:** ServiceInstaller class
- **Mocking:** YAML template files, SSH command execution
- **Key Features:**
  - Service template loading from YAML files
  - Requirement validation (ports, memory, disk space)
  - Docker Compose and ISO installation methods
  - Resource conflict detection

### VM Operations Unit Tests (2 files)

#### 9. `test_vm_operations.py`
- **Purpose:** Tests VM management operations
- **Components:** VMManager, VM deployment/control functions
- **Mocking:** Sitemap connections, VM providers, SSH connections
- **Key Features:**
  - VM deployment across different platforms
  - VM state control (start, stop, restart)
  - Status monitoring and log retrieval
  - Multi-platform support coordination

#### 10. `test_vm_providers.py`
- **Purpose:** Tests VM provider implementations
- **Components:** Docker and LXD providers
- **Mocking:** SSH connections, container/VM commands
- **Key Features:**
  - Docker container lifecycle management
  - LXD container operations
  - Provider factory pattern
  - Platform-specific command execution

### Integration Tests (2 files)

**Location:** `tests/integration/`

These tests involve real components working together, though still using some mocking for external dependencies.

#### 11. `test_sitemap_integration.py`
- **Purpose:** Integration tests for complete sitemap workflows
- **Components:** Full sitemap workflow with database and discovery
- **Dependencies:** In-memory database, Docker containers (for E2E scenarios)
- **Key Features:**
  - Complete discover-store-analyze workflow
  - MCP tool integration testing
  - Bulk discovery operations
  - Real SSH connections to test containers

#### 12. `test_ssh_integration.py`
- **Purpose:** Integration tests for SSH functionality with real connections
- **Components:** SSH operations with actual containers
- **Dependencies:** Docker test containers with SSH servers
- **Key Features:**
  - Real SSH key generation and management
  - Complete mcp_admin setup workflow
  - Authentication method testing
  - Container-based SSH server interactions

## Test Configuration and Fixtures

### Common Fixtures
- **Database fixtures:** In-memory SQLite for fast, isolated testing
- **Mock fixtures:** SSH connections, command results, JSON responses
- **Container fixtures:** Docker containers for integration testing
- **Temporary files:** Service templates and configuration files

### Test Markers
- `@pytest.mark.asyncio` - For async function testing
- `@pytest.mark.integration` - For integration tests requiring external dependencies

### External Dependencies for Integration Tests
- **Docker:** Required for container-based integration tests
- **PostgreSQL:** Optional, for database integration tests (currently mocked in unit tests)
- **SSH servers:** Test containers with SSH access

## Test Coverage Areas

### Core Functionality Tested
1. **Database Operations:** Schema management, CRUD operations, query optimization
2. **SSH Operations:** Connection handling, authentication, command execution
3. **Network Discovery:** System information gathering, parsing, storage
4. **Infrastructure Management:** Service deployment, configuration management
5. **VM Operations:** Container/VM lifecycle management across platforms
6. **Error Handling:** Timeout handling, retry logic, structured error responses
7. **MCP Protocol:** JSON-RPC handling, tool registration, response formatting

### Integration Workflows Tested
1. **Complete Discovery Workflow:** SSH discover → parse → store → analyze
2. **Admin Setup Workflow:** Key generation → user creation → access verification
3. **Service Installation:** Requirements check → template processing → deployment
4. **VM Management:** Provider selection → deployment → control → monitoring

## Test Execution Patterns

### Unit Test Characteristics
- **Fast execution:** Heavy use of mocking for speed
- **Isolated testing:** No external dependencies
- **Comprehensive coverage:** Test both success and failure scenarios
- **Structured responses:** Consistent JSON response format testing

### Integration Test Characteristics
- **Real component interaction:** Actual database and SSH operations
- **Container dependencies:** Docker containers for realistic environments
- **Workflow validation:** End-to-end process verification
- **Environment setup:** Fixture-based test environment preparation

## Testing Best Practices Implemented

1. **Fixture Reuse:** Common database and connection fixtures
2. **Mock Strategy:** Strategic mocking of external dependencies in unit tests
3. **Error Scenarios:** Comprehensive error condition testing
4. **Async Testing:** Proper async/await pattern testing
5. **Resource Cleanup:** Proper teardown in integration tests
6. **Realistic Data:** Sample data that mirrors real system outputs

## Recommendations for Test Maintenance

1. **Unit tests should remain isolated** - Avoid real external dependencies
2. **Integration tests should use containers** - Consistent, reproducible environments
3. **Mock realistic data** - Use actual command outputs and response formats
4. **Test error conditions** - Ensure robust error handling across all components
5. **Maintain fixture consistency** - Keep test fixtures up-to-date with real data formats

This categorization shows a well-structured test suite with clear separation between unit and integration tests, comprehensive coverage of core functionality, and proper use of mocking strategies for maintainable and reliable testing.
