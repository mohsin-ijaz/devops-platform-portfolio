# LGTM Stack Production Infrastructure - Standalone Configuration
# This creates GCS bucket, service accounts, and can be used to create node pools
# Node pools configured with min_node_count = 0 for testing

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ============================================================================
# GCS BUCKET - PRODUCTION STORAGE
# ============================================================================

resource "google_storage_bucket" "lgtm_storage_prod" {
  name          = "<GCS_BUCKET_NAME>"
  project       = var.project_id
  location      = "<GCP_REGION>"
  storage_class = "STANDARD"
  
  force_destroy = false  # Protection for production data
  
  uniform_bucket_level_access = true
  
  # Lifecycle: 90 days retention, then delete
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
  
  # Cost optimization: Move to NEARLINE after 30 days
  lifecycle_rule {
    condition {
      age                   = 30
      matches_storage_class = ["STANDARD"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  
  # Enable versioning for production
  versioning {
    enabled = true
  }
  
  # Soft delete: 30 day recovery window
  soft_delete_policy {
    retention_duration_seconds = 2592000  # 30 days
  }
  
  labels = {
    environment = "production"
    component   = "lgtm-stack"
    managed-by  = "terraform"
    team        = "platform"
    retention   = "90-days"
  }
}

# ============================================================================
# SERVICE ACCOUNTS - PRODUCTION
# ============================================================================

# Loki Service Account
resource "google_service_account" "loki_sa_prod" {
  account_id   = "lgtm-loki-sa-prod"
  display_name = "LGTM Loki Service Account - Production"
  description  = "Service account for Loki to access GCS in production"
  project      = var.project_id
}

# Mimir Service Account
resource "google_service_account" "mimir_sa_prod" {
  account_id   = "lgtm-mimir-sa"
  display_name = "LGTM Mimir Service Account - Production"
  description  = "Service account for Mimir to access GCS in production"
  project      = var.project_id
}

# Tempo Service Account
resource "google_service_account" "tempo_sa_prod" {
  account_id   = "lgtm-tempo-sa-prod"
  display_name = "LGTM Tempo Service Account - Production"
  description  = "Service account for Tempo to access GCS in production"
  project      = var.project_id
}

# Grafana Service Account (if needed for backups/plugins)
resource "google_service_account" "grafana_sa_prod" {
  account_id   = "lgtm-grafana-sa-prod"
  display_name = "LGTM Grafana Service Account - Production"
  description  = "Service account for Grafana in production"
  project      = var.project_id
}

# ============================================================================
# IAM - GCS BUCKET ACCESS
# ============================================================================

# Grant Loki objectAdmin access to bucket
resource "google_storage_bucket_iam_member" "loki_bucket_access" {
  bucket = google_storage_bucket.lgtm_storage_prod.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.loki_sa_prod.email}"
}

# Grant Mimir objectAdmin access to bucket
resource "google_storage_bucket_iam_member" "mimir_bucket_access" {
  bucket = google_storage_bucket.lgtm_storage_prod.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.mimir_sa_prod.email}"
}

# Grant Tempo objectAdmin access to bucket
resource "google_storage_bucket_iam_member" "tempo_bucket_access" {
  bucket = google_storage_bucket.lgtm_storage_prod.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.tempo_sa_prod.email}"
}

# ============================================================================
# WORKLOAD IDENTITY BINDINGS
# ============================================================================

# Loki Workload Identity
resource "google_service_account_iam_binding" "loki_workload_identity" {
  service_account_id = google_service_account.loki_sa_prod.name
  role               = "roles/iam.workloadIdentityUser"
  
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[lgtm-stack/loki-sa-prod]"
  ]
}

# Mimir Workload Identity
resource "google_service_account_iam_binding" "mimir_workload_identity" {
  service_account_id = google_service_account.mimir_sa_prod.name
  role               = "roles/iam.workloadIdentityUser"
  
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[lgtm-stack/mimir-sa]"
  ]
}

# Tempo Workload Identity
resource "google_service_account_iam_binding" "tempo_workload_identity" {
  service_account_id = google_service_account.tempo_sa_prod.name
  role               = "roles/iam.workloadIdentityUser"
  
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[lgtm-stack/tempo-sa-prod]"
  ]
}

# Grafana Workload Identity
resource "google_service_account_iam_binding" "grafana_workload_identity" {
  service_account_id = google_service_account.grafana_sa_prod.name
  role               = "roles/iam.workloadIdentityUser"
  
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[lgtm-stack/grafana-sa-prod]"
  ]
}
