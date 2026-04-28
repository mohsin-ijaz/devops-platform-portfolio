resource "google_managed_kafka_cluster" "gcp-managed-kafka" {
  cluster_id = var.cluster_id
  location   = var.location

  capacity_config {
    vcpu_count   = var.vcpu_count
    memory_bytes = var.memory_bytes
  }

  gcp_config {
    access_config {
      network_configs {
        subnet = var.subnet
      }
    }
  }

  rebalance_config {
    mode = var.rebalance_mode
  }

  labels = var.labels
}

data "google_project" "project" {}

