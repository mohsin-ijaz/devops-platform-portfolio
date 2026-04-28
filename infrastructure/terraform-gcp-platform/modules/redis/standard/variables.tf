variable "name" {
  type        = string
  description = "The ID of the redis instance"
}

variable "display_name" {
  type        = string
  description = "An arbitrary and optional user-provided name for the instance"
}

variable "memory_size_gb" {
  type        = number
  description = "Redis memory size in GiB"
}

variable "tier" {
  type        = string
  description = "The service tier of the instance"
}


variable "project" {
  type        = string
  description = "ID of the project in which the resource will be launched"
}

variable "authorized_network" {
  type        = string
  description = "The full name of the Google Compute Engine network to which the instance is connected"
}


variable "connect_mode" {
  type        = string
  description = "The connection mode of the Redis instance"
}

variable "replica_count" {
  type        = string
  description = "No. of replicas "
}

variable "read_replicas_mode" {
  type        = string
  description = "If not set, Memorystore Redis backend will default to READ_REPLICAS_DISABLED."
}

variable "auth_enabled" {
  type        = bool
  description = "Indicates whether OSS Redis AUTH is enabled for the instance"
}

variable "transit_encryption_mode" {
  type        = string
  description = "The TLS mode of the Redis instance, If not provided, TLS is disabled for the instance"
}

variable "region" {
  type        = string
  description = "The name of the Redis region of the instance"
}

variable "redis_version" {
  type        = string
  description = "The version of Redis software"
}

variable "labels" {
  type        = map(string)
  description = "Labels, provided as a map"
}

variable "secondary_ip_range" {
  type        = string
  description = "The name of the secondary IP range for Redis replication"
  default     = null
}

variable "maintenance_policy" {
  description = "Weekly maintenance window configuration"
  type = object({
    day = string
    start_time = object({
      hours   = number
      minutes = number
      seconds = number
      nanos   = number
    })
  })
  default = null
}

variable "persistence_config" {
  description = "Persistence configuration for Redis cluster"
  type = object({
    persistence_mode = string
    rdb_config = object({
      rdb_snapshot_period     = string
      rdb_snapshot_start_time = string
    })
  })
  default = null
}
