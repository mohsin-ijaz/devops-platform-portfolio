resource "google_redis_instance" "cache" {
  name                    = var.name
  project                 = var.project
  display_name            = var.display_name
  memory_size_gb          = var.memory_size_gb
  tier                    = var.tier
  region                  = var.region
  authorized_network      = var.authorized_network
  connect_mode            = var.connect_mode
  auth_enabled            = var.auth_enabled
  redis_version           = var.redis_version
  transit_encryption_mode = var.transit_encryption_mode
  replica_count           = var.replica_count
  read_replicas_mode      = var.read_replicas_mode
  secondary_ip_range      = var.secondary_ip_range

  labels = var.labels

  dynamic "maintenance_policy" {
    for_each = var.maintenance_policy == null ? [] : [var.maintenance_policy]
    content {
      weekly_maintenance_window {
        day = maintenance_policy.value.day
        start_time {
          hours   = maintenance_policy.value.start_time.hours
          minutes = maintenance_policy.value.start_time.minutes
          seconds = maintenance_policy.value.start_time.seconds
          nanos   = maintenance_policy.value.start_time.nanos
        }
      }
    }
  }

  dynamic "persistence_config" {
    for_each = var.persistence_config == null ? [] : [var.persistence_config]
    content {
      persistence_mode        = persistence_config.value.persistence_mode
      rdb_snapshot_period     = try(persistence_config.value.rdb_config.rdb_snapshot_period, null)
      rdb_snapshot_start_time = try(persistence_config.value.rdb_config.rdb_snapshot_start_time, null)
    }
  }
}
