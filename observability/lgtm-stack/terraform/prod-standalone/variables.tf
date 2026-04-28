# Variables for LGTM Production Infrastructure

variable "project_id" {
  description = "GCP Project ID where LGTM stack is deployed"
  type        = string
  default     = "<GCP_MGMT_PROJECT>"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "<GCP_REGION>"
}

variable "cluster_name" {
  description = "GKE cluster name where LGTM will be deployed"
  type        = string
  default     = "<GKE_MGMT_CLUSTER>"
}

variable "cluster_location" {
  description = "GKE cluster location (zone or region)"
  type        = string
  default     = "<GCP_REGION>-a"
}
