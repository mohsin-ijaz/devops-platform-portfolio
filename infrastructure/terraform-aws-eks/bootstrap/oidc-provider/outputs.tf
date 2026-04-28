output "oidc_provider_arn" {
  description = "ARN of the GitLab OIDC provider"
  value       = aws_iam_openid_connect_provider.gitlab.arn
}

output "gitlab_ci_role_arn" {
  description = "ARN of the GitLab CI IAM role"
  value       = aws_iam_role.gitlab_ci.arn
}

output "gitlab_ci_role_name" {
  description = "Name of the GitLab CI IAM role"
  value       = aws_iam_role.gitlab_ci.name
}
