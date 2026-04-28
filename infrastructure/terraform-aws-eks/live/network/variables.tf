# Network Account - Variables

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "company" {
  description = "Company name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "network_account_id" {
  description = "Network account ID"
  type        = string
}

variable "uat_account_id" {
  description = "UAT account ID"
  type        = string
}

variable "prod_account_id" {
  description = "Production account ID"
  type        = string
}

# Transit Gateway
variable "tgw_amazon_side_asn" {
  description = "Transit Gateway Amazon side ASN"
  type        = number
}

variable "tgw_auto_accept_shared_attachments" {
  description = "Auto accept shared attachments"
  type        = string
}

variable "tgw_default_route_table_association" {
  description = "Default route table association"
  type        = string
}

variable "tgw_default_route_table_propagation" {
  description = "Default route table propagation"
  type        = string
}

variable "tgw_dns_support" {
  description = "DNS support for Transit Gateway"
  type        = string
}

variable "tgw_vpn_ecmp_support" {
  description = "VPN ECMP support"
  type        = string
}

# VPN Configuration
variable "enable_vpn" {
  description = "Enable VPN connection"
  type        = bool
}

variable "customer_gateway_ip" {
  description = "Customer gateway public IP (FortiGate)"
  type        = string
}

variable "customer_gateway_bgp_asn" {
  description = "Customer gateway BGP ASN"
  type        = number
}

variable "vpn_type" {
  description = "VPN connection type"
  type        = string
}

variable "vpn_static_routes_only" {
  description = "Use static routes only (no BGP)"
  type        = bool
}

variable "onprem_cidrs" {
  description = "On-premises CIDR blocks"
  type        = list(string)
}

# Direct Connect Configuration
variable "enable_direct_connect" {
  description = "Enable Direct Connect"
  type        = bool
}

variable "dx_connection_id" {
  description = "Direct Connect connection ID (e.g., dxcon-xxxxxxxx)"
  type        = string
}

variable "dx_gateway_asn" {
  description = "DX Gateway Amazon side ASN (must differ from TGW ASN and customer ASN)"
  type        = number
}

variable "dx_create_transit_vif" {
  description = "Create a Transit VIF on the DX connection"
  type        = bool
}

variable "dx_vlan_id" {
  description = "VLAN ID for the Transit VIF (from telco)"
  type        = number
}

variable "dx_customer_bgp_asn" {
  description = "Customer BGP ASN for the DX Transit VIF"
  type        = number
}

variable "dx_mtu" {
  description = "MTU for the Transit VIF (1500 for hosted connections)"
  type        = number
}

variable "dx_accept_hosted_vif" {
  description = "Accept a hosted Transit VIF instead of creating one"
  type        = bool
}

variable "dx_hosted_vif_id" {
  description = "Hosted Transit VIF ID to accept"
  type        = string
}

variable "dx_enable_static_routes" {
  description = "Add static on-prem routes via DX in VPC route table (backup for BGP propagation)"
  type        = bool
}

# Remote State Configuration
variable "enable_workload_routes" {
  description = "Enable reading from workload account states to add TGW routes"
  type        = bool
}

# VPC CIDRs (used when remote state is not available)
variable "uat_vpc_cidr" {
  description = "UAT VPC CIDR (fallback if remote state unavailable)"
  type        = string
}

variable "prod_vpc_cidr" {
  description = "Production VPC CIDR (fallback if remote state unavailable)"
  type        = string
}
