variable "project_id" {
  type        = string
  description = "GCP Project ID for Production"
}

variable "service_accounts" {
  type = map(object({
    account_id   = string
    display_name = string
    description  = string
    roles        = list(string)
  }))
  description = "Map of PRODUCTION service accounts to create with their configurations"
  default = {
    mimir = {
      account_id   = "lgtm-mimir-sa"
      display_name = "LGTM Stack Mimir Service Account (Production)"
      description  = "Production service account for Mimir metrics storage component"
      roles = [
        "roles/storage.objectUser"
      ]
    }
    loki = {
      account_id   = "lgtm-loki-sa-prod"
      display_name = "LGTM Stack Loki Service Account (Production)"
      description  = "Production service account for Loki log aggregation component"
      roles = [
        "roles/storage.objectUser"
      ]
    }
    tempo = {
      account_id   = "lgtm-tempo-sa-prod"
      display_name = "LGTM Stack Tempo Service Account (Production)"
      description  = "Production service account for Tempo distributed tracing component"
      roles = [
        "roles/storage.objectUser"
      ]
    }
    grafana = {
      account_id   = "sa-lgtm-grafana-prod"
      display_name = "LGTM Grafana Service Account (Production)"
      description  = "Production Service Account for Grafana"
      roles = [
        "roles/monitoring.viewer",
        "roles/logging.viewer"
      ]
    }
  }
}
