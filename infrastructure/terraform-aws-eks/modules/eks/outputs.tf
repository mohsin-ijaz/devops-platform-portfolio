# EKS Module - Outputs

# Cluster outputs
output "cluster_id" {
  description = "EKS cluster ID"
  value       = aws_eks_cluster.this.id
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.this.name
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_version" {
  description = "EKS cluster Kubernetes version"
  value       = aws_eks_cluster.this.version
}

output "cluster_certificate_authority_data" {
  description = "EKS cluster CA certificate"
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "EKS cluster security group ID (created by EKS)"
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

# OIDC outputs
output "oidc_provider_arn" {
  description = "OIDC provider ARN for IRSA"
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  description = "OIDC provider URL"
  value       = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

# IAM Role outputs
output "cluster_iam_role_arn" {
  description = "EKS cluster IAM role ARN"
  value       = aws_iam_role.cluster.arn
}

output "node_iam_role_arn" {
  description = "EKS node IAM role ARN"
  value       = aws_iam_role.node.arn
}

output "node_iam_role_name" {
  description = "EKS node IAM role name"
  value       = aws_iam_role.node.name
}

# IRSA Role outputs
output "ebs_csi_role_arn" {
  description = "EBS CSI driver IRSA role ARN"
  value       = try(aws_iam_role.ebs_csi[0].arn, null)
}

output "cluster_autoscaler_role_arn" {
  description = "Cluster autoscaler IRSA role ARN"
  value       = try(aws_iam_role.cluster_autoscaler[0].arn, null)
}

output "aws_lb_controller_role_arn" {
  description = "AWS Load Balancer Controller IRSA role ARN"
  value       = try(aws_iam_role.aws_lb_controller[0].arn, null)
}

# Node Group outputs
output "node_group_names" {
  description = "List of node group names"
  value       = [for ng in aws_eks_node_group.this : ng.node_group_name]
}

output "node_group_arns" {
  description = "Map of node group ARNs"
  value       = { for k, v in aws_eks_node_group.this : k => v.arn }
}

# kubectl configuration command
output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${local.region} --name ${aws_eks_cluster.this.name}"
}

# ArgoCD cross-cluster access
output "argocd_access_role_arn" {
  description = "IAM role ARN for ArgoCD cross-cluster access"
  value       = try(aws_iam_role.argocd_access[0].arn, null)
}

# ArgoCD IRSA role (for the cluster hosting ArgoCD)
output "argocd_controller_role_arn" {
  description = "IRSA role ARN for ArgoCD application controller"
  value       = try(aws_iam_role.argocd_controller[0].arn, null)
}
