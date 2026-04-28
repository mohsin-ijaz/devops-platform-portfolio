variable "cluster_id" {
  description = "Full resource ID of the GKE cluster"
  type        = string
}

variable "project" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The region where the GKE cluster is located"
  type        = string
}

variable "backup_region" {
  description = "The region where backups will be stored"
  type        = string
}

variable "backup_plan_name" {
  description = "Name of the backup plan"
  type        = string
}

variable "backup_schedule_cron" {
  description = "Cron expression for backup schedule"
  type        = string
}

variable "retention_days" {
  description = "Number of days to retain backups"
  type        = number
  default     = 30
  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 365
    error_message = "Retention days must be between 1 and 365."
  }
}

variable "backup_delete_lock_days" {
  description = "Number of days to prevent backup deletion (delete lock period)"
  type        = number
  default     = 7
  validation {
    condition     = var.backup_delete_lock_days >= 1 && var.backup_delete_lock_days <= 30
    error_message = "Backup delete lock days must be between 1 and 30."
  }
}

variable "encryption_key_name" {
  description = "Customer-managed encryption key name"
  type        = string
  default     = null
}

variable "cross_project_backup" {
  description = "Enable cross-project backup"
  type        = bool
  default     = false
}

variable "backup_project_id" {
  description = "Project ID for cross-project backup storage"
  type        = string
  default     = null
}

variable "include_secrets" {
  description = "Include Kubernetes secrets in backups"
  type        = bool
  default     = true
}

variable "include_volume_data" {
  description = "Include persistent volume data in backups"
  type        = bool
  default     = true
}

variable "selected_namespaces" {
  description = "List of specific namespaces to backup"
  type        = list(string)
  default     = []
}

variable "all_namespaces" {
  description = "Backup all namespaces in the cluster"
  type        = bool
  default     = true
}

variable "enable_monitoring" {
  description = "Enable monitoring and alerting"
  type        = bool
  default     = true
}

variable "notification_channels" {
  description = "List of notification channels for backup alerts"
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Labels to apply to the backup plan."
  type        = map(string)
  default     = {}
}
