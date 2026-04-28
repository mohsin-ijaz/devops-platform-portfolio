# VPC Endpoints Module

locals {
  # Interface endpoints configuration
  interface_endpoints = {
    ecr_api = {
      service_name = "com.amazonaws.${var.aws_region}.ecr.api"
      enabled      = lookup(var.enable_endpoints, "ecr_api", true)
    }
    ecr_dkr = {
      service_name = "com.amazonaws.${var.aws_region}.ecr.dkr"
      enabled      = lookup(var.enable_endpoints, "ecr_dkr", true)
    }
    sts = {
      service_name = "com.amazonaws.${var.aws_region}.sts"
      enabled      = lookup(var.enable_endpoints, "sts", true)
    }
    logs = {
      service_name = "com.amazonaws.${var.aws_region}.logs"
      enabled      = lookup(var.enable_endpoints, "logs", true)
    }
    ssm = {
      service_name = "com.amazonaws.${var.aws_region}.ssm"
      enabled      = lookup(var.enable_endpoints, "ssm", true)
    }
    ssmmessages = {
      service_name = "com.amazonaws.${var.aws_region}.ssmmessages"
      enabled      = lookup(var.enable_endpoints, "ssmmessages", true)
    }
    ec2messages = {
      service_name = "com.amazonaws.${var.aws_region}.ec2messages"
      enabled      = lookup(var.enable_endpoints, "ec2messages", true)
    }
    ec2 = {
      service_name = "com.amazonaws.${var.aws_region}.ec2"
      enabled      = lookup(var.enable_endpoints, "ec2", true)
    }
    eks = {
      service_name = "com.amazonaws.${var.aws_region}.eks"
      enabled      = lookup(var.enable_endpoints, "eks", true)
    }
    secretsmanager = {
      service_name = "com.amazonaws.${var.aws_region}.secretsmanager"
      enabled      = lookup(var.enable_endpoints, "secretsmanager", true)
    }
    autoscaling = {
      service_name = "com.amazonaws.${var.aws_region}.autoscaling"
      enabled      = lookup(var.enable_endpoints, "autoscaling", true)
    }
    elasticloadbalancing = {
      service_name = "com.amazonaws.${var.aws_region}.elasticloadbalancing"
      enabled      = lookup(var.enable_endpoints, "elasticloadbalancing", true)
    }
  }

  # Enabled endpoints
  enabled_interface_endpoints = {
    for k, v in local.interface_endpoints : k => v if v.enabled
  }
}

# Security Group for Interface Endpoints

resource "aws_security_group" "endpoints" {
  name        = "${var.name}-vpc-endpoints-sg"
  description = "Security group for VPC endpoints"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name}-vpc-endpoints-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# S3 Gateway Endpoint

resource "aws_vpc_endpoint" "s3" {
  count = lookup(var.enable_endpoints, "s3", true) ? 1 : 0

  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids

  tags = merge(var.tags, {
    Name = "${var.name}-s3-endpoint"
  })
}

# Interface Endpoints

resource "aws_vpc_endpoint" "interface" {
  for_each = local.enabled_interface_endpoints

  vpc_id              = var.vpc_id
  service_name        = each.value.service_name
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.name}-${replace(each.key, "_", "-")}-endpoint"
  })
}
