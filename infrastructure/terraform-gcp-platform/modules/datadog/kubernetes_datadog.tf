provider "kubernetes" {
  host                   = var.cluster_endpoint != null ? "https://${var.cluster_endpoint}" : null
  token                  = var.cluster_access_token
  cluster_ca_certificate = var.cluster_ca_certificate != null ? base64decode(var.cluster_ca_certificate) : null
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = var.namespace
    labels = {
      "goldilocks.fairwinds.com/enabled" = "true"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
