# Workload Account - Outputs

# VPC
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = module.vpc.vpc_cidr
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "database_subnet_ids" {
  description = "Database subnet IDs"
  value       = module.vpc.database_subnet_ids
}

output "nat_gateway_public_ips" {
  description = "NAT Gateway public IPs"
  value       = module.vpc.nat_gateway_public_ips
}

# Security Groups
output "eks_cluster_security_group_id" {
  description = "EKS cluster security group ID"
  value       = module.security_groups.eks_cluster_security_group_id
}

output "eks_nodes_security_group_id" {
  description = "EKS nodes security group ID"
  value       = module.security_groups.eks_nodes_security_group_id
}

output "bastion_security_group_id" {
  description = "Bastion security group ID"
  value       = module.security_groups.bastion_security_group_id
}

output "database_security_group_id" {
  description = "Database security group ID"
  value       = module.security_groups.database_security_group_id
}

# Transit Gateway
output "tgw_attachment_id" {
  description = "Transit Gateway VPC attachment ID"
  value       = try(module.tgw_attachment[0].attachment_id, null)
}

# EKS
output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_version" {
  description = "EKS cluster version"
  value       = module.eks.cluster_version
}

output "eks_oidc_provider_arn" {
  description = "EKS OIDC provider ARN"
  value       = module.eks.oidc_provider_arn
}

output "eks_cluster_autoscaler_role_arn" {
  description = "Cluster autoscaler IRSA role ARN"
  value       = module.eks.cluster_autoscaler_role_arn
}

output "eks_aws_lb_controller_role_arn" {
  description = "AWS LB Controller IRSA role ARN"
  value       = module.eks.aws_lb_controller_role_arn
}

output "eks_configure_kubectl" {
  description = "Command to configure kubectl"
  value       = module.eks.configure_kubectl
}

# Bastion
output "bastion_instance_id" {
  description = "Bastion EC2 instance ID"
  value       = try(module.bastion[0].instance_id, null)
}

output "bastion_ssm_connect_command" {
  description = "SSM command to connect to bastion"
  value       = try(module.bastion[0].ssm_connect_command, null)
}

# ECR
output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value       = try(module.ecr[0].repository_urls, {})
}

output "ecr_repository_arns" {
  description = "ECR repository ARNs"
  value       = try(module.ecr[0].repository_arns, {})
}

# GitLab CI Role
output "gitlab_ci_role_arn" {
  description = "GitLab CI role ARN"
  value       = try(module.gitlab_ci_role[0].role_arn, null)
}

# ArgoCD
output "argocd_access_role_arn" {
  description = "IAM role ARN for ArgoCD cross-cluster access"
  value       = module.eks.argocd_access_role_arn
}

output "argocd_controller_role_arn" {
  description = "IRSA role ARN for ArgoCD application controller"
  value       = module.eks.argocd_controller_role_arn
}
