# Transit Gateway Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "amazon_side_asn" {
  description = "Amazon side ASN for the Transit Gateway"
  type        = number
}

variable "auto_accept_shared_attachments" {
  description = "Auto accept shared attachments"
  type        = string
}

variable "default_route_table_association" {
  description = "Default route table association"
  type        = string
}

variable "default_route_table_propagation" {
  description = "Default route table propagation"
  type        = string
}

variable "dns_support" {
  description = "DNS support"
  type        = string
}

variable "vpn_ecmp_support" {
  description = "VPN ECMP support"
  type        = string
}

variable "share_with_account_ids" {
  description = "AWS account IDs to share the Transit Gateway with via RAM"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}
