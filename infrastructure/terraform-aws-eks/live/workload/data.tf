# Workload Account - Data Sources

data "aws_caller_identity" "current" {}

# Remote state from network account
data "terraform_remote_state" "network" {
  count = var.enable_transit_gateway && var.transit_gateway_id == "" ? 1 : 0

  backend = "s3"
  config = {
    bucket = "acme-otis-terraform-state-${var.network_account_id}"
    key    = "network/terraform.tfstate"
    region = var.aws_region
  }
}

locals {
  name_prefix = "${var.company}-${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id

  # Transit Gateway ID from remote state or variable
  transit_gateway_id     = var.transit_gateway_id != "" ? var.transit_gateway_id : try(data.terraform_remote_state.network[0].outputs.transit_gateway_id, "")
  tgw_vpc_route_table_id = try(data.terraform_remote_state.network[0].outputs.vpc_route_table_id, "")

  # On-prem CIDRs from Network state (fallback to variable)
  onprem_cidrs = try(data.terraform_remote_state.network[0].outputs.onprem_cidrs, var.onprem_cidrs)

  # EKS name
  eks_name = "${local.name_prefix}-eks"
}
