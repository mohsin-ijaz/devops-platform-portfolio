# Transit Gateway Module

# Transit Gateway

resource "aws_ec2_transit_gateway" "this" {
  description = "Transit Gateway for ${var.name}"

  amazon_side_asn                 = var.amazon_side_asn
  auto_accept_shared_attachments  = var.auto_accept_shared_attachments
  default_route_table_association = var.default_route_table_association
  default_route_table_propagation = var.default_route_table_propagation
  dns_support                     = var.dns_support
  vpn_ecmp_support                = var.vpn_ecmp_support

  tags = merge(var.tags, {
    Name = "${var.name}-tgw"
  })
}

# Transit Gateway Route Tables

# Route table for VPC attachments
resource "aws_ec2_transit_gateway_route_table" "vpc" {
  transit_gateway_id = aws_ec2_transit_gateway.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-tgw-rt-vpc"
    Type = "vpc"
  })
}

# Route table for VPN attachment
resource "aws_ec2_transit_gateway_route_table" "vpn" {
  transit_gateway_id = aws_ec2_transit_gateway.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-tgw-rt-vpn"
    Type = "vpn"
  })
}

# RAM Resource Share

resource "aws_ram_resource_share" "tgw" {
  count = length(var.share_with_account_ids) > 0 ? 1 : 0

  name                      = "${var.name}-tgw-share"
  allow_external_principals = true  # Required until RAM org sharing propagates

  tags = merge(var.tags, {
    Name = "${var.name}-tgw-share"
  })
}

resource "aws_ram_resource_association" "tgw" {
  count = length(var.share_with_account_ids) > 0 ? 1 : 0

  resource_arn       = aws_ec2_transit_gateway.this.arn
  resource_share_arn = aws_ram_resource_share.tgw[0].arn
}

resource "aws_ram_principal_association" "tgw" {
  count = length(var.share_with_account_ids)

  principal          = var.share_with_account_ids[count.index]
  resource_share_arn = aws_ram_resource_share.tgw[0].arn
}
