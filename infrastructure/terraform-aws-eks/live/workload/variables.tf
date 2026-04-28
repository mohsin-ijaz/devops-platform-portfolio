# Workload Account - Variables

# General
variable "project_name" {
  description = "Project name"
  type        = string
}

variable "company" {
  description = "Company name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name (uat, prod)"
  type        = string

  validation {
    condition     = contains(["uat", "prod"], var.environment)
    error_message = "Environment must be one of: uat, prod."
  }
}

# Account IDs
variable "network_account_id" {
  description = "Network account ID (for remote state)"
  type        = string
}

# VPC Configuration
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDR blocks"
  type        = list(string)
}

variable "database_subnet_cidrs" {
  description = "Database subnet CIDR blocks"
  type        = list(string)
}

variable "nat_subnet_cidrs" {
  description = "NAT subnet CIDR blocks"
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use single NAT gateway"
  type        = bool
}

variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames in VPC"
  type        = bool
}

variable "enable_dns_support" {
  description = "Enable DNS support in VPC"
  type        = bool
}

# Transit Gateway
variable "enable_transit_gateway" {
  description = "Enable Transit Gateway attachment"
  type        = bool
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID (from network account)"
  type        = string
}

variable "transit_gateway_routes" {
  description = "CIDR blocks to route via Transit Gateway"
  type        = list(string)
}

variable "tgw_associate_with_route_table" {
  description = "Whether to associate TGW attachment with route table"
  type        = bool
}

variable "tgw_dns_support" {
  description = "Enable DNS support for TGW attachment"
  type        = string
}

# VPC Endpoints
variable "enable_vpc_endpoints" {
  description = "Enable VPC endpoints"
  type        = bool
}

variable "enable_endpoints" {
  description = "Map of endpoints to enable"
  type        = map(bool)
}

# EKS Configuration
variable "eks_cluster_version" {
  description = "EKS cluster version"
  type        = string
}

variable "eks_node_groups" {
  description = "EKS node group configurations"
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

variable "eks_endpoint_private_access" {
  description = "Enable private API endpoint"
  type        = bool
}

variable "eks_endpoint_public_access" {
  description = "Enable public API endpoint"
  type        = bool
}

variable "eks_service_cidr" {
  description = "Service CIDR for Kubernetes services"
  type        = string
}

variable "eks_cluster_addons" {
  description = "Map of cluster addons to install"
  type = map(object({
    version                  = string
    resolve_conflicts        = string
    service_account_role_arn = string
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

variable "eks_authentication_mode" {
  description = "EKS authentication mode"
  type        = string
}

# Bastion
variable "enable_bastion" {
  description = "Enable bastion host"
  type        = bool
}

variable "bastion_instance_type" {
  description = "Bastion instance type"
  type        = string
}

variable "bastion_associate_public_ip" {
  description = "Associate public IP with bastion"
  type        = bool
}

variable "bastion_enable_monitoring" {
  description = "Enable detailed monitoring for bastion"
  type        = bool
}

variable "bastion_root_volume_size" {
  description = "Bastion root volume size in GB"
  type        = number
}

# On-premises CIDRs
variable "onprem_cidrs" {
  description = "On-premises CIDR blocks"
  type        = list(string)
}

# GitLab Runner
variable "gitlab_runner_token" {
  description = "GitLab Runner registration token"
  type        = string
  sensitive   = true
}

variable "gitlab_runner_url" {
  description = "GitLab instance URL"
  type        = string
}

variable "gitlab_runner_tag" {
  description = "GitLab Runner tag for job matching"
  type        = string
}

# ArgoCD Cross-Cluster Access
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

variable "argocd_source_cidrs" {
  description = "CIDR blocks that ArgoCD uses to access this cluster (for cross-cluster management via TGW)"
  type        = list(string)
  default     = []
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

# ECR
variable "enable_ecr" {
  description = "Enable ECR repositories"
  type        = bool
  default     = false
}

variable "ecr_repository_names" {
  description = "List of ECR repository names"
  type        = list(string)
  default     = []
}

variable "ecr_image_tag_mutability" {
  description = "ECR image tag mutability"
  type        = string
  default     = "MUTABLE"
}

variable "ecr_scan_on_push" {
  description = "Enable ECR scan on push"
  type        = bool
  default     = true
}

variable "ecr_enable_lifecycle_policy" {
  description = "Enable ECR lifecycle policy"
  type        = bool
  default     = true
}

variable "ecr_max_image_count" {
  description = "Maximum number of images to keep"
  type        = number
  default     = 30
}

# GitLab CI Role
variable "enable_gitlab_ci_role" {
  description = "Enable GitLab CI role for application pipelines"
  type        = bool
  default     = false
}

variable "gitlab_ci_role_name" {
  description = "Name of the GitLab CI role"
  type        = string
  default     = "GitLabCIRole"
}

variable "gitlab_url" {
  description = "GitLab URL for OIDC"
  type        = string
  default     = "https://gitlab.com"
}

variable "gitlab_ci_allowed_subjects" {
  description = "List of allowed GitLab subjects for CI role"
  type        = list(string)
  default     = []
}
