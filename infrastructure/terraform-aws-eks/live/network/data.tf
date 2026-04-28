# Network Account - Data Sources

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# Remote State - UAT Account

data "terraform_remote_state" "uat" {
  count = var.enable_workload_routes ? 1 : 0

  backend = "s3"
  config = {
    bucket = "acme-otis-terraform-state-${var.uat_account_id}"
    key    = "uat/terraform.tfstate"
    region = var.aws_region
  }
}

# Remote State - Production Account

data "terraform_remote_state" "prod" {
  count = var.enable_workload_routes ? 1 : 0

  backend = "s3"
  config = {
    bucket = "acme-otis-terraform-state-${var.prod_account_id}"
    key    = "prod/terraform.tfstate"
    region = var.aws_region
  }
}

# Locals

locals {
  uat_vpc_cidr          = try(data.terraform_remote_state.uat[0].outputs.vpc_cidr, null)
  uat_tgw_attachment_id = try(data.terraform_remote_state.uat[0].outputs.tgw_attachment_id, null)

  prod_vpc_cidr          = try(data.terraform_remote_state.prod[0].outputs.vpc_cidr, null)
  prod_tgw_attachment_id = try(data.terraform_remote_state.prod[0].outputs.tgw_attachment_id, null)
}
