# Security Groups Module - Outputs

output "eks_cluster_security_group_id" {
  description = "EKS cluster (control plane) security group ID"
  value       = aws_security_group.eks_cluster.id
}

output "eks_nodes_security_group_id" {
  description = "EKS nodes security group ID"
  value       = aws_security_group.eks_nodes.id
}

output "bastion_security_group_id" {
  description = "Bastion security group ID"
  value       = aws_security_group.bastion.id
}

output "alb_internal_security_group_id" {
  description = "Internal ALB security group ID"
  value       = aws_security_group.alb_internal.id
}

output "database_security_group_id" {
  description = "Database security group ID"
  value       = aws_security_group.database.id
}

output "all_security_group_ids" {
  description = "Map of all security group IDs"
  value = {
    eks_cluster  = aws_security_group.eks_cluster.id
    eks_nodes    = aws_security_group.eks_nodes.id
    bastion      = aws_security_group.bastion.id
    alb_internal = aws_security_group.alb_internal.id
    database     = aws_security_group.database.id
  }
}
