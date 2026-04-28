# Rollback Controller - Target Cluster SA
# Creates a ServiceAccount on the target cluster (e.g., UAT) that the
# rollback controller on the source cluster (e.g., PROD) uses to scan
# for rollback annotations on Rollouts.
#
# Enable this on clusters that are TARGETS of rollback scanning (not the
# cluster hosting the controller itself).

resource "kubernetes_namespace" "rollback_target" {
  count = var.enable_rollback_target_sa ? 1 : 0

  metadata {
    name = "rollback-system"
  }
}

resource "kubernetes_service_account" "rollback_target" {
  count = var.enable_rollback_target_sa ? 1 : 0

  metadata {
    name      = "rollback-controller-remote"
    namespace = kubernetes_namespace.rollback_target[0].metadata[0].name
    labels = {
      app       = "rollback-controller"
      component = "remote-access"
    }
  }
}

resource "kubernetes_cluster_role" "rollback_target" {
  count = var.enable_rollback_target_sa ? 1 : 0

  metadata {
    name = "rollback-controller-remote"
    labels = {
      app       = "rollback-controller"
      component = "remote-access"
    }
  }

  # Rollout permissions - get/list/watch for scanning, patch for annotation removal
  rule {
    api_groups = ["argoproj.io"]
    resources  = ["rollouts"]
    verbs      = ["get", "list", "watch", "patch"]
  }
}

resource "kubernetes_cluster_role_binding" "rollback_target" {
  count = var.enable_rollback_target_sa ? 1 : 0

  metadata {
    name = "rollback-controller-remote"
    labels = {
      app       = "rollback-controller"
      component = "remote-access"
    }
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.rollback_target[0].metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.rollback_target[0].metadata[0].name
    namespace = kubernetes_namespace.rollback_target[0].metadata[0].name
  }
}

# Long-lived token for the SA (Kubernetes 1.24+ requires explicit Secret for long-lived tokens)
resource "kubernetes_secret" "rollback_target_token" {
  count = var.enable_rollback_target_sa ? 1 : 0

  metadata {
    name      = "rollback-controller-remote-token"
    namespace = kubernetes_namespace.rollback_target[0].metadata[0].name
    annotations = {
      "kubernetes.io/service-account.name" = kubernetes_service_account.rollback_target[0].metadata[0].name
    }
    labels = {
      app       = "rollback-controller"
      component = "remote-access"
    }
  }

  type = "kubernetes.io/service-account-token"
}
