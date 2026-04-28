# UAT Environment

environment = "uat"
vpc_cidr    = "10.101.0.0/16"

availability_zones    = ["<AWS_REGION>a", "<AWS_REGION>b"]
private_subnet_cidrs  = ["10.101.0.0/20", "10.101.16.0/20"]
database_subnet_cidrs = ["10.101.48.0/20", "10.101.64.0/20"]
nat_subnet_cidrs      = ["10.101.96.0/24", "10.101.97.0/24"]

single_nat_gateway    = true
bastion_instance_type = "t3.medium"

# GitLab Runner
gitlab_runner_tag = "acme-platform-uat-runner"

# EKS
eks_cluster_version = "1.35"
eks_node_groups = {
  general = {
    instance_types = ["t3.medium"]
    disk_size      = 50
    min_size       = 1
    desired_size   = 1
    max_size       = 4
    capacity_type  = "ON_DEMAND"
    ami_type       = "BOTTLEROCKET_x86_64"
    labels = {
      environment = "uat"
      workload    = "general"
    }
    taints = []
  }
}

# Transit Gateway routes (add Prod VPC CIDR for cross-cluster communication)
transit_gateway_routes = ["192.168.0.0/16", "10.102.0.0/16"]

# ArgoCD cross-cluster access (allow prod ArgoCD to manage UAT cluster)
enable_argocd_access     = true
argocd_source_account_id = "<AWS_ACCOUNT_ID>"
argocd_source_cidrs      = ["10.102.0.0/16"]

# ECR Repositories
enable_ecr = true
ecr_repository_names = [
  "platform-service-web",
  "platform-inspection-cms",
  "platform-inspection-server"
]

# GitLab CI Role for Application Pipelines
enable_gitlab_ci_role = true
gitlab_ci_role_name   = "GitLabCIRole"
gitlab_ci_allowed_subjects = [
  "project_path:acme/infrastructure/acme-platform-terraform-infra:ref_type:branch:ref:main",
  "project_path:acme/infrastructure/acme-platform-terraform-infra:ref_type:branch:ref:master",
  "project_path:acme/china-team/platform-service-web:*",
  "project_path:acme/china-team/platform-inspection-cms:*",
  "project_path:acme/china-team/platform-inspection-server:*"
]
