resource "google_sql_database_instance" "sql" {
  for_each            = var.instances
  project             = var.project_id
  name                = each.value.name
  region              = var.region
  database_version    = each.value.database_version
  deletion_protection = each.value.deletion_protection

  settings {
    tier                        = each.value.tier
    edition                     = each.value.edition
    availability_type           = each.value.availability_type
    disk_size                   = each.value.disk_size
    activation_policy           = each.value.activation_policy
    deletion_protection_enabled = each.value.deletion_protection_enabled

    # ✅ Dynamic final_backup_config
    dynamic "final_backup_config" {
      for_each = lookup(each.value, "final_backup_config", null) != null ? [each.value.final_backup_config] : []
      content {
        enabled        = final_backup_config.value.enabled
        retention_days = final_backup_config.value.retention_days
      }
    }

    retain_backups_on_delete = lookup(each.value, "retain_backups_on_delete", null)

    dynamic "backup_configuration" {
      for_each = each.value.backup_enable ? [1] : []
      content {
        enabled    = each.value.backup_enable
        start_time = each.value.backup_start_time

        # PostgreSQL / SQL Server PITR
        point_in_time_recovery_enabled = (
          contains(["POSTGRES", "SQLSERVER"], split("_", each.value.database_version)[0])
          ? each.value.pitr_enable
          : null
        )

        # MySQL PITR
        binary_log_enabled = (
          startswith(each.value.database_version, "MYSQL")
          ? each.value.pitr_enable
          : null
        )

        dynamic "backup_retention_settings" {
          for_each = each.value.retained_backups > 0 ? [1] : []
          content {
            retained_backups = each.value.retained_backups
            retention_unit   = each.value.retention_unit
          }
        }
      }
    }

    ip_configuration {
      ipv4_enabled    = each.value.ipv4_enabled
      private_network = each.value.private_network

      dynamic "authorized_networks" {
        for_each = each.value.authorized_networks
        content {
          name  = authorized_networks.value.name
          value = authorized_networks.value.value
        }
      }

      # ✅ PSC config per instance (optional)
      dynamic "psc_config" {
        for_each = lookup(each.value, "psc_config", null) != null ? [each.value.psc_config] : []
        content {
          psc_enabled               = psc_config.value.psc_enabled
          allowed_consumer_projects = psc_config.value.allowed_consumer_projects
        }
      }

    }
    # ✅ Per-instance maintenance window
    dynamic "maintenance_window" {
      for_each = each.value.maintenance_enable ? [1] : []
      content {
        day          = each.value.maintenance_day
        hour         = each.value.maintenance_hour
        update_track = each.value.update_track
      }
    }



    user_labels = each.value.labels != null ? each.value.labels : {}
  }



  lifecycle {
    ignore_changes = [
      name,
      settings[0].database_flags,
      settings[0].ip_configuration[0].psc_config,
    ]
  }
}
