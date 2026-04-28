# Transit Gateway Module - Outputs

output "transit_gateway_id" {
  description = "Transit Gateway ID"
  value       = aws_ec2_transit_gateway.this.id
}

output "transit_gateway_arn" {
  description = "Transit Gateway ARN"
  value       = aws_ec2_transit_gateway.this.arn
}

output "transit_gateway_owner_id" {
  description = "Transit Gateway owner account ID"
  value       = aws_ec2_transit_gateway.this.owner_id
}

output "vpc_route_table_id" {
  description = "Transit Gateway VPC route table ID"
  value       = aws_ec2_transit_gateway_route_table.vpc.id
}

output "vpn_route_table_id" {
  description = "Transit Gateway VPN route table ID"
  value       = aws_ec2_transit_gateway_route_table.vpn.id
}

output "ram_resource_share_arn" {
  description = "RAM resource share ARN"
  value       = try(aws_ram_resource_share.tgw[0].arn, null)
}
