# Outputs for LGTM Production Infrastructure

output "bucket_name" {
  description = "GCS bucket name for LGTM production storage"
  value       = google_storage_bucket.lgtm_storage_prod.name
}

output "bucket_url" {
  description = "GCS bucket URL"
  value       = google_storage_bucket.lgtm_storage_prod.url
}

output "loki_sa_email" {
  description = "Loki service account email"
  value       = google_service_account.loki_sa_prod.email
}

output "mimir_sa_email" {
  description = "Mimir service account email"
  value       = google_service_account.mimir_sa_prod.email
}

output "tempo_sa_email" {
  description = "Tempo service account email"
  value       = google_service_account.tempo_sa_prod.email
}

output "grafana_sa_email" {
  description = "Grafana service account email"
  value       = google_service_account.grafana_sa_prod.email
}

output "kubernetes_namespace" {
  description = "Kubernetes namespace for production LGTM stack"
  value       = "lgtm-stack"
}

output "kubernetes_service_accounts" {
  description = "Kubernetes service account names to create"
  value = {
    loki    = "loki-sa-prod"
    mimir   = "mimir-sa"
    tempo   = "tempo-sa-prod"
    grafana = "grafana-sa-prod"
  }
}
