variable "cluster_id" {
  description = "Kafka Cluster ID"
  type        = string
}

variable "location" {
  description = "Region for the Kafka Cluster"
  type        = string
}

variable "vcpu_count" {
  description = "Number of vCPUs for Kafka"
  type        = number
}

variable "memory_bytes" {
  description = "Memory in bytes for Kafka"
  type        = number
}

variable "subnet" {
  description = "Subnet for Kafka"
  type        = string
}

variable "rebalance_mode" {
  description = "Rebalance mode"
  type        = string
}

variable "labels" {
  description = "Labels for Kafka Cluster"
  type        = map(string)
  default     = {}
}


variable "project_id" {}

variable "region" {}

