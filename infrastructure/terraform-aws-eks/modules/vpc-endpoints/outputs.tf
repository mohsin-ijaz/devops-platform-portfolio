# VPC Endpoints Module - Outputs

output "security_group_id" {
  description = "Security group ID for VPC endpoints"
  value       = aws_security_group.endpoints.id
}

output "s3_endpoint_id" {
  description = "S3 Gateway endpoint ID"
  value       = try(aws_vpc_endpoint.s3[0].id, null)
}

output "interface_endpoint_ids" {
  description = "Map of interface endpoint IDs"
  value = {
    for k, v in aws_vpc_endpoint.interface : k => v.id
  }
}

output "interface_endpoint_dns_names" {
  description = "Map of interface endpoint DNS names"
  value = {
    for k, v in aws_vpc_endpoint.interface : k => v.dns_entry[0].dns_name
  }
}
