# ArgoCD Image Updater
# Automatically updates container images in ArgoCD Applications
# Mode 1: Imperative updates (no git commits)

# Data sources for IRSA
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_eks_cluster" "cluster_for_image_updater" {
  count = var.enable_argocd_image_updater ? 1 : 0
  name  = var.cluster_name
}

locals {
  image_updater_oidc_provider_url = var.enable_argocd_image_updater ? replace(data.aws_eks_cluster.cluster_for_image_updater[0].identity[0].oidc[0].issuer, "https://", "") : ""
  partition                       = data.aws_partition.current.partition
  account_id                      = data.aws_caller_identity.current.account_id
}

# IRSA Role for ArgoCD Image Updater
resource "aws_iam_role" "image_updater" {
  count = var.enable_argocd_image_updater ? 1 : 0

  name = "${var.cluster_name}-argocd-image-updater-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:${local.partition}:iam::${local.account_id}:oidc-provider/${local.image_updater_oidc_provider_url}"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${local.image_updater_oidc_provider_url}:aud" = "sts.amazonaws.com"
            "${local.image_updater_oidc_provider_url}:sub" = "system:serviceaccount:argocd:argocd-image-updater"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.cluster_name}-argocd-image-updater-role"
  }
}

# ECR read policy for Image Updater - allows reading from multiple accounts
resource "aws_iam_role_policy" "image_updater_ecr" {
  count = var.enable_argocd_image_updater ? 1 : 0

  name = "ecr-read-access"
  role = aws_iam_role.image_updater[0].id

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
          "ecr:DescribeRepositories",
          "ecr:DescribeImages",
          "ecr:ListImages",
          "ecr:GetRepositoryPolicy"
        ]
        Resource = [
          for account_id in var.image_updater_ecr_account_ids :
          "arn:${local.partition}:ecr:${var.aws_region}:${account_id}:repository/*"
        ]
      }
    ]
  })
}

# ConfigMap with ECR login script
resource "kubernetes_config_map" "ecr_login_script" {
  count = var.enable_argocd_image_updater && var.enable_argocd ? 1 : 0

  metadata {
    name      = "argocd-image-updater-ecr-login"
    namespace = "argocd"
  }

  data = {
    "ecr-login.sh" = <<-EOF
#!/bin/sh
echo "AWS:$(aws ecr get-login-password --region $AWS_REGION)"
EOF
  }

  depends_on = [kubernetes_namespace.argocd]
}

# Helm release for ArgoCD Image Updater
resource "helm_release" "argocd_image_updater" {
  count = var.enable_argocd_image_updater && var.enable_argocd ? 1 : 0

  name             = "argocd-image-updater"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-image-updater"
  version          = var.argocd_image_updater_version
  namespace        = "argocd"
  create_namespace = false

  values = [
    var.argocd_image_updater_values,
    # Override with IRSA role ARN
    yamlencode({
      serviceAccount = {
        annotations = {
          "eks.amazonaws.com/role-arn" = aws_iam_role.image_updater[0].arn
        }
      }
      extraEnv = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "AWS_STS_REGIONAL_ENDPOINTS"
          value = "regional"
        }
      ]
      config = {
        registries = [
          for idx, account_id in var.image_updater_ecr_account_ids : {
            name        = "ecr-${account_id}"
            prefix      = "${account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
            api_url     = "https://${account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
            default     = idx == 0
            credentials = "ext:/scripts/ecr-login.sh"
          }
        ]
      }
    })
  ]

  depends_on = [
    helm_release.argocd,
    kubernetes_config_map.ecr_login_script
  ]
}
