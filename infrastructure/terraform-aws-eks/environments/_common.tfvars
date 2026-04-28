# Common Variables - Shared across UAT and Prod

project_name = "otis"
company      = "acme"
aws_region   = "<AWS_REGION>"

# Account IDs
network_account_id = "<AWS_NETWORK_ACCOUNT_ID>"

# VPC
enable_dns_hostnames = true
enable_dns_support   = true

# Transit Gateway
enable_transit_gateway         = true
transit_gateway_id             = ""
transit_gateway_routes         = ["192.168.0.0/16"]
tgw_associate_with_route_table = false
tgw_dns_support                = "enable"

# VPC Endpoints
enable_vpc_endpoints = true
enable_endpoints = {
  s3                   = true
  ecr_api              = true
  ecr_dkr              = true
  sts                  = true
  logs                 = true
  ssm                  = true
  ssmmessages          = true
  ec2messages          = false
  ec2                  = true
  eks                  = true
  secretsmanager       = true
  autoscaling          = true
  elasticloadbalancing = true
}

# EKS
eks_endpoint_private_access    = true
eks_endpoint_public_access     = false
eks_service_cidr               = "172.20.0.0/16"
eks_authentication_mode        = "API_AND_CONFIG_MAP"
enable_cluster_autoscaler_irsa = true
enable_aws_lb_controller_irsa  = true
enable_ebs_csi_irsa            = true
eks_cluster_addons = {
  vpc-cni = {
    version                  = ""
    resolve_conflicts        = "OVERWRITE"
    service_account_role_arn = ""
  }
  coredns = {
    version                  = ""
    resolve_conflicts        = "OVERWRITE"
    service_account_role_arn = ""
  }
  kube-proxy = {
    version                  = ""
    resolve_conflicts        = "OVERWRITE"
    service_account_role_arn = ""
  }
  aws-ebs-csi-driver = {
    version                  = ""
    resolve_conflicts        = "OVERWRITE"
    service_account_role_arn = ""
  }
}

# Bastion
enable_bastion              = true
bastion_associate_public_ip = false
bastion_enable_monitoring   = false
bastion_root_volume_size    = 20

# On-premises CIDRs
onprem_cidrs = ["192.168.0.0/16"]

# GitLab Runner (token passed via CI/CD variable)
gitlab_runner_url = "https://gitlab.com"
