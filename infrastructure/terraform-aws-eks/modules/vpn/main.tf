# VPN Module

# Customer Gateway

resource "aws_customer_gateway" "this" {
  bgp_asn    = var.customer_gateway_bgp_asn
  ip_address = var.customer_gateway_ip
  type       = var.vpn_type

  tags = merge(var.tags, {
    Name = "${var.name}-cgw"
  })
}

# VPN Connection

resource "aws_vpn_connection" "this" {
  customer_gateway_id = aws_customer_gateway.this.id
  transit_gateway_id  = var.transit_gateway_id
  type                = var.vpn_type
  static_routes_only  = var.static_routes_only

  tags = merge(var.tags, {
    Name = "${var.name}-vpn"
  })
}

# TGW Route Table Association

resource "aws_ec2_transit_gateway_route_table_association" "vpn" {
  transit_gateway_attachment_id  = aws_vpn_connection.this.transit_gateway_attachment_id
  transit_gateway_route_table_id = var.transit_gateway_route_table_id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "vpn" {
  transit_gateway_attachment_id  = aws_vpn_connection.this.transit_gateway_attachment_id
  transit_gateway_route_table_id = var.transit_gateway_route_table_id
}
