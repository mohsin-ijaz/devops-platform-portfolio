# VPC Module - Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.this.cidr_block
}

output "vpc_arn" {
  description = "VPC ARN"
  value       = aws_vpc.this.arn
}

output "internet_gateway_id" {
  description = "Internet Gateway ID"
  value       = aws_internet_gateway.this.id
}

# NAT Subnets
output "nat_subnet_ids" {
  description = "NAT subnet IDs"
  value       = aws_subnet.nat[*].id
}

output "nat_subnet_cidrs" {
  description = "NAT subnet CIDR blocks"
  value       = aws_subnet.nat[*].cidr_block
}

# NAT Gateways
output "nat_gateway_ids" {
  description = "NAT Gateway IDs"
  value       = aws_nat_gateway.this[*].id
}

output "nat_gateway_public_ips" {
  description = "NAT Gateway public IPs"
  value       = aws_eip.nat[*].public_ip
}

# Private Subnets
output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "private_subnet_cidrs" {
  description = "Private subnet CIDR blocks"
  value       = aws_subnet.private[*].cidr_block
}

output "private_subnet_arns" {
  description = "Private subnet ARNs"
  value       = aws_subnet.private[*].arn
}

output "private_route_table_ids" {
  description = "Private route table IDs"
  value       = aws_route_table.private[*].id
}

# Database Subnets
output "database_subnet_ids" {
  description = "Database subnet IDs"
  value       = aws_subnet.database[*].id
}

output "database_subnet_cidrs" {
  description = "Database subnet CIDR blocks"
  value       = aws_subnet.database[*].cidr_block
}

output "database_subnet_group_name" {
  description = "Database subnet group name"
  value       = try(aws_db_subnet_group.this[0].name, null)
}

output "database_route_table_id" {
  description = "Database route table ID"
  value       = aws_route_table.database.id
}

# Availability Zones
output "availability_zones" {
  description = "Availability zones used"
  value       = var.availability_zones
}

# Subnet maps (for easy lookup)
output "private_subnet_by_az" {
  description = "Map of AZ to private subnet ID"
  value = {
    for idx, az in var.availability_zones : az => aws_subnet.private[idx].id
  }
}

output "database_subnet_by_az" {
  description = "Map of AZ to database subnet ID"
  value = {
    for idx, az in var.availability_zones : az => aws_subnet.database[idx].id
  }
}
