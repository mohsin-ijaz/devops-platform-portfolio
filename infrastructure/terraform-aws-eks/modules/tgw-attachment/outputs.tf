# TGW Attachment Module - Outputs

output "attachment_id" {
  description = "Transit Gateway VPC attachment ID"
  value       = aws_ec2_transit_gateway_vpc_attachment.this.id
}

output "vpc_id" {
  description = "Attached VPC ID"
  value       = aws_ec2_transit_gateway_vpc_attachment.this.vpc_id
}
