"""Schema definitions for infrastructure CRUD operations."""

from typing import Any

INFRASTRUCTURE_TOOLS: dict[str, dict[str, Any]] = {
    "deploy_infrastructure": {
        "description": "Deploy new infrastructure based on AI recommendations or user specifications",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deployment_plan": {
                    "type": "object",
                    "description": "Infrastructure deployment plan",
                    "properties": {
                        "services": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["docker", "lxd", "service"],
                                    },
                                    "target_device_id": {"type": "integer"},
                                    "config": {"type": "object"},
                                },
                                "required": ["name", "type", "target_device_id"],
                            },
                        },
                        "network_changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "enum": [
                                            "create_vlan",
                                            "configure_firewall",
                                            "setup_routing",
                                        ],
                                    },
                                    "target_device_id": {"type": "integer"},
                                    "config": {"type": "object"},
                                },
                            },
                        },
                    },
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate the plan without executing",
                },
            },
            "required": ["deployment_plan"],
        },
    },
    "update_device_config": {
        "description": "Update configuration of an existing device",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the device to update",
                },
                "config_changes": {
                    "type": "object",
                    "description": "Configuration changes to apply",
                    "properties": {
                        "services": {
                            "type": "object",
                            "description": "Service configuration changes",
                        },
                        "network": {
                            "type": "object",
                            "description": "Network configuration changes",
                        },
                        "security": {
                            "type": "object",
                            "description": "Security configuration changes",
                        },
                        "resources": {
                            "type": "object",
                            "description": "Resource allocation changes",
                        },
                    },
                },
                "backup_before_change": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create backup before applying changes",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate changes without applying",
                },
            },
            "required": ["device_id", "config_changes"],
        },
    },
    "decommission_device": {
        "description": "Safely remove a device from the network infrastructure",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "integer",
                    "description": "Database ID of the device to decommission",
                },
                "migration_plan": {
                    "type": "object",
                    "description": "Plan for migrating services to other devices",
                    "properties": {
                        "target_devices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Device IDs to migrate services to",
                        },
                        "service_mapping": {
                            "type": "object",
                            "description": "Mapping of services to target devices",
                        },
                    },
                },
                "force_removal": {
                    "type": "boolean",
                    "default": False,
                    "description": "Force removal without migration (data loss possible)",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate decommission plan without executing",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, return a preview of what would be affected without executing any changes.",
                },
            },
            "required": ["device_id"],
        },
    },
    "scale_services": {
        "description": "Scale services up or down based on resource analysis",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scaling_plan": {
                    "type": "object",
                    "description": "Service scaling plan",
                    "properties": {
                        "scale_up": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "integer"},
                                    "service_name": {"type": "string"},
                                    "target_replicas": {"type": "integer"},
                                    "resource_allocation": {"type": "object"},
                                },
                            },
                        },
                        "scale_down": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "device_id": {"type": "integer"},
                                    "service_name": {"type": "string"},
                                    "target_replicas": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate scaling plan without executing",
                },
            },
            "required": ["scaling_plan"],
        },
    },
    "validate_infrastructure_changes": {
        "description": "Validate infrastructure changes before applying them",
        "inputSchema": {
            "type": "object",
            "properties": {
                "change_plan": {
                    "type": "object",
                    "description": "Infrastructure change plan to validate",
                },
                "validation_level": {
                    "type": "string",
                    "enum": ["basic", "comprehensive", "simulation"],
                    "default": "comprehensive",
                    "description": "Level of validation to perform",
                },
            },
            "required": ["change_plan"],
        },
    },
    "create_infrastructure_backup": {
        "description": "Create a backup of current infrastructure state",
        "inputSchema": {
            "type": "object",
            "properties": {
                "backup_scope": {
                    "type": "string",
                    "enum": ["full", "partial", "device_specific"],
                    "default": "full",
                    "description": "Scope of the backup",
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific device IDs to backup (for partial/device_specific)",
                },
                "include_data": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include application data in backup",
                },
                "backup_name": {
                    "type": "string",
                    "description": "Name for the backup (auto-generated if not provided)",
                },
            },
            "required": [],
        },
    },
    "rollback_infrastructure_changes": {
        "description": "Rollback recent infrastructure changes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "backup_id": {
                    "type": "string",
                    "description": "Backup ID to rollback to",
                },
                "rollback_scope": {
                    "type": "string",
                    "enum": ["full", "partial", "device_specific"],
                    "default": "full",
                    "description": "Scope of the rollback",
                },
                "device_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific device IDs to rollback (for partial/device_specific)",
                },
                "validate_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Only validate rollback plan without executing",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, return a preview of what would be affected without executing any changes.",
                },
            },
            "required": ["backup_id"],
        },
    },
}
