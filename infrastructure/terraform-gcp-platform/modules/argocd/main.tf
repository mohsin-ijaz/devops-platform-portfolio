# Fetch GCP authentication details
data "google_client_config" "default" {}

# Fetch GKE cluster details
data "google_container_cluster" "gke_cluster" {
  name     = var.cluster_name
  location = var.location
}

provider "helm" {
  kubernetes = {
    host                   = data.google_container_cluster.gke_cluster.endpoint
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(data.google_container_cluster.gke_cluster.master_auth[0].cluster_ca_certificate)

    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "gcloud"
      args = [
        "container",
        "clusters",
        "get-credentials",
        data.google_container_cluster.gke_cluster.name,
        "--region",
        data.google_container_cluster.gke_cluster.location,
        "--project",
        var.project_id
      ]
    }
  }
}

provider "kubernetes" {
  host                   = "https://${data.google_container_cluster.gke_cluster.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(data.google_container_cluster.gke_cluster.master_auth[0].cluster_ca_certificate)
}

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = var.namespace
  }
}

resource "helm_release" "argocd" {
  name       = var.release_name
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.chart_version
  namespace  = kubernetes_namespace.argocd.metadata[0].name

  # Allow passing values file path from child module
  values = var.values_file_path != "" ? [file(var.values_file_path)] : []

  set = [
    for key, value in var.extra_values : {
      name  = key
      value = value
    }
  ]

  # Optionally handle sensitive values securely
  set_sensitive = [
    for key, value in var.sensitive_values : {
      name  = key
      value = value
    }
  ]
}

