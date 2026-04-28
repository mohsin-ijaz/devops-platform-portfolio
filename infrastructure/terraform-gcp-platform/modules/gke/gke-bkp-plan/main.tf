resource "google_gke_backup_backup_plan" "backup_plan" {
  name     = var.backup_plan_name
  project  = var.project
  location = var.backup_region
  cluster  = var.cluster_id

  backup_schedule {
    cron_schedule = var.backup_schedule_cron
  }


  retention_policy {
    backup_retain_days      = var.retention_days
    backup_delete_lock_days = var.backup_delete_lock_days
  }


  backup_config {
    all_namespaces      = var.all_namespaces ? true : null
    include_secrets     = var.include_secrets
    include_volume_data = var.include_volume_data
    dynamic "selected_namespaces" {
      for_each = var.all_namespaces ? [] : [1]
      content {
        namespaces = var.selected_namespaces
      }
    }

    dynamic "encryption_key" {
      for_each = var.encryption_key_name != null ? [1] : []
      content {
        gcp_kms_encryption_key = var.encryption_key_name
      }
    }
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = true
  }
}
