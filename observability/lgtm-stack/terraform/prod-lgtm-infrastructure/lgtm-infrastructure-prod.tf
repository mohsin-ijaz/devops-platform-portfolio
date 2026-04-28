# LGTM Stack PRODUCTION Storage Infrastructure
# Based on: cs-dev-terraform-infra/environments/mgmt/gke/.../lgtm-infrastructure.tf
# Environment: PRODUCTION
# Namespace: lgtm-stack

# Local values for LGTM Stack PRODUCTION storage
locals {
  lgtm_storage_bucket_prod = "<GCS_BUCKET_NAME>"
}

# GCS Bucket for LGTM Stack PRODUCTION storage backend
resource "google_storage_bucket" "lgtm_storage_prod" {
  name          = local.lgtm_storage_bucket_prod
  project       = var.project
  location      = "<GCP_REGION>"
  storage_class = "STANDARD"
  
  # PRODUCTION: Do NOT force destroy (data protection)
  force_destroy = false
  
  # Uniform bucket-level access for security
  uniform_bucket_level_access = true
  
  # Lifecycle policy for PRODUCTION - 90 days retention
  lifecycle_rule {
    condition {
      age = 90  # Delete after 90 days for production
    }
    action {
      type = "Delete"
    }
  }
  
  # Optional: Tiered storage for cost optimization
  lifecycle_rule {
    condition {
      age                   = 30
      matches_storage_class = ["STANDARD"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"  # Move to cheaper storage after 30 days
    }
  }
  
  # Versioning ENABLED for production (data recovery)
  versioning {
    enabled = true
  }
  
  # Soft delete policy (30 days recovery window)
  soft_delete_policy {
    retention_duration_seconds = 2592000  # 30 days
  }
  
  # Labels for resource management
  labels = {
    environment = "production"
    component   = "lgtm-stack"
    managed-by  = "terraform"
    team        = "platform"
    retention   = "90-days"
    criticality = "high"
  }
}

# Output the bucket name for Helm charts
output "lgtm_storage_bucket_prod" {
  description = "GCS bucket name for LGTM Stack PRODUCTION storage"
  value       = google_storage_bucket.lgtm_storage_prod.name
}

output "lgtm_storage_bucket_url_prod" {
  description = "GCS bucket URL for LGTM Stack PRODUCTION storage"
  value       = google_storage_bucket.lgtm_storage_prod.url
}
