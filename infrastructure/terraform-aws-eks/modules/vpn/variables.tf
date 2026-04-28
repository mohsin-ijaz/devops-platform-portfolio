# VPN Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID to attach VPN to"
  type        = string
}

variable "customer_gateway_ip" {
  description = "Customer gateway public IP address"
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

variable "static_routes_only" {
  description = "Use static routes only (no BGP)"
  type        = bool
}

variable "transit_gateway_route_table_id" {
  description = "Transit Gateway route table ID to associate VPN with"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}
