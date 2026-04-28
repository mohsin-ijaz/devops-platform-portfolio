# Network Account - Outputs

output "transit_gateway_id" {
  description = "Transit Gateway ID"
  value       = module.transit_gateway.transit_gateway_id
}

output "transit_gateway_arn" {
  description = "Transit Gateway ARN"
  value       = module.transit_gateway.transit_gateway_arn
}

output "vpc_route_table_id" {
  description = "Transit Gateway VPC route table ID"
  value       = module.transit_gateway.vpc_route_table_id
}

output "vpn_route_table_id" {
  description = "Transit Gateway VPN route table ID"
  value       = module.transit_gateway.vpn_route_table_id
}

output "ram_resource_share_arn" {
  description = "RAM resource share ARN"
  value       = module.transit_gateway.ram_resource_share_arn
}

output "vpn_connection_id" {
  description = "VPN connection ID"
  value       = try(module.vpn[0].vpn_connection_id, null)
}

output "vpn_tunnel1_address" {
  description = "VPN tunnel 1 public IP"
  value       = try(module.vpn[0].tunnel1_address, null)
}

output "vpn_tunnel2_address" {
  description = "VPN tunnel 2 public IP"
  value       = try(module.vpn[0].tunnel2_address, null)
}

# Remote State Information
output "uat_vpc_cidr_from_state" {
  description = "UAT VPC CIDR (from remote state)"
  value       = local.uat_vpc_cidr
}

output "prod_vpc_cidr_from_state" {
  description = "Production VPC CIDR (from remote state)"
  value       = local.prod_vpc_cidr
}

output "uat_tgw_attachment_id" {
  description = "UAT TGW attachment ID (from remote state)"
  value       = local.uat_tgw_attachment_id
}

output "prod_tgw_attachment_id" {
  description = "Production TGW attachment ID (from remote state)"
  value       = local.prod_tgw_attachment_id
}

# Direct Connect
output "dx_gateway_id" {
  description = "Direct Connect Gateway ID"
  value       = try(module.direct_connect[0].dx_gateway_id, null)
}

output "dx_tgw_attachment_id" {
  description = "DX Gateway TGW attachment ID"
  value       = try(module.direct_connect[0].tgw_attachment_id, null)
}

output "dx_transit_vif_id" {
  description = "Transit Virtual Interface ID"
  value       = try(module.direct_connect[0].transit_vif_id, null)
}

output "dx_bgp_peer_ips" {
  description = "BGP peer IPs (amazon and customer side)"
  value = {
    amazon_address   = try(module.direct_connect[0].amazon_address, null)
    customer_address = try(module.direct_connect[0].customer_address, null)
  }
}

# Shared configuration for workload accounts
output "onprem_cidrs" {
  description = "On-premises CIDR blocks"
  value       = var.onprem_cidrs
}
