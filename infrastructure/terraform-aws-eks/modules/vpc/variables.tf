# VPC Module - Variables

variable "name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) >= 1 && length(var.availability_zones) <= 3
    error_message = "Must specify 1-3 availability zones."
  }
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets (one per AZ)"
  type        = list(string)

  validation {
    condition     = alltrue([for cidr in var.private_subnet_cidrs : can(cidrhost(cidr, 0))])
    error_message = "All private subnet CIDRs must be valid IPv4 CIDR blocks."
  }
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets (one per AZ)"
  type        = list(string)

  validation {
    condition     = alltrue([for cidr in var.database_subnet_cidrs : can(cidrhost(cidr, 0))])
    error_message = "All database subnet CIDRs must be valid IPv4 CIDR blocks."
  }
}

variable "nat_subnet_cidrs" {
  description = "CIDR blocks for NAT subnets (public subnets for NAT GW)"
  type        = list(string)

  validation {
    condition     = alltrue([for cidr in var.nat_subnet_cidrs : can(cidrhost(cidr, 0))])
    error_message = "All NAT subnet CIDRs must be valid IPv4 CIDR blocks."
  }
}

variable "single_nat_gateway" {
  description = "Use single NAT gateway for cost optimization"
  type        = bool
}

variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames in VPC"
  type        = bool
}

variable "enable_dns_support" {
  description = "Enable DNS support in VPC"
  type        = bool
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID for routing (optional)"
  type        = string
}

variable "transit_gateway_routes" {
  description = "CIDR blocks to route via Transit Gateway"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
}
