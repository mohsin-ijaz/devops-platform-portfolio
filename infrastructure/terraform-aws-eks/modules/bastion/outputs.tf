# Bastion Module - Outputs

output "instance_id" {
  description = "Bastion EC2 instance ID"
  value       = aws_instance.bastion.id
}

output "private_ip" {
  description = "Bastion private IP address"
  value       = aws_instance.bastion.private_ip
}

output "iam_role_arn" {
  description = "Bastion IAM role ARN"
  value       = aws_iam_role.bastion.arn
}

output "iam_role_name" {
  description = "Bastion IAM role name"
  value       = aws_iam_role.bastion.name
}

output "ssm_connect_command" {
  description = "AWS CLI command to connect via SSM"
  value       = "aws ssm start-session --target ${aws_instance.bastion.id}"
}
