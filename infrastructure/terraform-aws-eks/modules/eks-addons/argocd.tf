# ArgoCD

# ACM Certificate for ArgoCD domain
resource "aws_acm_certificate" "argocd" {
  count = var.enable_argocd && var.argocd_hostname != "" ? 1 : 0

  domain_name       = var.argocd_hostname
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "argocd-${var.argocd_hostname}"
  }
}

# Wait for certificate validation (user must add DNS record in Cloudflare)
resource "aws_acm_certificate_validation" "argocd" {
  count = var.enable_argocd && var.argocd_hostname != "" ? 1 : 0

  certificate_arn = aws_acm_certificate.argocd[0].arn

  timeouts {
    create = "30m"
  }
}

# Create namespace first if SSO secret is needed
resource "kubernetes_namespace" "argocd" {
  count = var.enable_argocd ? 1 : 0

  metadata {
    name = "argocd"
  }
}

# Generate server secret key for ArgoCD
resource "random_password" "argocd_server_secret" {
  count   = var.enable_argocd && var.argocd_google_client_id != "" ? 1 : 0
  length  = 32
  special = false
}

# Create Google OAuth credentials secret before ArgoCD deployment
resource "kubernetes_secret" "argocd_oauth" {
  count = var.enable_argocd && var.argocd_google_client_id != "" ? 1 : 0

  metadata {
    name      = "argocd-secret"
    namespace = "argocd"
    labels = {
      "app.kubernetes.io/name"    = "argocd-secret"
      "app.kubernetes.io/part-of" = "argocd"
    }
  }

  data = {
    "dex.google.clientID"     = var.argocd_google_client_id
    "dex.google.clientSecret" = var.argocd_google_client_secret
    "server.secretkey"        = random_password.argocd_server_secret[0].result
  }

  depends_on = [kubernetes_namespace.argocd]
}

locals {
  # Base ArgoCD values
  argocd_base_values = [var.argocd_values]

  # Add certificate ARN if hostname is provided
  argocd_cert_values = var.argocd_hostname != "" ? [
    yamlencode({
      server = {
        ingress = {
          annotations = {
            "alb.ingress.kubernetes.io/certificate-arn" = aws_acm_certificate.argocd[0].arn
          }
        }
      }
    })
  ] : []

  # Add IRSA annotation if controller role is provided
  argocd_irsa_values = var.argocd_controller_role_arn != "" ? [
    yamlencode({
      controller = {
        serviceAccount = {
          annotations = {
            "eks.amazonaws.com/role-arn" = var.argocd_controller_role_arn
          }
        }
      }
      server = {
        serviceAccount = {
          annotations = {
            "eks.amazonaws.com/role-arn" = var.argocd_controller_role_arn
          }
        }
      }
      repoServer = {
        serviceAccount = {
          annotations = {
            "eks.amazonaws.com/role-arn" = var.argocd_controller_role_arn
          }
        }
      }
    })
  ] : []

  # Add Lua resource actions for rollback controller (when enabled)
  argocd_rollback_values = var.enable_rollback_controller ? [
    yamlencode({
      configs = {
        cm = {
          "resource.customizations.actions.argoproj.io_Rollout"      = file("${path.module}/files/rollback-lua-action.yaml")
          "resource.customizations.actions.argoproj.io_Application" = file("${path.module}/files/resume-updates-lua-action.yaml")
        }
      }
    })
  ] : []
}

resource "helm_release" "argocd" {
  count = var.enable_argocd ? 1 : 0

  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_version
  namespace        = "argocd"
  create_namespace = false # We create it above

  values = concat(local.argocd_base_values, local.argocd_cert_values, local.argocd_irsa_values, local.argocd_rollback_values)

  depends_on = [
    helm_release.aws_lb_controller,
    kubernetes_namespace.argocd,
    kubernetes_secret.argocd_oauth,
    aws_acm_certificate_validation.argocd
  ]
}

# Register UAT cluster with ArgoCD (only when ArgoCD is enabled and UAT cluster info is provided)
resource "kubernetes_secret" "argocd_cluster_uat" {
  count = var.enable_argocd && var.argocd_uat_cluster_endpoint != "" ? 1 : 0

  metadata {
    name      = "cluster-uat"
    namespace = "argocd"
    labels = {
      "argocd.argoproj.io/secret-type" = "cluster"
    }
  }

  data = {
    name   = "uat"
    server = var.argocd_uat_cluster_endpoint
    config = jsonencode({
      awsAuthConfig = {
        clusterName = var.argocd_uat_cluster_name
        roleARN     = var.argocd_uat_role_arn
        externalId  = "argocd"
      }
      tlsClientConfig = {
        insecure = false
        caData   = var.argocd_uat_cluster_ca
      }
    })
  }

  depends_on = [helm_release.argocd]
}
