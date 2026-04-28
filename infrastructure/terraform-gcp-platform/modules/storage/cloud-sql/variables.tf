variable "project_id" {
  description = "The ID of the project in which to create the database instance."
  type        = string
}

variable "region" {
  description = "The region in which the database instance will be created."
  type        = string
}

variable "instances" {
  description = "Map of database instances to be created with relevant configuration."
  type = map(object({
    name                        = string
    database_version            = string
    deletion_protection         = bool
    deletion_protection_enabled = optional(bool)
    tier                        = string
    edition                     = string
    availability_type           = string
    disk_size                   = number
    private_network             = string
    backup_enable               = bool
    backup_start_time           = string
    pitr_enable                 = bool
    maintenance_enable          = optional(bool, false)
    maintenance_day             = optional(number)
    maintenance_hour            = optional(number)
    update_track                = optional(string)
    retained_backups            = number
    retention_unit              = string
    labels                      = optional(map(string))
    ipv4_enabled                = bool
    activation_policy           = optional(string)
    authorized_networks = list(object({
      name  = string
      value = string
    }))
    psc_config = optional(object({
      psc_enabled               = bool
      allowed_consumer_projects = list(string)
    }))
    final_backup_config = optional(object({
      enabled        = bool
      retention_days = number
    }))
    retain_backups_on_delete = optional(bool)
  }))
  default = {}

}

variable "backup_enable" {
  description = "Enable or disable database backups."
  type        = bool
  default     = false
}
