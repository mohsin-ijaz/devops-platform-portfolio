# GitLab CI Role Module
# Creates an IAM role that can be assumed by GitLab CI pipelines via OIDC

data "aws_caller_identity" "current" {}

# Get existing OIDC provider
data "aws_iam_openid_connect_provider" "gitlab" {
  url = var.gitlab_url
}

# IAM Role for GitLab CI
resource "aws_iam_role" "gitlab_ci" {
  name                 = var.role_name
  max_session_duration = var.max_session_duration

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = data.aws_iam_openid_connect_provider.gitlab.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(var.gitlab_url, "https://", "")}:aud" = var.gitlab_url
          }
          StringLike = {
            "${replace(var.gitlab_url, "https://", "")}:sub" = var.allowed_subjects
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = var.role_name
  })
}

# ECR Push/Pull Policy
resource "aws_iam_role_policy" "ecr" {
  count = var.enable_ecr_access ? 1 : 0
  name  = "ecr-access"
  role  = aws_iam_role.gitlab_ci.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages"
        ]
        Resource = var.ecr_repository_arns
      }
    ]
  })
}

# EKS Access Policy
resource "aws_iam_role_policy" "eks" {
  count = var.enable_eks_access ? 1 : 0
  name  = "eks-access"
  role  = aws_iam_role.gitlab_ci.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters"
        ]
        Resource = "*"
      }
    ]
  })
}
