# EKS Addons Module - Variables

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where EKS is deployed"
  type        = string
}

# IRSA Role ARNs
variable "aws_lb_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller"
  type        = string
}

variable "cluster_autoscaler_role_arn" {
  description = "IAM role ARN for Cluster Autoscaler"
  type        = string
}

# Feature toggles
variable "enable_alb_controller" {
  description = "Enable AWS Load Balancer Controller"
  type        = bool
}

variable "enable_cluster_autoscaler" {
  description = "Enable Cluster Autoscaler"
  type        = bool
}

# Version configuration
variable "alb_controller_version" {
  description = "AWS Load Balancer Controller Helm chart version"
  type        = string
}

variable "cluster_autoscaler_version" {
  description = "Cluster Autoscaler Helm chart version"
  type        = string
}

# ArgoCD
variable "enable_argocd" {
  description = "Enable ArgoCD"
  type        = bool
}

variable "argocd_version" {
  description = "ArgoCD Helm chart version"
  type        = string
}

variable "argocd_values" {
  description = "ArgoCD Helm values content"
  type        = string
}

variable "argocd_google_client_id" {
  description = "Google OAuth client ID for ArgoCD"
  type        = string
  default     = ""
  sensitive   = true
}

variable "argocd_google_client_secret" {
  description = "Google OAuth client secret for ArgoCD"
  type        = string
  default     = ""
  sensitive   = true
}

# ArgoCD - UAT cluster registration (for cross-cluster management)
variable "argocd_uat_cluster_name" {
  description = "UAT EKS cluster name for ArgoCD registration"
  type        = string
  default     = ""
}

variable "argocd_uat_cluster_endpoint" {
  description = "UAT EKS cluster endpoint for ArgoCD registration"
  type        = string
  default     = ""
}

variable "argocd_uat_cluster_ca" {
  description = "UAT EKS cluster CA certificate (base64 encoded)"
  type        = string
  default     = ""
}

variable "argocd_uat_role_arn" {
  description = "IAM role ARN for ArgoCD to access UAT cluster"
  type        = string
  default     = ""
}

variable "argocd_hostname" {
  description = "ArgoCD hostname for ACM certificate (e.g., argocd.example.com)"
  type        = string
  default     = ""
}

variable "argocd_controller_role_arn" {
  description = "IRSA role ARN for ArgoCD application controller (for cross-cluster management)"
  type        = string
  default     = ""
}

# Argo Rollouts
variable "enable_argo_rollouts" {
  description = "Enable Argo Rollouts for progressive delivery"
  type        = bool
  default     = false
}

variable "argo_rollouts_version" {
  description = "Argo Rollouts Helm chart version"
  type        = string
  default     = "2.35.1"
}

variable "argo_rollouts_values" {
  description = "Argo Rollouts Helm values content"
  type        = string
  default     = ""
}

# ArgoCD Image Updater
variable "enable_argocd_image_updater" {
  description = "Enable ArgoCD Image Updater for automatic image updates"
  type        = bool
  default     = false
}

variable "argocd_image_updater_version" {
  description = "ArgoCD Image Updater Helm chart version"
  type        = string
  default     = "0.9.6"
}

variable "argocd_image_updater_values" {
  description = "ArgoCD Image Updater Helm values content"
  type        = string
  default     = ""
}

variable "image_updater_ecr_account_ids" {
  description = "List of AWS account IDs for ECR access (UAT and Prod)"
  type        = list(string)
  default     = []
}

# Rollback Controller
variable "enable_rollback_controller" {
  description = "Enable the rollback controller for one-click Rollout rollback via ArgoCD UI"
  type        = bool
  default     = false
}

variable "rollback_controller_gitlab_token" {
  description = "GitLab PAT with write_repository scope for the rollback controller"
  type        = string
  default     = ""
  sensitive   = true
}

variable "rollback_uat_cluster_server" {
  description = "UAT EKS cluster API server URL for rollback controller cross-cluster scanning"
  type        = string
  default     = ""
}

variable "rollback_uat_cluster_token" {
  description = "UAT cluster service account bearer token for rollback controller"
  type        = string
  default     = ""
  sensitive   = true
}

# Rollback Controller - Target cluster SA (for clusters scanned by the controller)
variable "enable_rollback_target_sa" {
  description = "Create a ServiceAccount on this cluster for rollback controller remote scanning"
  type        = bool
  default     = false
}
