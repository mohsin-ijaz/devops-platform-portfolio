# VPC Endpoints Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block (for security group rules)"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for interface endpoints"
  type        = list(string)
}

variable "route_table_ids" {
  description = "Route table IDs for gateway endpoints"
  type        = list(string)
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "enable_endpoints" {
  description = "Map of endpoints to enable"
  type        = map(bool)
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}
