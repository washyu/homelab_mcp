# Modern Homelab MCP Server - Architecture Document

## Project Overview
This document outlines a **Model Context Protocol (MCP) server** for AI-driven homelab automation, inspired by the WTT (Windows Test Technologies) architecture patterns from 2009. The MCP server provides tools and context for AI agents to intelligently manage Proxmox infrastructure, making decisions based on resource availability, user requirements, and operational best practices.

### AI-Driven Architecture Vision
- **AI Agent**: Makes intelligent decisions about VM sizing, placement, and configuration
- **MCP Server**: Provides tools, context, and operational knowledge (SOPs)
- **Infrastructure**: Proxmox + Terraform + Ansible execute the AI's decisions
- **User**: Provides high-level requirements ("I need a Jenkins server")

**Example Workflow:**
1. User: "Deploy an Ollama server for local LLM hosting"
2. AI Agent queries MCP for available GPU nodes and current utilization
3. AI Agent analyzes requirements and selects optimal configuration
4. AI Agent uses MCP tools to deploy via Terraform + Ansible
5. AI Agent monitors deployment and reports status

## Core Architecture Principles (From Original WTT Design)

### 1. Hierarchical Resource Pools
- **Original**: `/pool/subpool/config` paths for organizing test machines
- **Modern**: `/homelab/compute/gpu-nodes` for organizing Proxmox resources
- **Benefit**: Logical grouping and inheritance of properties

### 2. Database-Driven Configuration
- **Original**: SQL Server with XML blobs for deployment parameters
- **Modern**: PostgreSQL with JSONB for infrastructure definitions
- **Benefit**: Complex queries, relationships, and state management

### 3. Template-Based Deployment
- **Original**: `DistributedTestWorkflowTemplate` with parameters
- **Modern**: Combined Terraform + Ansible templates with variables
- **Benefit**: Reusable, parameterized infrastructure patterns

### 4. Dimension-Based Properties
- **Original**: Resource dimensions for machine characteristics
- **Modern**: Resource tags and metadata for VM/container properties
- **Benefit**: Flexible, queryable resource attributes

### 5. Service-Oriented Architecture
- **Original**: Separate Identity, Resource, Workflow, Schedule services
- **Modern**: Microservices with MCP protocol integration
- **Benefit**: Separation of concerns and scalability

## Technology Stack Comparison

| Component | Original WTT | Modern Implementation |
|-----------|--------------|----------------------|
| Database | SQL Server | PostgreSQL with JSONB |
| Configuration | XML Blobs | YAML/JSON Templates |
| Deployment | WTT Workflows | Terraform + Ansible + Provider-Specific Tools |
| API | COM/SOAP | REST/gRPC + MCP Protocol |
| Authentication | Windows Identity | JWT/OAuth2 + Provider-Specific Auth |
| Resource Target | Bare Metal Test Machines | **Multi-Provider**: Proxmox, Docker, LXD, K8s, VMware, AWS, Azure |
| Client | Windows Forms C# | Web UI + MCP Clients + Cloud Consoles |

## Multi-Provider Architecture (Enhanced WTT Design)

### Provider-Agnostic Resource Pools
```
/infrastructure/
├── on-premise/
│   ├── proxmox/
│   │   ├── compute/gpu-nodes/
│   │   └── storage/high-performance/
│   ├── docker/
│   │   ├── swarm-cluster/
│   │   └── standalone-hosts/
│   ├── kubernetes/
│   │   ├── production-cluster/
│   │   └── development-cluster/
│   └── vmware/
│       ├── esxi-01/
│       └── esxi-02/
└── cloud/
    ├── aws/
    │   ├── us-east-1/compute/
    │   └── us-west-2/storage/
    └── azure/
        ├── eastus/aks-cluster/
        └── westus/vm-scale-sets/
```

### Helm Chart Translation Layer (Provider Driver Pattern)

The universal resource definition gets translated through provider-specific Helm charts:

```yaml
# Universal Resource Definition (inspired by WTT XML configs)
apiVersion: homelab.ai/v1
kind: UniversalResource
metadata:
  name: ollama-server
spec:
  resource_type: compute
  workload_type: ai-inference
  requirements:
    cpu: 4
    memory_gb: 8
    storage_gb: 100
    gpu: true
    network: default
    high_availability: false
  deployment:
    environment: production
    backup_required: true
    monitoring: enabled
```

**Helm Chart Translation Architecture:**
```
Universal Definition → Helm Chart → Provider-Specific Config

ollama-server.yaml → proxmox-chart/ → terraform + ansible
                  → k8s-chart/     → kubernetes deployment
                  → docker-chart/  → docker compose
                  → aws-chart/     → cloudformation + EC2
                  → azure-chart/   → ARM template + VM
```

### Framework-Specific Helm Charts

#### 1. Proxmox Helm Chart (`charts/proxmox-compute/`)
```yaml
# values.yaml (receives universal definition)
resource:
  name: "{{ .Values.metadata.name }}"
  cpu: "{{ .Values.spec.requirements.cpu }}"
  memory_mb: "{{ mul .Values.spec.requirements.memory_gb 1024 }}"
  storage_gb: "{{ .Values.spec.requirements.storage_gb }}"
  gpu: "{{ .Values.spec.requirements.gpu }}"

# templates/terraform.tf.tpl
resource "proxmox_vm_qemu" "{{ .Values.resource.name }}" {
  name        = "{{ .Values.resource.name }}"
  target_node = "{{ .Values.proxmox.node | default "proxmox-01" }}"
  cores       = {{ .Values.resource.cpu }}
  memory      = {{ .Values.resource.memory_mb }}

  {{- if .Values.resource.gpu }}
  hostpci {
    host     = "{{ .Values.proxmox.gpu_device | default "01:00" }}"
    pcie     = 1
  }
  {{- end }}
}

# templates/ansible-playbook.yml.tpl
- name: Configure {{ .Values.resource.name }}
  hosts: "{{ .Values.resource.name }}"
  tasks:
    {{- if eq .Values.spec.workload_type "ai-inference" }}
    - include_role:
        name: nvidia-drivers
    - include_role:
        name: ollama
    {{- end }}
```

#### 2. Kubernetes Helm Chart (`charts/k8s-compute/`)
```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.metadata.name }}
spec:
  replicas: {{ if .Values.spec.requirements.high_availability }}3{{ else }}1{{ end }}
  template:
    spec:
      containers:
      - name: {{ .Values.metadata.name }}
        resources:
          requests:
            cpu: "{{ .Values.spec.requirements.cpu }}"
            memory: "{{ .Values.spec.requirements.memory_gb }}Gi"
            {{- if .Values.spec.requirements.gpu }}
            nvidia.com/gpu: 1
            {{- end }}
        {{- if eq .Values.spec.workload_type "ai-inference" }}
        image: ollama/ollama:latest
        {{- end }}
      {{- if .Values.spec.requirements.gpu }}
      nodeSelector:
        accelerator: nvidia-tesla-k80
      {{- end }}
```

#### 3. Docker Helm Chart (`charts/docker-compute/`)
```yaml
# templates/docker-compose.yml.tpl
version: '3.8'
services:
  {{ .Values.metadata.name }}:
    {{- if eq .Values.spec.workload_type "ai-inference" }}
    image: ollama/ollama:latest
    {{- end }}
    deploy:
      resources:
        limits:
          cpus: '{{ .Values.spec.requirements.cpu }}'
          memory: {{ .Values.spec.requirements.memory_gb }}G
    {{- if .Values.spec.requirements.gpu }}
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    {{- end }}
    volumes:
      - {{ .Values.metadata.name }}_data:/data
```

#### 4. AWS Helm Chart (`charts/aws-compute/`)
```yaml
# templates/cloudformation.yml.tpl
Resources:
  {{ .Values.metadata.name }}Instance:
    Type: AWS::EC2::Instance
    Properties:
      {{- if .Values.spec.requirements.gpu }}
      InstanceType: g4dn.xlarge
      {{- else }}
      InstanceType: t3.{{ if lt .Values.spec.requirements.cpu 4 }}medium{{ else }}large{{ end }}
      {{- end }}
      ImageId: ami-0c02fb55956c7d316  # Ubuntu 22.04
      UserData:
        Fn::Base64: !Sub |
          #!/bin/bash
          {{- if eq .Values.spec.workload_type "ai-inference" }}
          curl -fsSL https://ollama.ai/install.sh | sh
          {{- end }}
```

## Modern Project Structure (With Helm Chart Translation)

```
homelab-mcp-server/
├── src/
│   ├── mcp-server/           # MCP protocol implementation
│   ├── database/             # Schema and migrations
│   ├── services/             # Core business logic
│   ├── templates/            # Infrastructure templates
│   └── api/                  # REST API endpoints
├── charts/                   # Helm charts for provider translation
│   ├── proxmox-compute/      # Proxmox VM deployment charts
│   │   ├── Chart.yaml
│   │   ├── values.yaml       # Default values for universal→Proxmox translation
│   │   └── templates/
│   │       ├── terraform.tf.tpl      # Generates Terraform for Proxmox
│   │       ├── ansible-playbook.yml.tpl  # Generates Ansible configuration
│   │       └── _helpers.tpl
│   ├── kubernetes-workload/  # K8s deployment charts
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── deployment.yaml       # K8s Deployment
│   │       ├── service.yaml          # K8s Service
│   │       ├── configmap.yaml        # Configuration
│   │       └── ingress.yaml          # External access
│   ├── docker-compose/       # Docker Compose charts
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── docker-compose.yml.tpl
│   │       └── .env.tpl
│   ├── aws-ec2/             # AWS deployment charts
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── cloudformation.yml.tpl
│   │       ├── userdata.sh.tpl
│   │       └── security-groups.yml.tpl
│   ├── azure-vm/            # Azure deployment charts
│   │   ├── Chart.yaml
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── arm-template.json.tpl
│   │       ├── vm-config.yml.tpl
│   │       └── network-config.yml.tpl
│   └── vmware-vsphere/      # VMware deployment charts
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── terraform-vsphere.tf.tpl
│           └── vm-customization.yml.tpl
├── terraform/
│   ├── modules/              # Reusable TF modules
│   └── providers/            # Provider configurations
├── ansible/
│   ├── playbooks/            # Configuration playbooks
│   ├── roles/                # Reusable roles
│   └── inventory/            # Dynamic inventory
├── config/
│   ├── universal-definitions/    # Universal resource YAML definitions
│   │   ├── workload-types/       # Templates for common workloads
│   │   │   ├── ai-inference.yaml     # Ollama, ML models
│   │   │   ├── web-application.yaml  # Web apps, APIs
│   │   │   ├── database.yaml         # MySQL, PostgreSQL, MongoDB
│   │   │   └── ci-cd.yaml           # Jenkins, GitLab, GitHub Actions
│   │   └── examples/             # Example universal definitions
│   └── resource-pools/           # Pool configurations
├── rendered-configs/         # Generated provider-specific configs (gitignored)
│   ├── proxmox/
│   ├── kubernetes/
│   ├── docker/
│   ├── aws/
│   └── azure/
├── tests/
│   ├── helm-chart-tests/     # Test Helm chart rendering
│   ├── integration-tests/    # End-to-end deployment tests
│   └── unit-tests/
├── docs/
│   ├── helm-charts/          # Helm chart documentation
│   ├── universal-schema/     # Universal definition schema docs
│   └── provider-guides/      # Provider-specific setup guides
└── docker/                   # Container definitions
```

### Chart Naming Convention

Charts follow a consistent naming pattern for AI agent discovery:
- `{provider}-{resource-type}`: Basic resource deployment (vm, container, etc.)
- `{provider}-{workload-type}`: Workload-specific optimizations (ai-inference, web-app, etc.)
- `{provider}-{specialty}`: Special capabilities (gpu-compute, high-availability, etc.)

### Universal Definition Validation Flow

```
User Definition → Schema Validation → Chart Compatibility Check → AI Provider Selection

Example:
ollama-server.yaml → ✅ Valid universal schema → ✅ Compatible with proxmox-compute chart → AI: "Proxmox recommended for 24/7 AI workloads"
```

## Database Schema (Modernized from WTT)

```sql
-- Resource Pool Hierarchy (Based on WTT ResourcePool)
CREATE TABLE resource_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    full_path VARCHAR(500) NOT NULL UNIQUE, -- /homelab/compute/gpu-nodes
    parent_id UUID REFERENCES resource_pools(id),
    pool_type VARCHAR(50) NOT NULL, -- compute, storage, network
    proxmox_node VARCHAR(100),
    description TEXT,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Deployment Templates (Based on WTT DistributedTestWorkflowTemplate)
CREATE TABLE deployment_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    template_type VARCHAR(50) NOT NULL, -- vm, container, service
    terraform_module_path TEXT,
    ansible_playbook_path TEXT,
    default_parameters JSONB DEFAULT '{}',
    required_parameters JSONB DEFAULT '[]',
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0.0',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Resource Dimensions (Based on WTT Dimension system)
CREATE TABLE resource_dimensions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id UUID NOT NULL,
    resource_type VARCHAR(50) NOT NULL, -- pool, instance, template
    dimension_name VARCHAR(100) NOT NULL,
    dimension_value TEXT,
    dimension_type VARCHAR(50) DEFAULT 'string', -- string, number, boolean, json
    created_at TIMESTAMP DEFAULT NOW()
);

-- Deployment Instances (Based on WTT WorkflowInstance)
CREATE TABLE deployment_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    template_id UUID REFERENCES deployment_templates(id),
    resource_pool_id UUID REFERENCES resource_pools(id),
    parameters JSONB DEFAULT '{}',
    terraform_state_path TEXT,
    ansible_inventory_path TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, deploying, running, failed, destroyed
    proxmox_vm_id INTEGER,
    ip_address INET,
    ssh_credentials JSONB, -- Encrypted credentials
    error_message TEXT,
    -- State tracking for AI deviation detection
    expected_state JSONB, -- What the AI thinks should be running
    actual_state JSONB,   -- What was last discovered from Proxmox
    state_last_checked TIMESTAMP,
    deviation_detected BOOLEAN DEFAULT FALSE,
    deviation_details JSONB,
    -- Template generation from successful deployments
    template_candidate BOOLEAN DEFAULT FALSE,
    template_generated_from UUID REFERENCES deployment_templates(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deployed_at TIMESTAMP,
    destroyed_at TIMESTAMP
);

-- Infrastructure State Snapshots (New - for AI context)
CREATE TABLE infrastructure_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_type VARCHAR(50) NOT NULL, -- discovery, deployment, migration
    snapshot_data JSONB NOT NULL, -- Complete infrastructure state
    proxmox_node VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255), -- AI agent or user
    notes TEXT
);

-- State Deviations (New - for AI anomaly detection)
CREATE TABLE state_deviations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID REFERENCES deployment_instances(id),
    deviation_type VARCHAR(50) NOT NULL, -- missing_vm, config_drift, resource_change
    expected_value JSONB,
    actual_value JSONB,
    severity VARCHAR(20) DEFAULT 'medium', -- low, medium, high, critical
    auto_correctable BOOLEAN DEFAULT FALSE,
    corrective_action TEXT,
    detected_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(255)
);

-- Generated Templates (New - AI learns from successful deployments)
CREATE TABLE generated_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_instance_id UUID REFERENCES deployment_instances(id),
    template_name VARCHAR(255) NOT NULL,
    confidence_score FLOAT DEFAULT 0.0, -- AI confidence in template quality
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,
    learned_optimizations JSONB, -- What the AI learned from this deployment
    template_config JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used TIMESTAMP
);

-- Audit Log (New addition for modern requirements)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,
    user_id VARCHAR(255),
    changes JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_resource_pools_path ON resource_pools(full_path);
CREATE INDEX idx_resource_pools_parent ON resource_pools(parent_id);
CREATE INDEX idx_dimensions_resource ON resource_dimensions(resource_id, resource_type);
CREATE INDEX idx_instances_status ON deployment_instances(status);
CREATE INDEX idx_instances_pool ON deployment_instances(resource_pool_id);
```

## Configuration Template Format

```yaml
# deployment-template.yml - Modern replacement for XML blobs
apiVersion: homelab.mcp/v1
kind: DeploymentTemplate
metadata:
  name: ollama-gpu-server
  version: "1.0.0"
  description: "AI inference server with GPU passthrough"

spec:
  # Resource requirements
  resources:
    pool_path: "/homelab/compute/gpu-nodes"
    requirements:
      cores: 8
      memory_gb: 16
      storage_gb: 100
      gpu_passthrough: true

  # Infrastructure definition (Terraform)
  infrastructure:
    provider: proxmox
    module: "vm-with-gpu"
    variables:
      template_id: 9000
      network_bridge: "vmbr0"
      storage_pool: "local-lvm"

  # Configuration management (Ansible)
  configuration:
    playbooks:
      - name: "setup-base-system"
        path: "ansible/playbooks/base-system.yml"
      - name: "install-nvidia-drivers"
        path: "ansible/playbooks/nvidia-gpu.yml"
      - name: "deploy-ollama"
        path: "ansible/playbooks/ollama.yml"
    variables:
      ollama_models: ["llama2", "codellama"]
      ollama_port: 11434
      backup_enabled: true

  # Resource dimensions/tags
  dimensions:
    purpose: "ai-inference"
    backup_schedule: "daily"
    monitoring: "prometheus"
    owner: "homelab-admin"
    cost_center: "research"

  # Validation rules
  validation:
    required_dimensions:
      - gpu_passthrough: true
    node_constraints:
      - has_gpu: true
      - min_memory_gb: 32
```

## MCP Tools for AI Agents (Based on WTT Operations)

The MCP server provides tools that enable AI agents to intelligently manage infrastructure. Each tool provides both **execution capability** and **contextual information** for decision-making.

```javascript
// MCP tool definitions for AI-driven homelab management
const mcpTools = [

  // MULTI-PROVIDER DISCOVERY TOOLS - Provide context for AI decision-making
  {
    name: "discover-infrastructure-context",
    description: "Get complete multi-provider infrastructure inventory for AI decision-making",
    inputSchema: {
      type: "object",
      properties: {
        providers: { type: "array", items: { type: "string" }, default: ["all"] }, // proxmox, docker, k8s, aws, azure
        include_capacity: { type: "boolean", default: true },
        include_utilization: { type: "boolean", default: true },
        include_templates: { type: "boolean", default: true },
        include_costs: { type: "boolean", default: true },
        staleness_hours: { type: "number", default: 1 }
      }
    },
    returns: {
      providers: {
        proxmox: "Proxmox nodes, VMs, templates, capacity",
        docker: "Docker hosts, containers, images, swarm status",
        kubernetes: "K8s clusters, nodes, pods, deployments",
        aws: "EC2 instances, EKS clusters, regions, costs",
        azure: "VMs, AKS clusters, resource groups, costs",
        vmware: "ESXi hosts, VMs, clusters, datastores"
      },
      resource_pools: "Hierarchical pool structure across all providers",
      cost_analysis: "Cross-provider cost comparison",
      availability_zones: "Geographic distribution of resources"
    }
  },

  {
    name: "find-best-provider-for-workload",
    description: "AI tool to determine optimal provider/platform for specific workload",
    inputSchema: {
      type: "object",
      properties: {
        workload_type: { type: "string" }, // "web-app", "ai-inference", "database", "batch-processing"
        requirements: { type: "object" }, // cpu, memory, storage, network, compliance
        cost_constraints: { type: "object" }, // max_monthly_cost, prefer_on_premise
        availability_requirements: { type: "string", enum: ["basic", "high", "critical"] },
        data_locality: { type: "string" } // geographic requirements
      },
      required: ["workload_type"]
    },
    returns: {
      recommended_provider: "Best provider for this workload",
      provider_comparison: "Pros/cons of each viable provider",
      cost_estimates: "Monthly cost projections per provider",
      migration_complexity: "Effort to move between providers later",
      deployment_strategy: "How to deploy on recommended provider"
    }
  },

  {
    name: "analyze-resource-requirements",
    description: "Help AI determine optimal resource allocation for workload",
    inputSchema: {
      type: "object",
      properties: {
        workload_type: { type: "string" }, // "ollama", "jenkins", "nextcloud"
        user_requirements: { type: "object" }, // CPU, memory, storage hints
        performance_tier: { type: "string", enum: ["minimal", "standard", "high-performance"] },
        consider_gpu: { type: "boolean", default: false }
      },
      required: ["workload_type"]
    },
    returns: {
      recommended_config: "Optimal VM configuration",
      alternative_configs: "Array of alternative configurations",
      resource_justification: "Explanation of resource decisions",
      placement_recommendations: "Best nodes/pools for deployment"
    }
  },

  {
    name: "find-optimal-placement",
    description: "AI tool to find best node/pool for deployment based on current state",
    inputSchema: {
      type: "object",
      properties: {
        resource_requirements: { type: "object" }, // cores, memory, storage, gpu
        affinity_rules: { type: "object" }, // prefer/avoid certain nodes
        high_availability: { type: "boolean", default: false }
      },
      required: ["resource_requirements"]
    },
    returns: {
      best_node: "Optimal Proxmox node for deployment",
      resource_pool: "Recommended resource pool path",
      capacity_impact: "How deployment affects node capacity",
      alternative_nodes: "Backup placement options"
    }
  },

  // HELM CHART TRANSLATION TOOLS - Convert universal definitions to provider-specific configs
  {
    name: "translate-universal-to-provider",
    description: "Use Helm charts to translate universal resource definition to provider-specific config",
    inputSchema: {
      type: "object",
      properties: {
        universal_definition: { type: "object" }, // The universal resource YAML
        target_provider: { type: "string" }, // "proxmox", "kubernetes", "docker", "aws", "azure"
        chart_version: { type: "string", default: "latest" },
        provider_overrides: { type: "object", default: {} } // Provider-specific customizations
      },
      required: ["universal_definition", "target_provider"]
    },
    returns: {
      rendered_config: "Provider-specific configuration (Terraform, K8s YAML, etc.)",
      helm_values: "The values passed to the Helm chart",
      validation_results: "Chart template validation results",
      deployment_commands: "Commands to execute the rendered configuration"
    }
  },

  {
    name: "list-available-helm-charts",
    description: "Get available Helm charts for different providers and workload types",
    inputSchema: {
      type: "object",
      properties: {
        provider_filter: { type: "string" }, // "proxmox", "kubernetes", etc.
        workload_filter: { type: "string" }, // "ai-inference", "web-app", etc.
        include_custom_charts: { type: "boolean", default: true }
      }
    },
    returns: {
      available_charts: "List of charts by provider and workload type",
      chart_capabilities: "What each chart can deploy",
      compatibility_matrix: "Which universal features work with which charts",
      chart_versions: "Available versions and their differences"
    }
  },

  {
    name: "validate-universal-definition",
    description: "Validate universal resource definition against available Helm charts",
    inputSchema: {
      type: "object",
      properties: {
        universal_definition: { type: "object" },
        target_providers: { type: "array", items: { type: "string" } },
        strict_validation: { type: "boolean", default: false }
      },
      required: ["universal_definition"]
    },
    returns: {
      validation_results: "Per-provider validation results",
      unsupported_features: "Features not supported by target providers",
      recommended_alternatives: "Alternative configurations for unsupported features",
      provider_recommendations: "Best providers for this workload"
    }
  },

  {
    name: "deploy-with-intelligence",
    description: "AI-driven deployment using Helm chart translation",
    inputSchema: {
      type: "object",
      properties: {
        universal_definition: { type: "object" }, // Complete universal resource definition
        preferred_provider: { type: "string" }, // AI recommendation, but user can override
        auto_optimize: { type: "boolean", default: true },
        dry_run: { type: "boolean", default: false },
        helm_chart_overrides: { type: "object", default: {} }
      },
      required: ["universal_definition"]
    },
    returns: {
      selected_provider: "Provider chosen for deployment",
      helm_chart_used: "Which chart was used for translation",
      rendered_configs: "All generated configuration files",
      deployment_plan: "Step-by-step execution plan",
      execution_results: "Results of actual deployment (if not dry_run)"
    }
  },

  {
    name: "query-resource-pools",
    description: "Query resource pools with filters (like WTT resource queries)",
    inputSchema: {
      type: "object",
      properties: {
        path_pattern: { type: "string" },
        pool_type: { type: "string" },
        dimension_filters: { type: "array", items: { type: "string" } },
        include_capacity: { type: "boolean", default: false }
      }
    }
  },

  {
    name: "list-deployment-templates",
    description: "List available templates (like WTT template discovery)",
    inputSchema: {
      type: "object",
      properties: {
        template_type: { type: "string" },
        compatible_with_pool: { type: "string" },
        include_parameters: { type: "boolean", default: false }
      }
    }
  },

  {
    name: "get-deployment-status",
    description: "Get deployment status (like WTT job status)",
    inputSchema: {
      type: "object",
      properties: {
        instance_id: { type: "string" },
        instance_name: { type: "string" },
        include_logs: { type: "boolean", default: false }
      }
    }
  },

  {
    name: "update-resource-dimensions",
    description: "Update resource metadata (like WTT dimensions)",
    inputSchema: {
      type: "object",
      properties: {
        resource_id: { type: "string" },
        resource_type: { type: "string", enum: ["pool", "instance", "template"] },
        dimensions: { type: "object" },
        merge_mode: { type: "string", enum: ["replace", "merge"], default: "merge" }
      },
      required: ["resource_id", "resource_type", "dimensions"]
    }
  },

  // STATE MANAGEMENT TOOLS - AI-driven deviation detection and correction
  {
    name: "compare-expected-vs-actual-state",
    description: "Compare database expected state vs live Proxmox state (like WTT state validation)",
    inputSchema: {
      type: "object",
      properties: {
        instance_id: { type: "string" },
        instance_name: { type: "string" },
        check_all_instances: { type: "boolean", default: false },
        auto_correct_minor_deviations: { type: "boolean", default: false }
      }
    },
    returns: {
      deviations_found: "Array of state deviations detected",
      correctable_issues: "Issues AI can automatically fix",
      manual_intervention_required: "Complex issues needing human decision",
      recommended_actions: "AI recommendations for each deviation"
    }
  },

  {
    name: "generate-template-from-instance",
    description: "Create reusable template from successful deployment (AI learning)",
    inputSchema: {
      type: "object",
      properties: {
        instance_id: { type: "string" },
        template_name: { type: "string" },
        include_optimizations: { type: "boolean", default: true },
        confidence_threshold: { type: "number", default: 0.8 }
      },
      required: ["instance_id", "template_name"]
    },
    returns: {
      template_id: "Generated template UUID",
      confidence_score: "AI confidence in template quality (0-1)",
      learned_optimizations: "Performance/security improvements discovered",
      reusability_score: "How broadly applicable this template is"
    }
  },

  {
    name: "create-infrastructure-snapshot",
    description: "Capture complete infrastructure state for migration/backup (like WTT state capture)",
    inputSchema: {
      type: "object",
      properties: {
        snapshot_name: { type: "string" },
        include_secrets: { type: "boolean", default: false },
        proxmox_node: { type: "string" },
        include_vm_configs: { type: "boolean", default: true },
        include_network_configs: { type: "boolean", default: true }
      },
      required: ["snapshot_name"]
    },
    returns: {
      snapshot_id: "Snapshot UUID for later reference",
      captured_resources: "List of captured VMs, networks, storage",
      migration_readiness: "Assessment of how portable this snapshot is",
      estimated_migration_time: "Time to recreate this infrastructure elsewhere"
    }
  },

  {
    name: "plan-migration-from-snapshot",
    description: "Plan infrastructure migration using captured state",
    inputSchema: {
      type: "object",
      properties: {
        snapshot_id: { type: "string" },
        target_node: { type: "string" },
        target_resource_pool: { type: "string" },
        migration_strategy: { type: "string", enum: ["clone", "backup-restore", "rebuild"], default: "clone" }
      },
      required: ["snapshot_id", "target_node"]
    },
    returns: {
      migration_plan: "Step-by-step migration process",
      resource_requirements: "Resources needed on target node",
      potential_conflicts: "Issues that might prevent migration",
      estimated_downtime: "Expected service interruption time"
    }
  },

  {
    name: "detect-infrastructure-anomalies",
    description: "AI-driven detection of unusual patterns or problems",
    inputSchema: {
      type: "object",
      properties: {
        analysis_window_hours: { type: "number", default: 24 },
        include_performance_metrics: { type: "boolean", default: true },
        anomaly_sensitivity: { type: "string", enum: ["low", "medium", "high"], default: "medium" }
      }
    },
    returns: {
      anomalies_detected: "Unusual patterns found",
      risk_assessment: "Potential impact of each anomaly",
      recommended_investigations: "What to check next",
      auto_correctable_issues": "Problems AI can fix automatically"
    }
  },

  {
    name: "discover-proxmox-resources",
    description: "Discover and sync Proxmox resources with state tracking (like WTT resource discovery)",
    inputSchema: {
      type: "object",
      properties: {
        proxmox_node: { type: "string" },
        include_templates: { type: "boolean", default: true },
        include_storage: { type: "boolean", default: true },
        update_inventory: { type: "boolean", default: true },
        detect_deviations: { type: "boolean", default: true }
      }
    },
    returns: {
      discovered_resources: "All discovered VMs, storage, networks",
      new_resources_found: "Resources not in database",
      missing_resources: "Database resources not found in Proxmox",
      state_deviations: "Configuration differences detected",
      sync_actions_taken": "What was automatically synchronized"
    }
  }
];
```

## AI-Driven Workflow Examples

### Example 1: "Deploy Jenkins with High Availability"
```
User: "I need a Jenkins server that can handle CI/CD for 5 developers"

AI Agent Workflow:
1. analyze-resource-requirements(workload_type="jenkins", user_requirements={developers: 5})
   → Returns: 4 cores, 8GB RAM, 100GB storage recommended

2. discover-infrastructure-context(include_utilization=true)
   → Returns: Current cluster state, available capacity

3. find-optimal-placement(resource_requirements={cores:4, memory_gb:8}, high_availability=true)
   → Returns: Deploy on node-01, backup on node-02

4. deploy-with-intelligence(workload_type="jenkins", instance_name="jenkins-prod",
                           user_requirements={developers: 5})
   → Executes: Terraform VM creation + Ansible Jenkins installation

5. update-context-after-deployment(instance_id, endpoint="http://jenkins.local:8080")
   → Updates: MCP context with new service information
```

### Example 2: "Deploy Ollama with GPU, but I'm not sure about sizing"
```
User: "I want to run LLaMA models locally but not sure what I need"

AI Agent Workflow:
1. get-sop(operation="deploy_ollama", detailed=true)
   → Returns: Best practices, model size requirements, GPU recommendations

2. analyze-resource-requirements(workload_type="ollama", consider_gpu=true,
                                performance_tier="standard")
   → Returns: Recommends RTX 4090, 16GB RAM, explains model size trade-offs

3. discover-infrastructure-context(providers=["all"], include_capacity=true)
   → Checks: GPU availability across Proxmox, AWS (P3 instances), Azure (NC series)

4. find-best-provider-for-workload(workload_type="ai-inference",
                                  requirements={gpu:true, cost_sensitive:true})
   → Returns: "Proxmox cheapest for 24/7, AWS best for burst workloads"

5. deploy-with-intelligence(workload_type="ollama", instance_name="ollama-gpu",
                           provider="proxmox", auto_optimize=true)
   → Creates: GPU-enabled VM with proper drivers and Ollama installation
```

### Example 3: "I need high availability web app, you pick the best approach"
```
User: "Deploy my web app with high availability, I don't care how"

AI Agent Workflow:
1. find-best-provider-for-workload(workload_type="web-app",
                                  availability_requirements="high")
   → Compares: Proxmox HA cluster vs K8s vs AWS auto-scaling
   → Returns: "Kubernetes provides best HA with automatic failover"

2. discover-infrastructure-context(providers=["kubernetes", "proxmox"])
   → Checks: K8s cluster capacity, Proxmox available for K8s nodes

3. deploy-with-intelligence(workload_type="web-app",
                           deployment_target="kubernetes",
                           instance_name="webapp-ha")
   → Creates: K8s deployment with 3 replicas, load balancer, auto-scaling
```

### Example 4: "Cost optimize my development environment across providers"
```
User: "I have dev/staging/prod environments, optimize costs across all platforms"

AI Agent Workflow:
1. discover-infrastructure-context(providers=["all"], include_costs=true)
   → Returns: Current spend across Proxmox (power), AWS, Azure, Docker hosts

2. analyze-cross-provider-optimization()
   → Finds: "Dev can move to cheaper Proxmox, Staging to spot instances, Prod stay put"

3. plan-multi-provider-migration()
   → Creates: Migration plan to optimize costs by $200/month

4. execute-optimization-plan(auto_approve_under_threshold=100)
   → Migrates: Dev to Proxmox, resizes staging instances, consolidates Docker containers
```

## Standard Operating Procedures (SOPs) for AI Agents

The MCP server includes built-in operational knowledge that guides AI decision-making:

```javascript
// SOP tools that provide procedural knowledge to AI agents
const sopTools = [
  {
    name: "get-deployment-sop",
    description: "Get detailed deployment procedure for any service",
    inputSchema: {
      service_name: { type: "string" }, // "jenkins", "ollama", "nextcloud"
      target_environment: { type: "string", default: "production" },
      include_troubleshooting: { type: "boolean", default: true }
    },
    returns: {
      prerequisites: "Required infrastructure and dependencies",
      deployment_steps: "Step-by-step deployment process",
      validation_checks: "How to verify successful deployment",
      common_issues: "Known problems and solutions",
      post_deployment: "Configuration and maintenance tasks"
    }
  },

  {
    name: "get-resource-allocation-guidelines",
    description: "Get best practices for resource sizing decisions",
    inputSchema: {
      workload_category: { type: "string" }, // "web", "ai", "database", "ci-cd"
      expected_load: { type: "string", enum: ["light", "medium", "heavy"] }
    },
    returns: {
      baseline_config: "Starting resource allocation",
      scaling_guidelines: "When and how to scale resources",
      performance_indicators: "Metrics to monitor",
      cost_optimization: "How to optimize resource usage"
    }
  },

  {
    name: "get-placement-strategy",
    description: "Get best practices for VM/container placement",
    inputSchema: {
      service_type: { type: "string" },
      availability_requirements: { type: "string" },
      performance_requirements: { type: "string" }
    },
    returns: {
      placement_rules: "Where to deploy for optimal performance",
      anti_affinity_rules: "What to avoid placing together",
      network_considerations: "Network topology impacts",
      backup_strategies: "How to ensure redundancy"
    }
  }
];
```

## Context Management (Enhanced from WTT)

Your WTT system's strength was maintaining accurate state - the MCP server enhances this for AI agents:

```javascript
// Context management for AI decision-making
class ContextManager {

  // Infrastructure Context (like WTT resource discovery)
  async getInfrastructureContext() {
    return {
      nodes: await this.discoverProxmoxNodes(),
      resource_pools: await this.getResourcePoolHierarchy(),
      templates: await this.getAvailableTemplates(),
      current_deployments: await this.getCurrentDeployments(),
      capacity_trends: await this.getCapacityTrends(),
      last_updated: timestamp
    };
  }

  // Service Context (new capability)
  async getServiceContext() {
    return {
      running_services: await this.getRunningServices(),
      service_dependencies: await this.getServiceDependencies(),
      health_status: await this.getHealthChecks(),
      backup_status: await this.getBackupStatus(),
      security_posture: await this.getSecurityStatus()
    };
  }

  // Operational Context (based on WTT audit logs)
  async getOperationalContext() {
    return {
      recent_deployments: await this.getRecentDeployments(),
      failed_operations: await this.getFailedOperations(),
      resource_utilization_trends: await this.getUtilizationTrends(),
      maintenance_windows: await this.getMaintenanceSchedule(),
      cost_tracking: await this.getCostAnalysis()
    };
  }
}
```

## Service Architecture (Modernized WTT Services)

```javascript
// Core services based on WTT architecture
class ModernHomelabServices {

  // Identity Service (WTT Identity equivalent)
  class IdentityService {
    authenticate(token) {}
    authorize(user, resource, action) {}
    getUserPermissions(user) {}
  }

  // Resource Service (WTT Resource equivalent)
  class ResourceService {
    createResourcePool(poolConfig) {}
    queryResourcePools(filters) {}
    updateResourceCapacity(poolId, capacity) {}
    getResourceDimensions(resourceId) {}
  }

  // Template Service (WTT Workflow Template equivalent)
  class TemplateService {
    createTemplate(templateConfig) {}
    validateTemplate(templateId) {}
    listTemplates(filters) {}
    generateDeploymentPlan(templateId, parameters) {}
  }

  // Deployment Service (WTT Job/Workflow equivalent)
  class DeploymentService {
    deployFromTemplate(templateId, parameters) {}
    getDeploymentStatus(instanceId) {}
    cancelDeployment(instanceId) {}
    destroyDeployment(instanceId) {}
  }

  // Infrastructure Service (New - handles Terraform/Ansible)
  class InfrastructureService {
    executeTerraform(moduleConfig) {}
    runAnsiblePlaybook(playbookConfig) {}
    validateInfrastructure(instanceId) {}
  }

  // Notification Service (WTT Notification equivalent)
  class NotificationService {
    sendDeploymentNotification(instanceId, status) {}
    sendResourceAlert(poolId, alertType) {}
    configureWebhooks(webhookConfig) {}
  }
}
```

## Implementation Roadmap

### Phase 1: Core Foundation (Weeks 1-2)
- [ ] Database schema setup with migrations
- [ ] Basic MCP server implementation
- [ ] Resource pool CRUD operations
- [ ] Template management system

### Phase 2: Infrastructure Integration (Weeks 3-4)
- [ ] Proxmox API integration
- [ ] Terraform module execution
- [ ] Ansible playbook execution
- [ ] Basic deployment workflows

### Phase 3: Advanced Features (Weeks 5-6)
- [ ] Resource dimension system
- [ ] Template validation and testing
- [ ] Deployment monitoring and rollback
- [ ] Web UI for management

### Phase 4: Production Ready (Weeks 7-8)
- [ ] Authentication and authorization
- [ ] Audit logging and compliance
- [ ] Performance optimization
- [ ] Documentation and testing

## Key Advantages of This Architecture

1. **Proven Patterns**: Based on battle-tested WTT architecture from 2009
2. **Modern Stack**: Uses current best practices and tools
3. **Scalable**: Microservices architecture supports growth
4. **Flexible**: Database-driven configuration allows complex scenarios
5. **AI-Friendly**: MCP protocol enables AI agent integration
6. **GitOps Compatible**: Templates and configurations can be version controlled

## Migration Benefits from Original WTT

- **Preserve Logic**: Core resource management concepts remain intact
- **Modern Tools**: Terraform/Ansible replace proprietary WTT workflows
- **Cloud Ready**: Can extend to cloud providers beyond Proxmox
- **Open Source**: No proprietary dependencies or licensing concerns
- **AI Integration**: MCP protocol enables intelligent automation

This architecture preserves the brilliant concepts from your original WTT system while modernizing it for current homelab automation needs.
