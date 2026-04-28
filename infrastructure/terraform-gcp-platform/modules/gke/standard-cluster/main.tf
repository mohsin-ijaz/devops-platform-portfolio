resource "google_container_cluster" "gke-cluster-01" {
  name                     = var.name
  location                 = var.location
  project                  = var.project
  network                  = var.network
  subnetwork               = var.subnetwork
  enable_shielded_nodes    = var.enable_shielded_nodes
  remove_default_node_pool = var.remove_default_node_pool
  deletion_protection      = false
  initial_node_count       = var.initial_node_count
  #allow_net_admin          = true
  min_master_version = var.min_master_version

  ip_allocation_policy {
    cluster_secondary_range_name  = var.cluster_secondary_range_name
    services_secondary_range_name = var.services_secondary_range_name
  }


  logging_config {
    enable_components = var.enable_components
  }

  master_auth {
    client_certificate_config {
      issue_client_certificate = var.issue_client_certificate
    }
  }

  master_authorized_networks_config {
    gcp_public_cidrs_access_enabled      = var.gcp_public_cidrs_access_enabled
    private_endpoint_enforcement_enabled = var.private_endpoint_enforcement_enabled

    dynamic "cidr_blocks" {
      for_each = var.authorized_networks
      content {
        cidr_block   = cidr_blocks.value["cidr_block"]
        display_name = cidr_blocks.value["display_name"]
      }
    }
  }

  network_policy {
    enabled = var.network_policy
  }

  private_cluster_config {
    enable_private_endpoint = var.enable_private_endpoint
    enable_private_nodes    = var.enable_private_nodes
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
    master_global_access_config {
      enabled = var.master_global_access
    }
  }

  release_channel {
    channel = var.channel
  }

  gateway_api_config {
    channel = var.gateway_api_channel
  }

  workload_identity_config {
    workload_pool = var.workload_pool
  }

  maintenance_policy {
    recurring_window {
      start_time = var.maintenance_start_time
      end_time   = var.maintenance_end_time
      recurrence = var.maintenance_recurrence
    }
  }

  resource_labels = var.labels

  # Optional and dynamic addon configuration for GKE Backup Agent
  dynamic "addons_config" {
    for_each = var.enable_backup_agent ? [1] : []
    content {
      gke_backup_agent_config {
        enabled = true
      }
    }
  }

  lifecycle {
    ignore_changes = [
      min_master_version
    ]
  }

}


resource "google_container_node_pool" "node_pools" {
  for_each = { for np in var.node_pools : np.name => np }

  cluster  = google_container_cluster.gke-cluster-01.name
  location = var.location
  project  = var.project
  name     = each.value.name
  version  = each.value.node_version

  autoscaling {
    max_node_count = each.value.max_node_count
    min_node_count = each.value.min_node_count
  }

  management {
    auto_repair  = each.value.auto_repair
    auto_upgrade = each.value.auto_upgrade
  }

  max_pods_per_node = each.value.max_pods_per_node

  node_config {
    disk_size_gb    = each.value.disk_size_gb
    disk_type       = each.value.disk_type
    machine_type    = each.value.machine_type
    oauth_scopes    = var.oauth_scopes
    service_account = var.service_account
    preemptible     = each.value.preemptible

    tags = each.value.tags

    # Apply labels if provided
    labels = each.value.labels != null ? each.value.labels : {}

    # Apply taints if provided
    dynamic "taint" {
      for_each = each.value.taints != null ? each.value.taints : []
      content {
        key    = taint.value.key
        value  = taint.value.value
        effect = taint.value.effect
      }
    }

    gcfs_config {
      enabled = true
    }

    shielded_instance_config {
      enable_integrity_monitoring = var.enable_integrity_monitoring
      enable_secure_boot          = var.enable_secure_boot
    }
  }

  upgrade_settings {
    max_surge       = var.max_surge
    max_unavailable = var.max_unavailable
  }

  lifecycle {
    ignore_changes = [
      version
    ]
  }
}



######
