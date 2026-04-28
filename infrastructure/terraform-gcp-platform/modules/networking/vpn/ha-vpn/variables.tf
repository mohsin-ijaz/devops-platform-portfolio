variable "stack_type" {
  description = "The IP stack type will apply to all the tunnels associated with this VPN gateway."
  type        = string
  default     = "IPV4_ONLY"
}

variable "network" {
  description = "VPC used for the gateway and routes."
  type        = string
}

variable "project_id" {
  description = "Project where resources will be created."
  type        = string
}

variable "region" {
  description = "Region used for resources."
  type        = string
}

variable "name" {
  description = "VPN gateway name, and prefix used for dependent resources."
  type        = string
}


variable "env" {
  description = "The environment (e.g., dev, staging, prod) used for naming resources."
  type        = string
}

variable "region_code" {
  description = "The region code used for naming purposes (e.g., us-central1, us-east1)."
  type        = string
}
