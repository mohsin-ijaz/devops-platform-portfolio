variable "cluster_name" {
  type        = string
  description = "Name of the redis cluster to be created"
}

variable "shard_count" {
  type        = number
  description = "Number of shards for the Redis cluster"
}

variable "zone_mode" {
  type        = string
  description = "The mode for zone distribution for Memorystore Redis cluster. If not provided, MULTI_ZONE will be used as default Possible"

}

variable "zone" {
  type        = string
  description = "The zone for single zone Memorystore Redis cluster"
}

variable "replica_count" {
  type        = string
  description = "Number of replicas per shard"
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
}

variable "persistence_config" {
  description = "Persistence configuration for Redis cluster"
  type = object({
    mode = string
    rdb_config = object({
      rdb_snapshot_period     = string
      rdb_snapshot_start_time = string
    })
  })
}

variable "deletion_protection_enabled" {
  type    = bool
  default = true
}


variable "region" {
  type        = string
  description = "The location of the ServiceConnectionPolicy"
}

variable "node_type" {
  type        = string
  description = "The nodeType for the Redis cluster"
}

variable "authorization_mode" {
  type        = string
  description = "The authorization mode of the Redis cluster. If not provided, auth feature is disabled for the cluster"
}

variable "transit_encryption_mode" {
  type        = string
  description = "The in-transit encryption for the Redis cluster. If not provided, encryption is disabled for the cluster."
}

variable "network" {
  type        = string
  description = "The resource path of the consumer network"
}

