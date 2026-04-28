# TGW Attachment Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID to attach"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for the attachment (one per AZ)"
  type        = list(string)
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID"
  type        = string
}

variable "transit_gateway_route_table_id" {
  description = "Transit Gateway route table ID to associate with"
  type        = string
}

variable "associate_with_route_table" {
  description = "Whether to associate attachment with route table"
  type        = bool
}

variable "dns_support" {
  description = "Enable DNS support for the attachment"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}
