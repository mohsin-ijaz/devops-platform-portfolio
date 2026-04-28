# GitLab OIDC Provider Bootstrap
# This creates the OIDC identity provider and IAM role for GitLab CI

provider "aws" {
  region = var.aws_region
}

# Get GitLab OIDC thumbprint
data "tls_certificate" "gitlab" {
  url = var.gitlab_url
}

# Create OIDC Identity Provider for GitLab
resource "aws_iam_openid_connect_provider" "gitlab" {
  url             = var.gitlab_url
  client_id_list  = [var.gitlab_url]
  thumbprint_list = [data.tls_certificate.gitlab.certificates[0].sha1_fingerprint]

  tags = merge(var.tags, {
    Name = "gitlab-oidc-provider"
  })
}

# Build the list of allowed subjects (branches)
locals {
  # Format: project_path:<group/project>:ref_type:branch:ref:<branch>
  # If allowed_subjects is provided, use it directly; otherwise build from project_path and branches
  allowed_subjects = length(var.allowed_subjects) > 0 ? var.allowed_subjects : [
    for branch in var.allowed_branches :
    "project_path:${var.gitlab_project_path}:ref_type:branch:ref:${branch}"
  ]
}

# IAM Role for GitLab CI
resource "aws_iam_role" "gitlab_ci" {
  name                 = var.role_name
  max_session_duration = var.role_max_session_duration

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.gitlab.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(var.gitlab_url, "https://", "")}:aud" = var.gitlab_url
          }
          StringLike = {
            "${replace(var.gitlab_url, "https://", "")}:sub" = local.allowed_subjects
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = var.role_name
  })
}

# Attach AdministratorAccess policy if enabled
resource "aws_iam_role_policy_attachment" "admin" {
  count      = var.attach_admin_policy ? 1 : 0
  role       = aws_iam_role.gitlab_ci.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
