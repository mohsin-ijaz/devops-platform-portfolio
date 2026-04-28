variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "project" {
  type = string
}

variable "node_locations" {
  type = list(string)
}

variable "enable_backup_agent" {
  description = "Enable GKE Backup Agent addon (optional)"
  type        = bool
  default     = false
}


variable "initial_node_count" {
  type = number
}

variable "channel" {
  type = string
}

variable "cluster_secondary_range_name" {
  type = string
}

variable "services_secondary_range_name" {
  type = string
}

variable "network" {
  type = string
}
variable "min_master_version" {
  type = string
}

variable "subnetwork" {
  type = string
}

variable "enable_private_endpoint" {
  type = bool
}

variable "remove_default_node_pool" {
  type = bool
}

variable "enable_private_nodes" {
  type = bool
}

variable "master_ipv4_cidr_block" {
  type = string
}

variable "enable_shielded_nodes" {
  type = bool
}

variable "workload_pool" {
  type = string
}

variable "issue_client_certificate" {
  type = bool
}

variable "display_name" {
  type = string
}

variable "enable_components" {
  type = list(string)
}



variable "node_count" {
  type = number
}



variable "image_type" {
  type = string
}

variable "local_ssd_count" {
  type = number
}



variable "service_account" {
  type = string
}

variable "oauth_scopes" {
  type = list(string)
}



variable "max_surge" {
  type = number
}

variable "max_unavailable" {
  type = number
}

variable "enable_integrity_monitoring" {
  type = bool
}

variable "enable_secure_boot" {
  type = bool
}

variable "network_policy" {
  type = bool
}

variable "master_global_access" {
  type = bool
}


variable "authorized_networks" {
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
}

variable "gateway_api_channel" {
  type        = string
  description = "The gateway api channel of this cluster. Accepted values are CHANNEL_STANDARD and CHANNEL_DISABLED."

}



variable "gcp_public_cidrs_access_enabled" {
  description = "If set true Kubernetes master will be accessible via Google Compute Engine Public IPs"
  type        = bool
}

variable "private_endpoint_enforcement_enabled" {
  description = "If set true authorized networks will be enforced on the private endpoint"
  type        = bool
}


variable "maintenance_start_time" {
  description = "Start time for the recurring maintenance window (UTC, RFC3339 format)"
  type        = string
  default     = "2025-01-10T16:00:00Z" # Sat 12AM MYT
}

variable "maintenance_end_time" {
  description = "End time for the recurring maintenance window (UTC, RFC3339 format)"
  type        = string
  default     = "2025-01-12T18:00:00Z" # Mon 2AM MYT
}

variable "maintenance_recurrence" {
  description = "Recurrence rule for the maintenance window"
  type        = string
  default     = "FREQ=WEEKLY;BYDAY=SA"
}

variable "labels" {
  description = "Labels to apply to the GKE cluster"
  type        = map(string)
  default     = {}
}






variable "node_pools" {
  type = list(object({
    name              = string
    node_version      = string
    machine_type      = string
    disk_size_gb      = number
    disk_type         = string
    min_node_count    = number
    max_node_count    = number
    auto_repair       = bool
    auto_upgrade      = bool
    max_pods_per_node = number
    preemptible       = bool
    tags              = optional(list(string))
    labels            = optional(map(string), {})
    taints = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
  }))
}
