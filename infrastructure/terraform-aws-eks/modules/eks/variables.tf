# EKS Module - Variables

variable "name" {
  description = "Name for the EKS cluster"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for EKS cluster and nodes"
  type        = list(string)
}

variable "cluster_security_group_id" {
  description = "Security group ID for EKS cluster"
  type        = string
}

variable "node_security_group_id" {
  description = "Security group ID for EKS nodes"
  type        = string
}

variable "endpoint_private_access" {
  description = "Enable private API endpoint"
  type        = bool
}

variable "endpoint_public_access" {
  description = "Enable public API endpoint"
  type        = bool
}

variable "service_cidr" {
  description = "Service CIDR for Kubernetes services"
  type        = string
}

variable "node_groups" {
  description = "Map of node group configurations"
  type = map(object({
    instance_types = list(string)
    disk_size      = number
    min_size       = number
    desired_size   = number
    max_size       = number
    capacity_type  = string
    ami_type       = string
    labels         = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
}

variable "enable_cluster_autoscaler_irsa" {
  description = "Create IRSA role for cluster autoscaler"
  type        = bool
}

variable "enable_aws_lb_controller_irsa" {
  description = "Create IRSA role for AWS Load Balancer Controller"
  type        = bool
}

variable "enable_ebs_csi_irsa" {
  description = "Create IRSA role for EBS CSI driver"
  type        = bool
}

variable "cluster_addons" {
  description = "Map of cluster addons to install"
  type = map(object({
    version                  = string
    resolve_conflicts        = string
    service_account_role_arn = string
  }))
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}

variable "cluster_admin_arns" {
  description = "List of IAM role/user ARNs to grant cluster admin access via EKS Access Entries"
  type        = list(string)
}

variable "authentication_mode" {
  description = "EKS authentication mode (API, CONFIG_MAP, or API_AND_CONFIG_MAP)"
  type        = string
}

# ArgoCD cross-cluster access
variable "enable_argocd_access" {
  description = "Create IAM role for ArgoCD cross-cluster access"
  type        = bool
  default     = false
}

variable "argocd_source_account_id" {
  description = "AWS account ID where ArgoCD is deployed (for cross-account trust)"
  type        = string
  default     = ""
}

# ArgoCD IRSA (for the cluster hosting ArgoCD)
variable "enable_argocd_irsa" {
  description = "Create IRSA role for ArgoCD application controller (for cross-cluster management)"
  type        = bool
  default     = false
}

variable "argocd_target_role_arns" {
  description = "List of IAM role ARNs that ArgoCD can assume for cross-cluster management"
  type        = list(string)
  default     = []
}
