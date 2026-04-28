# Network Account

locals {
  name_prefix = "${var.company}-${var.project_name}"
}

# Transit Gateway

module "transit_gateway" {
  source = "../../modules/transit-gateway"

  name                            = local.name_prefix
  amazon_side_asn                 = var.tgw_amazon_side_asn
  auto_accept_shared_attachments  = var.tgw_auto_accept_shared_attachments
  default_route_table_association = var.tgw_default_route_table_association
  default_route_table_propagation = var.tgw_default_route_table_propagation
  dns_support                     = var.tgw_dns_support
  vpn_ecmp_support                = var.tgw_vpn_ecmp_support
  share_with_account_ids          = [var.uat_account_id, var.prod_account_id]

  tags = {
    Component = "transit-gateway"
  }
}

# VPN Connection

module "vpn" {
  source = "../../modules/vpn"
  count  = var.enable_vpn && var.customer_gateway_ip != "0.0.0.0" ? 1 : 0

  name                           = local.name_prefix
  transit_gateway_id             = module.transit_gateway.transit_gateway_id
  customer_gateway_ip            = var.customer_gateway_ip
  customer_gateway_bgp_asn       = var.customer_gateway_bgp_asn
  vpn_type                       = var.vpn_type
  static_routes_only             = var.vpn_static_routes_only
  transit_gateway_route_table_id = module.transit_gateway.vpn_route_table_id

  tags = {
    Component = "vpn"
  }
}

# VPC Attachment Route Table Associations
# These associate workload VPC attachments with the VPC route table
# so traffic from VPCs entering the TGW has a route table for egress routing

resource "aws_ec2_transit_gateway_route_table_association" "uat" {
  count = var.enable_workload_routes && local.uat_tgw_attachment_id != null ? 1 : 0

  transit_gateway_attachment_id  = local.uat_tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpc_route_table_id
}

resource "aws_ec2_transit_gateway_route_table_association" "prod" {
  count = var.enable_workload_routes && local.prod_tgw_attachment_id != null ? 1 : 0

  transit_gateway_attachment_id  = local.prod_tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpc_route_table_id
}

# Transit Gateway Routes

# Route to on-premises via VPN
resource "aws_ec2_transit_gateway_route" "onprem" {
  for_each = var.enable_vpn && var.customer_gateway_ip != "0.0.0.0" ? toset(var.onprem_cidrs) : toset([])

  destination_cidr_block         = each.value
  transit_gateway_attachment_id  = module.vpn[0].vpn_connection_transit_gateway_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpc_route_table_id
}

# VPN to UAT
resource "aws_ec2_transit_gateway_route" "vpn_to_uat" {
  count = var.enable_workload_routes && local.uat_tgw_attachment_id != null ? 1 : 0

  destination_cidr_block         = coalesce(local.uat_vpc_cidr, var.uat_vpc_cidr)
  transit_gateway_attachment_id  = local.uat_tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpn_route_table_id
}

# VPN to Prod
resource "aws_ec2_transit_gateway_route" "vpn_to_prod" {
  count = var.enable_workload_routes && local.prod_tgw_attachment_id != null ? 1 : 0

  destination_cidr_block         = coalesce(local.prod_vpc_cidr, var.prod_vpc_cidr)
  transit_gateway_attachment_id  = local.prod_tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpn_route_table_id
}

# UAT to Prod
resource "aws_ec2_transit_gateway_route" "uat_to_prod" {
  count = var.enable_workload_routes && local.prod_tgw_attachment_id != null ? 1 : 0

  destination_cidr_block         = coalesce(local.prod_vpc_cidr, var.prod_vpc_cidr)
  transit_gateway_attachment_id  = local.prod_tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpc_route_table_id
}

# Prod to UAT
resource "aws_ec2_transit_gateway_route" "prod_to_uat" {
  count = var.enable_workload_routes && local.uat_tgw_attachment_id != null ? 1 : 0

  destination_cidr_block         = coalesce(local.uat_vpc_cidr, var.uat_vpc_cidr)
  transit_gateway_attachment_id  = local.uat_tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpc_route_table_id
}

# Direct Connect

module "direct_connect" {
  source = "../../modules/direct-connect"
  count  = var.enable_direct_connect ? 1 : 0

  name             = local.name_prefix
  dx_gateway_asn   = var.dx_gateway_asn
  dx_connection_id = var.dx_connection_id

  # Transit VIF configuration
  create_transit_vif = var.dx_create_transit_vif
  vlan_id            = var.dx_vlan_id
  customer_bgp_asn   = var.dx_customer_bgp_asn
  mtu                = var.dx_mtu

  # Accept hosted VIF (alternative to creating one)
  accept_hosted_vif = var.dx_accept_hosted_vif
  hosted_vif_id     = var.dx_hosted_vif_id

  # TGW association
  transit_gateway_id = module.transit_gateway.transit_gateway_id
  allowed_prefixes   = [var.uat_vpc_cidr, var.prod_vpc_cidr]

  # Associate DX attachment with the VPN/DX route table (on-prem ingress routing)
  transit_gateway_route_table_id = module.transit_gateway.vpn_route_table_id

  # Propagate on-prem BGP routes to the VPC route table (VPC egress to on-prem)
  propagate_to_route_table_ids = [module.transit_gateway.vpc_route_table_id]

  tags = {
    Component = "direct-connect"
  }
}

# Route to on-premises via Direct Connect (static fallback in VPC route table)
# BGP propagation handles this dynamically, but static route serves as backup
resource "aws_ec2_transit_gateway_route" "onprem_dx" {
  for_each = var.enable_direct_connect && var.dx_enable_static_routes ? toset(var.onprem_cidrs) : toset([])

  destination_cidr_block         = each.value
  transit_gateway_attachment_id  = module.direct_connect[0].tgw_attachment_id
  transit_gateway_route_table_id = module.transit_gateway.vpc_route_table_id
}
