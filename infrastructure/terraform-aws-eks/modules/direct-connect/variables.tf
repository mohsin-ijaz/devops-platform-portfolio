# Direct Connect Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

# DX Gateway

variable "dx_gateway_asn" {
  description = "Amazon side ASN for the DX Gateway (must differ from TGW ASN and customer ASN)"
  type        = number
}

# DX Connection

variable "dx_connection_id" {
  description = "Direct Connect connection ID (e.g., dxcon-xxxxxxxx)"
  type        = string
  default     = ""
}

# Transit VIF - create new

variable "create_transit_vif" {
  description = "Create a Transit VIF on the DX connection (set false if using hosted VIF)"
  type        = bool
  default     = true
}

variable "vlan_id" {
  description = "VLAN ID for the Transit VIF (assigned by telco for hosted connections)"
  type        = number
  default     = 0
}

variable "customer_bgp_asn" {
  description = "Customer-side BGP ASN (on-prem router)"
  type        = number
}

variable "address_family" {
  description = "BGP address family (ipv4 or ipv6)"
  type        = string
  default     = "ipv4"
}

variable "amazon_address" {
  description = "AWS-side BGP peer IP in CIDR notation (auto-assigned if null)"
  type        = string
  default     = null
}

variable "customer_address" {
  description = "Customer-side BGP peer IP in CIDR notation (auto-assigned if null)"
  type        = string
  default     = null
}

variable "bgp_auth_key" {
  description = "BGP MD5 authentication key (auto-generated if null)"
  type        = string
  default     = null
  sensitive   = true
}

variable "mtu" {
  description = "MTU size (1500 for hosted connections, 8500 for jumbo frames on dedicated)"
  type        = number
  default     = 1500
}

# Transit VIF - accept hosted

variable "accept_hosted_vif" {
  description = "Accept a hosted Transit VIF created by the telco/partner"
  type        = bool
  default     = false
}

variable "hosted_vif_id" {
  description = "Hosted Transit VIF ID to accept (required when accept_hosted_vif = true)"
  type        = string
  default     = ""
}

# Transit Gateway Association

variable "transit_gateway_id" {
  description = "Transit Gateway ID to associate the DX Gateway with"
  type        = string
}

variable "allowed_prefixes" {
  description = "VPC CIDRs to advertise to on-prem via BGP (e.g., UAT and Prod VPC CIDRs)"
  type        = list(string)
}

# TGW Route Table

variable "transit_gateway_route_table_id" {
  description = "TGW route table to associate the DX attachment with (for on-prem ingress routing)"
  type        = string
}

variable "propagate_to_route_table_ids" {
  description = "TGW route table IDs to propagate DX routes to (for VPC egress to on-prem)"
  type        = list(string)
  default     = []
}

# Tags

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
