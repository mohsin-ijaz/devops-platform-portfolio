variable "cloud_provider" {
  description = "Cloud provider type (auto-detected if not specified)"
  type        = string
  default     = null
  validation {
    condition     = var.cloud_provider == null || contains(["gcp", "aws"], var.cloud_provider)
    error_message = "Cloud provider must be either 'gcp', 'aws', or null for auto-detection."
  }
}

variable "cluster_name" {
  description = "The Kubernetes cluster name"
  type        = string
}

variable "cluster_location" {
  description = "The Kubernetes cluster location (region or zone)"
  type        = string
}

variable "cluster_endpoint" {
  description = "The cluster endpoint"
  type        = string
  default     = null
}

variable "cluster_ca_certificate" {
  description = "The cluster CA certificate"
  type        = string
  default     = null
}

variable "cluster_access_token" {
  description = "The cluster access token"
  type        = string
  default     = null
  sensitive   = true
}

variable "namespace" {
  description = "The namespace to deploy Datadog into"
  type        = string
  default     = "monitoring"
}

variable "datadog_api_key" {
  description = "Datadog API Key"
  type        = string
}

variable "datadog_app_key" {
  description = "Datadog Application Key"
  type        = string
}

variable "datadog_site" {
  description = "Datadog Site Parameter"
  type        = string
  default     = "datadoghq.com"
  validation {
    condition = contains([
      "datadoghq.com",     # US1
      "us3.datadoghq.com", # US3
      "us5.datadoghq.com", # US5
      "datadoghq.eu",      # EU1
      "ddog-gov.com",      # US1-FED
      "ap1.datadoghq.com", # AP1 (Japan)
      "ap2.datadoghq.com"  # AP2 (Australia)
    ], var.datadog_site)
    error_message = "Datadog site must be one of: datadoghq.com (US1), us3.datadoghq.com (US3), us5.datadoghq.com (US5), datadoghq.eu (EU1), ddog-gov.com (US1-FED), ap1.datadoghq.com (AP1), ap2.datadoghq.com (AP2)."
  }
}

variable "datadog_api_url" {
  description = "Datadog API URL"
  type        = string
  default     = "https://api.datadoghq.com"
  validation {
    condition = contains([
      "https://api.datadoghq.com",     # US1
      "https://api.us3.datadoghq.com", # US3
      "https://api.us5.datadoghq.com", # US5
      "https://api.datadoghq.eu",      # EU1
      "https://api.ddog-gov.com",      # US1-FED
      "https://api.ap1.datadoghq.com", # AP1 (Japan)
      "https://api.ap2.datadoghq.com"  # AP2 (Australia)
    ], var.datadog_api_url)
    error_message = "Datadog API URL must be one of the valid Datadog API endpoints."
  }
}

variable "datadog_environment" {
  description = "Datadog environment tag"
  type        = string
  validation {
    condition     = contains(["dev", "uat", "qa", "prod"], var.datadog_environment)
    error_message = "Environment must be one of 'dev', 'uat', 'qa', or 'prod'."
  }
}

variable "datadog_domain" {
  description = "Business domain identifier"
  type        = string
  validation {
    condition     = contains(["consumer", "enterprise"], var.datadog_domain)
    error_message = "Domain must be either 'consumer' or 'enterprise'."
  }
}

variable "datadog_apm_port_enabled" {
  description = "Enable APM over TCP communication (hostPort 8126 by default)"
  type        = bool
  default     = false
}

variable "chart_version" {
  description = "The version of the Datadog Helm chart to use"
  type        = string
  default     = "3.132.0"
}

variable "agent_cpu_limit" {
  description = "CPU limit for Datadog agent"
  type        = string
  default     = "100m"
  validation {
    condition     = can(regex("^([0-9]+(\\.[0-9]+)?|[0-9]+m)$", var.agent_cpu_limit))
    error_message = "CPU limit must be cores (e.g., '1', '0.5') or millicores (e.g., '100m')."
  }
}

variable "agent_memory_limit" {
  description = "Memory limit for Datadog agent"
  type        = string
  default     = "256Mi"
  validation {
    condition     = can(regex("^(?i)([0-9]+)(Ei|Pi|Ti|Gi|Mi|Ki|E|P|T|G|M|K)?$", var.agent_memory_limit))
    error_message = "Memory limit must be a number optionally suffixed with a unit like Ki, Mi, Gi (e.g., '256Mi', '1Gi')."
  }
}

variable "agent_cpu_request" {
  description = "CPU request for Datadog agent"
  type        = string
  default     = "20m"
  validation {
    condition     = can(regex("^([0-9]+(\\.[0-9]+)?|[0-9]+m)$", var.agent_cpu_request))
    error_message = "CPU request must be cores (e.g., '1', '0.5') or millicores (e.g., '20m')."
  }
}

variable "agent_memory_request" {
  description = "Memory request for Datadog agent"
  type        = string
  default     = "64Mi"
  validation {
    condition     = can(regex("^(?i)([0-9]+)(Ei|Pi|Ti|Gi|Mi|Ki|E|P|T|G|M|K)?$", var.agent_memory_request))
    error_message = "Memory request must be a number optionally suffixed with a unit like Ki, Mi, Gi (e.g., '64Mi', '512Mi')."
  }
}
