resource "google_container_cluster" "main" {
  name                = var.cluster
  description         = var.description
  project             = var.project_id
  resource_labels     = var.labels
  location            = var.region
  network             = var.network
  subnetwork          = var.subnetwork
  initial_node_count  = var.initial_node_count
  deletion_protection = var.deletion_protection

  dynamic "master_authorized_networks_config" {
    for_each = var.master_authorized_networks_config
    content {
      dynamic "cidr_blocks" {
        for_each = master_authorized_networks_config.value.cidr_blocks
        content {
          cidr_block   = lookup(cidr_blocks.value, "cidr_block", "")
          display_name = lookup(cidr_blocks.value, "display_name", "")
        }
      }
    }
  }

  master_auth {
    client_certificate_config {
      issue_client_certificate = var.issue_client_certificate
    }
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.ip_range_pods
    services_secondary_range_name = var.ip_range_services
  }



  enable_shielded_nodes = var.enable_shielded_nodes
  min_master_version    = var.master_version

  workload_identity_config {
    workload_pool = var.workload_pool
  }

  release_channel {
    channel = var.release_channel
  }

  gateway_api_config {
    channel = var.gateway_api_channel
  }

  dynamic "cost_management_config" {
    for_each = var.enable_cost_allocation ? [1] : []
    content {
      enabled = var.enable_cost_allocation
    }
  }

  private_cluster_config {
    enable_private_endpoint = var.enable_private_endpoint
    enable_private_nodes    = var.enable_private_nodes
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
    master_global_access_config {
      enabled = var.master_global_access
    }
  }

  security_posture_config {
    mode               = var.security_mode
    vulnerability_mode = var.vulnerability_mode
  }

  monitoring_config {
    enable_components = var.monitoring_enabled_components
  }

  node_config {
    gcfs_config {
      enabled = var.enable_gcfs
    }
  }

  remove_default_node_pool = var.remove_default_node_pool

  addons_config {
    http_load_balancing {
      disabled = !var.http_load_balancing
    }

    horizontal_pod_autoscaling {
      disabled = !var.horizontal_pod_autoscaling
    }

    network_policy_config {
      disabled = !var.network_policy
    }

    dns_cache_config {
      enabled = var.dns_cache
    }

    gcp_filestore_csi_driver_config {
      enabled = var.filestore_csi_driver
    }

    gce_persistent_disk_csi_driver_config {
      enabled = var.gce_pd_csi_driver
    }

    gke_backup_agent_config {
      enabled = var.gke_backup_agent_config
    }
  }
}

resource "google_compute_network_peering_routes_config" "peering_gke_routes" {
  peering              = google_container_cluster.main.private_cluster_config[0].peering_name
  network              = var.network
  project              = var.project_id
  import_custom_routes = var.import_custom_routes
  export_custom_routes = var.export_custom_routes
}

