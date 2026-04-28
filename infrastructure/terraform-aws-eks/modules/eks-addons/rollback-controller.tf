# Rollback Controller
# Watches Rollout resources for rollback annotations and performs git-based rollback.
# Uses per-app freeze (ignore-tags) instead of global Image Updater scaling.
# Deployed to the ArgoCD namespace on the PROD cluster.

# --- ServiceAccount ---

resource "kubernetes_service_account" "rollback_controller" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name      = "rollback-controller"
    namespace = "argocd"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  depends_on = [kubernetes_namespace.argocd]
}

# --- ClusterRole ---

resource "kubernetes_cluster_role" "rollback_controller" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name = "rollback-controller"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  # Rollout permissions - watch for rollback annotations and patch them
  rule {
    api_groups = ["argoproj.io"]
    resources  = ["rollouts"]
    verbs      = ["get", "list", "watch", "patch"]
  }

  # Application permissions - to discover repo info and annotate for per-app freeze
  rule {
    api_groups = ["argoproj.io"]
    resources  = ["applications"]
    verbs      = ["get", "list", "patch"]
  }

  # Secret permissions - to read git credentials and cluster tokens
  rule {
    api_groups = [""]
    resources  = ["secrets"]
    verbs      = ["get", "list"]
  }

  # Event permissions - for audit logging
  rule {
    api_groups = [""]
    resources  = ["events"]
    verbs      = ["create", "patch"]
  }

  # ConfigMap permissions - to read controller configuration
  rule {
    api_groups = [""]
    resources  = ["configmaps"]
    verbs      = ["get"]
  }
}

# --- ClusterRoleBinding ---

resource "kubernetes_cluster_role_binding" "rollback_controller" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name = "rollback-controller"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.rollback_controller[0].metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.rollback_controller[0].metadata[0].name
    namespace = "argocd"
  }
}

# --- ConfigMap: Controller Configuration ---

resource "kubernetes_config_map" "rollback_controller_config" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name      = "rollback-controller-config"
    namespace = "argocd"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  data = {
    "config.yaml" = <<-YAML
      # ArgoCD namespace where Application resources are deployed
      argocdNamespace: "argocd"

      # Git credentials secret (managed by Terraform)
      gitCredentialsSecret: "rollback-git-creds"
      gitCredentialsNamespace: "argocd"

      # Git commit settings
      gitCommitAuthor: "ArgoCD Rollback Controller"
      gitCommitEmail: "argocd-rollback<YOUR_DOMAIN>"

      # Controller polling interval (seconds)
      pollIntervalSeconds: 10

      # Log level (debug, info, warn, error)
      logLevel: "info"
    YAML
  }

  depends_on = [kubernetes_namespace.argocd]
}

# --- ConfigMap: Controller Script ---

resource "kubernetes_config_map" "rollback_controller_scripts" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name      = "rollback-controller-scripts"
    namespace = "argocd"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  data = {
    "controller.sh" = file("${path.module}/files/controller.sh")
  }

  depends_on = [kubernetes_namespace.argocd]
}

# --- Deployment ---

resource "kubernetes_deployment" "rollback_controller" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name      = "rollback-controller"
    namespace = "argocd"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "rollback-controller"
      }
    }

    template {
      metadata {
        labels = {
          app       = "rollback-controller"
          component = "automation"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.rollback_controller[0].metadata[0].name

        container {
          name  = "controller"
          image = "alpine:3.19"

          command = [
            "sh", "-c",
            <<-EOT
            # Install required tools
            apk add --no-cache curl git jq bash

            # Install kubectl
            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
            chmod +x kubectl
            mv kubectl /usr/local/bin/kubectl

            # Run controller
            exec /bin/bash /scripts/controller.sh
            EOT
          ]

          env {
            name  = "CONFIG_FILE"
            value = "/config/config.yaml"
          }

          volume_mount {
            name       = "config"
            mount_path = "/config"
            read_only  = true
          }

          volume_mount {
            name       = "scripts"
            mount_path = "/scripts"
            read_only  = true
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }
        }

        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.rollback_controller_config[0].metadata[0].name
          }
        }

        volume {
          name = "scripts"
          config_map {
            name         = kubernetes_config_map.rollback_controller_scripts[0].metadata[0].name
            default_mode = "0755"
          }
        }

        restart_policy = "Always"
      }
    }
  }

  depends_on = [kubernetes_namespace.argocd]
}

# --- Secret: Git Credentials ---

resource "kubernetes_secret" "rollback_git_creds" {
  count = var.enable_rollback_controller ? 1 : 0

  metadata {
    name      = "rollback-git-creds"
    namespace = "argocd"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  data = {
    token = var.rollback_controller_gitlab_token
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace.argocd]
}

# --- Secret: UAT Cluster Credentials ---
# Used by the controller to scan the UAT cluster for rollback annotations.
# Labeled with app=rollback-controller so the controller discovers it automatically.

resource "kubernetes_secret" "rollback_uat_cluster" {
  count = var.enable_rollback_controller && var.rollback_uat_cluster_server != "" ? 1 : 0

  metadata {
    name      = "rollback-cluster-uat"
    namespace = "argocd"
    labels = {
      app       = "rollback-controller"
      component = "automation"
    }
  }

  data = {
    name   = "uat"
    server = var.rollback_uat_cluster_server
    token  = var.rollback_uat_cluster_token
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace.argocd]
}
