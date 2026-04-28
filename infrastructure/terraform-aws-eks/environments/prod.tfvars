# Production Environment

environment = "prod"
vpc_cidr    = "10.102.0.0/16"

availability_zones    = ["<AWS_REGION>a", "<AWS_REGION>b"]
private_subnet_cidrs  = ["10.102.0.0/20", "10.102.16.0/20"]
database_subnet_cidrs = ["10.102.48.0/20", "10.102.64.0/20"]
nat_subnet_cidrs      = ["10.102.96.0/24", "10.102.97.0/24"]

# For 3 AZs:
# availability_zones    = ["<AWS_REGION>a", "<AWS_REGION>b", "<AWS_REGION>c"]
# private_subnet_cidrs  = ["10.102.0.0/20", "10.102.16.0/20", "10.102.32.0/20"]
# database_subnet_cidrs = ["10.102.48.0/20", "10.102.64.0/20", "10.102.80.0/20"]
# nat_subnet_cidrs      = ["10.102.96.0/24", "10.102.97.0/24", "10.102.98.0/24"]

single_nat_gateway    = true
bastion_instance_type = "t3.medium"

# GitLab Runner
gitlab_runner_tag = "acme-platform-prod-runner"

# Transit Gateway routes (add UAT VPC CIDR for cross-cluster communication)
transit_gateway_routes = ["192.168.0.0/16", "10.101.0.0/16"]

# ArgoCD IRSA (for cross-cluster management)
enable_argocd_irsa      = true
argocd_target_role_arns = ["arn:aws:iam::<AWS_ACCOUNT_ID>:role/acme-otis-uat-eks-argocd-access"]

# Allow UAT VPC to access prod EKS cluster (for UAT runner to manage ArgoCD)
argocd_source_cidrs = ["10.101.0.0/16"]

# EKS
eks_cluster_version = "1.35"
eks_node_groups = {
  general = {
    instance_types = ["t3.medium"]
    disk_size      = 50
    min_size       = 1
    desired_size   = 3
    max_size       = 10
    capacity_type  = "ON_DEMAND"
    ami_type       = "BOTTLEROCKET_x86_64"
    labels = {
      environment = "prod"
      workload    = "general"
    }
    taints = []
  }
}

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
