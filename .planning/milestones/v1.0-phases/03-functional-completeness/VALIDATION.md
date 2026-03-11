# Phase 3: Functional Completeness Validation Strategy

## Validation Requirements

This phase requires validating that:
1. Sitemap reflects new devices automatically after deployment
2. Device info reflects updated state after configuration changes
3. Script-based service installation completes successfully
4. All exception handlers emit appropriate log messages (no bare except:pass)
5. Every tool has required hints (readOnlyHint, destructiveHint, idempotentHint)
6. All error responses include isError: true

## Validation Artifacts

### 1. Sitemap Auto-Refresh
- **Artifact**: sitemap endpoint response
- **Test**: Deploy a new device and verify sitemap includes it without manual refresh
- **Implementation**: Verify sitemap cache invalidation after device deployment

### 2. Device Configuration Auto-Update
- **Artifact**: device info endpoint response
- **Test**: Change device config and verify response includes updated state
- **Implementation**: Verify cache invalidation after config updates

### 3. Script-based Service Installation
- **Artifact**: Service installation logs and exit codes
- **Test**: Run _install_with_script on a target host
- **Implementation**: Verify script execution completes successfully

### 4. Exception Handling
- **Artifact**: Application logs
- **Test**: Trigger errors and verify exception handlers emit log messages
- **Implementation**: Search for and remove any bare except:pass patterns

### 5. MCP Tool Annotations
- **Artifact**: Tool definitions exposed via MCP protocol
- **Test**: Verify each tool has readOnlyHint, destructiveHint, idempotentHint
- **Implementation**: Add missing annotations to tool definitions

### 6. Error Response Formatting
- **Artifact**: Error response objects
- **Test**: Trigger errors and verify isError: true is included
- **Implementation**: Verify error response structure matches specification

## Success Criteria Validation

Each success criterion must be validated by:
1. Documenting the validation approach
2. Creating test cases or validation scripts
3. Running validation and recording results
4. Fixing any failures
5. Re-validating until all pass

## Priority Order

1. **Critical**: Tool annotations (MCP-01, MCP-02) - affects MCP client interaction
2. **Critical**: Exception handling - affects error visibility
3. **High**: Sitemap auto-refresh - affects UX
4. **High**: Device auto-update - affects UX
5. **Medium**: Service installation - affects functionality