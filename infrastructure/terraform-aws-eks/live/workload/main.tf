# Workload Account

# VPC

module "vpc" {
  source = "../../modules/vpc"

  name                   = local.name_prefix
  vpc_cidr               = var.vpc_cidr
  availability_zones     = var.availability_zones
  private_subnet_cidrs   = var.private_subnet_cidrs
  database_subnet_cidrs  = var.database_subnet_cidrs
  nat_subnet_cidrs       = var.nat_subnet_cidrs
  single_nat_gateway     = var.single_nat_gateway
  enable_dns_hostnames   = var.enable_dns_hostnames
  enable_dns_support     = var.enable_dns_support
  transit_gateway_id     = var.enable_transit_gateway ? local.transit_gateway_id : ""
  transit_gateway_routes = var.enable_transit_gateway ? var.transit_gateway_routes : []

  tags = {
    Component = "vpc"
  }
}

# Security Groups

module "security_groups" {
  source = "../../modules/security-groups"

  name                = local.name_prefix
  vpc_id              = module.vpc.vpc_id
  vpc_cidr            = var.vpc_cidr
  onprem_cidrs        = local.onprem_cidrs
  argocd_source_cidrs = var.argocd_source_cidrs

  tags = {
    Component = "security-groups"
  }
}

# VPC Endpoints

module "vpc_endpoints" {
  source = "../../modules/vpc-endpoints"
  count  = var.enable_vpc_endpoints ? 1 : 0

  name             = local.name_prefix
  vpc_id           = module.vpc.vpc_id
  vpc_cidr         = var.vpc_cidr
  subnet_ids       = module.vpc.private_subnet_ids
  route_table_ids  = concat(module.vpc.private_route_table_ids, [module.vpc.database_route_table_id])
  aws_region       = var.aws_region
  enable_endpoints = var.enable_endpoints

  tags = {
    Component = "vpc-endpoints"
  }
}

# Transit Gateway Attachment

module "tgw_attachment" {
  source = "../../modules/tgw-attachment"
  count  = var.enable_transit_gateway && local.transit_gateway_id != "" ? 1 : 0

  name                           = local.name_prefix
  vpc_id                         = module.vpc.vpc_id
  subnet_ids                     = module.vpc.private_subnet_ids
  transit_gateway_id             = local.transit_gateway_id
  transit_gateway_route_table_id = local.tgw_vpc_route_table_id
  associate_with_route_table     = var.tgw_associate_with_route_table
  dns_support                    = var.tgw_dns_support

  tags = {
    Component = "tgw-attachment"
  }
}

# EKS Cluster

module "eks" {
  source = "../../modules/eks"

  name                      = "${local.name_prefix}-eks"
  cluster_version           = var.eks_cluster_version
  vpc_id                    = module.vpc.vpc_id
  subnet_ids                = module.vpc.private_subnet_ids
  cluster_security_group_id = module.security_groups.eks_cluster_security_group_id
  node_security_group_id    = module.security_groups.eks_nodes_security_group_id
  endpoint_private_access   = var.eks_endpoint_private_access
  endpoint_public_access    = var.eks_endpoint_public_access
  service_cidr              = var.eks_service_cidr
  node_groups               = var.eks_node_groups
  cluster_addons            = var.eks_cluster_addons
  enable_cluster_autoscaler_irsa = var.enable_cluster_autoscaler_irsa
  enable_aws_lb_controller_irsa  = var.enable_aws_lb_controller_irsa
  enable_ebs_csi_irsa            = var.enable_ebs_csi_irsa
  authentication_mode       = var.eks_authentication_mode
  cluster_admin_arns        = var.enable_bastion ? [module.bastion[0].iam_role_arn] : []

  # ArgoCD cross-cluster access (for target clusters)
  enable_argocd_access     = var.enable_argocd_access
  argocd_source_account_id = var.argocd_source_account_id

  # ArgoCD IRSA (for the cluster hosting ArgoCD)
  enable_argocd_irsa      = var.enable_argocd_irsa
  argocd_target_role_arns = var.argocd_target_role_arns

  tags = {
    Component = "eks"
  }
}

# Bastion Host

module "bastion" {
  source = "../../modules/bastion"
  count  = var.enable_bastion ? 1 : 0

  name                = local.name_prefix
  subnet_id           = module.vpc.private_subnet_ids[0]
  security_group_ids  = [module.security_groups.bastion_security_group_id]
  instance_type       = var.bastion_instance_type
  associate_public_ip = var.bastion_associate_public_ip
  enable_monitoring   = var.bastion_enable_monitoring
  root_volume_size    = var.bastion_root_volume_size
  eks_cluster_name    = local.eks_name
  aws_region          = var.aws_region
  gitlab_runner_token = var.gitlab_runner_token
  gitlab_runner_url   = var.gitlab_runner_url
  gitlab_runner_tag   = var.gitlab_runner_tag

  tags = {
    Component = "bastion"
  }
}

# ECR Repositories for JPJ Services

module "ecr" {
  source = "../../modules/ecr"
  count  = var.enable_ecr ? 1 : 0

  repository_names        = var.ecr_repository_names
  image_tag_mutability    = var.ecr_image_tag_mutability
  scan_on_push            = var.ecr_scan_on_push
  enable_lifecycle_policy = var.ecr_enable_lifecycle_policy
  max_image_count         = var.ecr_max_image_count

  tags = {
    Component = "ecr"
  }
}

# GitLab CI Role for JPJ Application Pipelines

module "gitlab_ci_role" {
  source = "../../modules/gitlab-ci-role"
  count  = var.enable_gitlab_ci_role ? 1 : 0

  role_name        = var.gitlab_ci_role_name
  gitlab_url       = var.gitlab_url
  allowed_subjects = var.gitlab_ci_allowed_subjects
  enable_ecr_access = true
  ecr_repository_arns = var.enable_ecr ? [for arn in values(module.ecr[0].repository_arns) : arn] : []
  enable_eks_access = true

  tags = {
    Component = "gitlab-ci-role"
  }

  depends_on = [module.ecr]
}
