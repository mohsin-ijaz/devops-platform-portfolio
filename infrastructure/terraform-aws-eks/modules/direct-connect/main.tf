# Direct Connect Module
# Creates DX Gateway, Transit VIF, and TGW Association with route propagation

# DX Gateway - must use a different ASN from the TGW (64512) and customer router (65000)

resource "aws_dx_gateway" "this" {
  name            = "${var.name}-dxgw"
  amazon_side_asn = var.dx_gateway_asn
}

# Transit Virtual Interface (required for TGW integration)
# Use this when the customer creates the VIF on a dedicated or hosted connection

resource "aws_dx_transit_virtual_interface" "this" {
  count = var.create_transit_vif ? 1 : 0

  connection_id = var.dx_connection_id
  name          = "${var.name}-dx-transit-vif"
  vlan          = var.vlan_id
  bgp_asn       = var.customer_bgp_asn
  dx_gateway_id = aws_dx_gateway.this.id
  mtu           = var.mtu

  address_family   = var.address_family
  amazon_address   = var.amazon_address
  customer_address = var.customer_address

  tags = merge(var.tags, {
    Name = "${var.name}-dx-transit-vif"
  })
}

# Accept hosted Transit VIF (when the partner/telco creates the VIF)
# Use this instead of create_transit_vif when the telco provisions the VIF directly

resource "aws_dx_hosted_transit_virtual_interface_accepter" "this" {
  count = var.accept_hosted_vif ? 1 : 0

  virtual_interface_id = var.hosted_vif_id
  dx_gateway_id        = aws_dx_gateway.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-dx-transit-vif-hosted"
  })
}

# Associate DX Gateway with Transit Gateway
# allowed_prefixes = VPC CIDRs that AWS advertises to the on-prem router via BGP

resource "aws_dx_gateway_association" "this" {
  dx_gateway_id         = aws_dx_gateway.this.id
  associated_gateway_id = var.transit_gateway_id

  allowed_prefixes = var.allowed_prefixes

  timeouts {
    create = "30m"
    update = "30m"
    delete = "30m"
  }

  depends_on = [
    aws_dx_transit_virtual_interface.this,
    aws_dx_hosted_transit_virtual_interface_accepter.this,
  ]
}

# Look up the TGW attachment automatically created by the DX GW association

data "aws_ec2_transit_gateway_attachment" "dx" {
  filter {
    name   = "resource-type"
    values = ["direct-connect-gateway"]
  }

  filter {
    name   = "resource-id"
    values = [aws_dx_gateway.this.id]
  }

  filter {
    name   = "transit-gateway-id"
    values = [var.transit_gateway_id]
  }

  depends_on = [aws_dx_gateway_association.this]
}

# Associate DX attachment with TGW route table
# This route table is used for traffic ENTERING the TGW from on-premises
# (i.e., on-prem traffic looks up this table to find VPC routes)

resource "aws_ec2_transit_gateway_route_table_association" "dx" {
  transit_gateway_attachment_id  = data.aws_ec2_transit_gateway_attachment.dx.id
  transit_gateway_route_table_id = var.transit_gateway_route_table_id
}

# Propagate DX BGP-learned routes to specified TGW route tables
# This adds on-prem routes (e.g., 192.168.0.0/16) to the VPC route table
# so VPC traffic destined for on-prem is routed through the DX attachment

resource "aws_ec2_transit_gateway_route_table_propagation" "dx" {
  for_each = toset(var.propagate_to_route_table_ids)

  transit_gateway_attachment_id  = data.aws_ec2_transit_gateway_attachment.dx.id
  transit_gateway_route_table_id = each.value
}
