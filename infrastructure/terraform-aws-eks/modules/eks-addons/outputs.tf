# EKS Addons Module - Outputs

output "alb_controller_release_name" {
  description = "AWS Load Balancer Controller Helm release name"
  value       = var.enable_alb_controller ? helm_release.aws_lb_controller[0].name : null
}

output "alb_controller_release_status" {
  description = "AWS Load Balancer Controller Helm release status"
  value       = var.enable_alb_controller ? helm_release.aws_lb_controller[0].status : null
}

output "cluster_autoscaler_release_name" {
  description = "Cluster Autoscaler Helm release name"
  value       = var.enable_cluster_autoscaler ? helm_release.cluster_autoscaler[0].name : null
}

output "cluster_autoscaler_release_status" {
  description = "Cluster Autoscaler Helm release status"
  value       = var.enable_cluster_autoscaler ? helm_release.cluster_autoscaler[0].status : null
}

# ArgoCD ACM Certificate outputs
output "argocd_acm_certificate_arn" {
  description = "ArgoCD ACM certificate ARN"
  value       = var.enable_argocd && var.argocd_hostname != "" ? aws_acm_certificate.argocd[0].arn : null
}

output "argocd_acm_validation_records" {
  description = "DNS validation records to add in Cloudflare for ArgoCD certificate"
  value = var.enable_argocd && var.argocd_hostname != "" ? {
    for dvo in aws_acm_certificate.argocd[0].domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  } : null
}

# Argo Rollouts
output "argo_rollouts_release_name" {
  description = "Argo Rollouts Helm release name"
  value       = var.enable_argo_rollouts ? helm_release.argo_rollouts[0].name : null
}

output "argo_rollouts_release_status" {
  description = "Argo Rollouts Helm release status"
  value       = var.enable_argo_rollouts ? helm_release.argo_rollouts[0].status : null
}

# ArgoCD Image Updater
output "argocd_image_updater_release_name" {
  description = "ArgoCD Image Updater Helm release name"
  value       = var.enable_argocd_image_updater && var.enable_argocd ? helm_release.argocd_image_updater[0].name : null
}

output "argocd_image_updater_release_status" {
  description = "ArgoCD Image Updater Helm release status"
  value       = var.enable_argocd_image_updater && var.enable_argocd ? helm_release.argocd_image_updater[0].status : null
}

output "argocd_image_updater_role_arn" {
  description = "IRSA role ARN for ArgoCD Image Updater"
  value       = var.enable_argocd_image_updater ? aws_iam_role.image_updater[0].arn : null
}

# Rollback Controller - Target SA token (for remote cluster scanning)
output "rollback_target_sa_token" {
  description = "Bearer token for the rollback controller remote SA (extract and store in CI/CD variables)"
  value       = var.enable_rollback_target_sa ? kubernetes_secret.rollback_target_token[0].data["token"] : null
  sensitive   = true
}
