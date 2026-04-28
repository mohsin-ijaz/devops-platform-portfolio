# VPC Module - Main
# Creates VPC, Subnets, Route Tables, NAT Gateway, Internet Gateway

locals {
  az_count = length(var.availability_zones)

  # Determine number of NAT gateways
  nat_gateway_count = var.single_nat_gateway ? 1 : local.az_count

  # Create AZ suffix mapping (e.g., <AWS_REGION>a -> apse5a)
  az_suffix_map = {
    for az in var.availability_zones : az => replace(
      replace(az, "ap-southeast-", "apse"),
      "-", ""
    )
  }
}

# VPC

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = var.enable_dns_hostnames
  enable_dns_support   = var.enable_dns_support

  tags = merge(var.tags, {
    Name = "${var.name}-vpc"
  })
}

# Internet Gateway

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-igw"
  })
}

# NAT Subnets

resource "aws_subnet" "nat" {
  count = length(var.nat_subnet_cidrs)

  vpc_id            = aws_vpc.this.id
  cidr_block        = var.nat_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name                     = "${var.name}-nat-${local.az_suffix_map[var.availability_zones[count.index]]}"
    Type                     = "nat"
    "kubernetes.io/role/elb" = "1"
  })
}

# Elastic IPs for NAT Gateways

resource "aws_eip" "nat" {
  count  = local.nat_gateway_count
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "${var.name}-nat-eip-${local.az_suffix_map[var.availability_zones[count.index]]}"
  })

  depends_on = [aws_internet_gateway.this]
}

# NAT Gateways

resource "aws_nat_gateway" "this" {
  count = local.nat_gateway_count

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.nat[count.index].id

  tags = merge(var.tags, {
    Name = "${var.name}-nat-${local.az_suffix_map[var.availability_zones[count.index]]}"
  })

  depends_on = [aws_internet_gateway.this]
}

# NAT Subnet Route Table

resource "aws_route_table" "nat" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-nat-rt"
    Type = "nat"
  })
}

resource "aws_route" "nat_igw" {
  route_table_id         = aws_route_table.nat.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "nat" {
  count = length(var.nat_subnet_cidrs)

  subnet_id      = aws_subnet.nat[count.index].id
  route_table_id = aws_route_table.nat.id
}

# Private Subnets

resource "aws_subnet" "private" {
  count = length(var.private_subnet_cidrs)

  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name                              = "${var.name}-private-${local.az_suffix_map[var.availability_zones[count.index]]}"
    Type                              = "private"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

# Private Route Tables

resource "aws_route_table" "private" {
  count = local.az_count

  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-private-rt-${local.az_suffix_map[var.availability_zones[count.index]]}"
    Type = "private"
  })
}

resource "aws_route" "private_nat" {
  count = local.az_count

  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = var.single_nat_gateway ? aws_nat_gateway.this[0].id : aws_nat_gateway.this[count.index].id
}

# Transit Gateway routes
resource "aws_route" "private_tgw" {
  for_each = var.transit_gateway_id != null && var.transit_gateway_id != "" ? {
    for pair in setproduct(range(local.az_count), var.transit_gateway_routes) :
    "${pair[0]}:${pair[1]}" => {
      rt_index = pair[0]
      cidr     = pair[1]
    }
  } : {}

  route_table_id         = aws_route_table.private[each.value.rt_index].id
  destination_cidr_block = each.value.cidr
  transit_gateway_id     = var.transit_gateway_id
}

resource "aws_route_table_association" "private" {
  count = length(var.private_subnet_cidrs)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Database Subnets

resource "aws_subnet" "database" {
  count = length(var.database_subnet_cidrs)

  vpc_id            = aws_vpc.this.id
  cidr_block        = var.database_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "${var.name}-db-${local.az_suffix_map[var.availability_zones[count.index]]}"
    Type = "database"
  })
}

# Database Route Table

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-db-rt"
    Type = "database"
  })
}

# Transit Gateway routes for database subnets
resource "aws_route" "database_tgw" {
  for_each = var.transit_gateway_id != null && var.transit_gateway_id != "" ? toset(var.transit_gateway_routes) : toset([])

  route_table_id         = aws_route_table.database.id
  destination_cidr_block = each.value
  transit_gateway_id     = var.transit_gateway_id
}

resource "aws_route_table_association" "database" {
  count = length(var.database_subnet_cidrs)

  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.database.id
}

# Database Subnet Group

resource "aws_db_subnet_group" "this" {
  count = length(var.database_subnet_cidrs) > 0 ? 1 : 0

  name        = "${var.name}-db-<SUBNET_ID>"
  description = "Database subnet group for ${var.name}"
  subnet_ids  = aws_subnet.database[*].id

  tags = merge(var.tags, {
    Name = "${var.name}-db-<SUBNET_ID>"
  })
}
