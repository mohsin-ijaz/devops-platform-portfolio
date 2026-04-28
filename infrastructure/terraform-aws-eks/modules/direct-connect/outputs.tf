# Direct Connect Module - Outputs

output "dx_gateway_id" {
  description = "Direct Connect Gateway ID"
  value       = aws_dx_gateway.this.id
}

output "dx_gateway_arn" {
  description = "Direct Connect Gateway ARN"
  value       = aws_dx_gateway.this.id
}

output "transit_vif_id" {
  description = "Transit Virtual Interface ID"
  value       = try(aws_dx_transit_virtual_interface.this[0].id, try(aws_dx_hosted_transit_virtual_interface_accepter.this[0].virtual_interface_id, null))
}

output "transit_vif_arn" {
  description = "Transit Virtual Interface ARN"
  value       = try(aws_dx_transit_virtual_interface.this[0].arn, null)
}

output "dx_gateway_association_id" {
  description = "DX Gateway to TGW association ID"
  value       = aws_dx_gateway_association.this.id
}

output "tgw_attachment_id" {
  description = "Transit Gateway attachment ID for the DX Gateway"
  value       = data.aws_ec2_transit_gateway_attachment.dx.id
}

output "bgp_asn" {
  description = "BGP ASN configured on the Transit VIF"
  value       = try(aws_dx_transit_virtual_interface.this[0].bgp_asn, null)
}

output "amazon_address" {
  description = "AWS-side BGP peer IP"
  value       = try(aws_dx_transit_virtual_interface.this[0].amazon_address, null)
}

output "customer_address" {
  description = "Customer-side BGP peer IP"
  value       = try(aws_dx_transit_virtual_interface.this[0].customer_address, null)
}

output "bgp_auth_key" {
  description = "BGP MD5 authentication key"
  value       = try(aws_dx_transit_virtual_interface.this[0].bgp_auth_key, null)
  sensitive   = true
}
