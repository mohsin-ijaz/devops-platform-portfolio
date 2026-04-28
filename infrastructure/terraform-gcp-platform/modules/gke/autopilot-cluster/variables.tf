variable "project_id" {
  description = "The ID of the project where this GKE Cluster will be created"
  type        = string
}

variable "name" {
  description = "Name of the cluster to be created"
  type        = string
}

variable "region" {
  type = string
}

variable "allow_net_admin" {
  type        = bool
  description = "Enable NET_ADMIN for the cluster. Defaults to false. This field should only be enabled for Autopilot clusters"
}

variable "network" {
  description = "Name of the VPC in which Cluster to be created"
  type        = string
}

variable "subnet" {
  description = "Name of the Subnet in which Cluster to be created"
  type        = string
}

variable "enable_private_nodes" {
  description = "If set true cluster created will be private"
  type        = bool
}

variable "enable_private_endpoint" {
  description = "If set true cluster created private endpoints"
  type        = bool
}

variable "service_account" {
  description = "Service account that needs to be assigned to the cluster"
  type        = string
}

variable "oauth_scopes" {
  description = "Scopes for the service account"
  type        = list(string)
}

variable "enable_autopilot" {
  description = "If set true cluster created will be autopilot | set false for standard cluster"
  type        = bool
}

variable "deletion_protection" {
  description = "If set true deletion protection will be enabled"
  type        = bool
}

variable "cluster_secondary_range_name" {
  description = "Secondary range name for the cluster"
  type        = string
}

variable "services_secondary_range_name" {
  description = "Service Secondary range name for the cluster"
  type        = string
}

variable "gcp_public_cidrs_access_enabled" {
  description = "If set true Kubernetes master will be accessible via Google Compute Engine Public IPs"
  type        = bool
}

variable "private_endpoint_enforcement_enabled" {
  description = "If set true authorized networks will be enforced on the private endpoint"
  type        = bool
}

variable "authorized_networks" {
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
}