# Security Groups Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "onprem_cidrs" {
  description = "On-premises CIDR blocks for inbound access"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}

variable "argocd_source_cidrs" {
  description = "CIDR blocks that ArgoCD uses to access this cluster (for cross-cluster management)"
  type        = list(string)
  default     = []
}
