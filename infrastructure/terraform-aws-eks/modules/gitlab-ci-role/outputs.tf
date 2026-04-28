# GitLab CI Role Module Outputs

output "role_arn" {
  description = "ARN of the GitLab CI role"
  value       = aws_iam_role.gitlab_ci.arn
}

output "role_name" {
  description = "Name of the GitLab CI role"
  value       = aws_iam_role.gitlab_ci.name
}
