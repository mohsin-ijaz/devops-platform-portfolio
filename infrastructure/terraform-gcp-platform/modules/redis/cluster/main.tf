resource "google_redis_cluster" "cluster-ha-single-zone" {
  name   = var.cluster_name
  region = var.region
  zone_distribution_config {
    mode = var.zone_mode
    zone = var.zone
  }
  node_type = var.node_type


  shard_count   = var.shard_count
  replica_count = var.replica_count

  psc_configs {
    network = var.network
  }

  transit_encryption_mode = var.transit_encryption_mode
  authorization_mode      = var.authorization_mode

  persistence_config {
    mode = var.persistence_config.mode
    rdb_config {
      rdb_snapshot_period     = var.persistence_config.rdb_config.rdb_snapshot_period
      rdb_snapshot_start_time = var.persistence_config.rdb_config.rdb_snapshot_start_time
    }
  }

  maintenance_policy {
    weekly_maintenance_window {
      day = var.maintenance_policy.day
      start_time {
        hours   = var.maintenance_policy.start_time.hours
        minutes = var.maintenance_policy.start_time.minutes
        seconds = var.maintenance_policy.start_time.seconds
        nanos   = var.maintenance_policy.start_time.nanos
      }
    }
  }


  deletion_protection_enabled = var.deletion_protection_enabled
}


