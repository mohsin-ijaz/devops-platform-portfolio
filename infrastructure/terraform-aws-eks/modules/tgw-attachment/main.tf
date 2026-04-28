# TGW Attachment Module

resource "aws_ec2_transit_gateway_vpc_attachment" "this" {
  transit_gateway_id = var.transit_gateway_id
  vpc_id             = var.vpc_id
  subnet_ids         = var.subnet_ids

  dns_support = var.dns_support

  tags = merge(var.tags, {
    Name = "${var.name}-tgw-attachment"
  })
}

# Route table association
resource "aws_ec2_transit_gateway_route_table_association" "this" {
  count = var.associate_with_route_table ? 1 : 0

  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.this.id
  transit_gateway_route_table_id = var.transit_gateway_route_table_id
}

# Route propagation
resource "aws_ec2_transit_gateway_route_table_propagation" "this" {
  count = var.associate_with_route_table ? 1 : 0

  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.this.id
  transit_gateway_route_table_id = var.transit_gateway_route_table_id
}
