resource "google_container_cluster" "gke-pvt-autopilot" {
  name       = var.name
  location   = var.region
  project    = var.project_id
  network    = var.network
  subnetwork = var.subnet

  private_cluster_config {
    enable_private_nodes    = var.enable_private_nodes
    enable_private_endpoint = var.enable_private_endpoint
  }
  allow_net_admin = var.allow_net_admin
  cluster_autoscaling {
    auto_provisioning_defaults {
      service_account = var.service_account
      oauth_scopes    = var.oauth_scopes
    }
  }

  # Enable Autopilot for this cluster
  enable_autopilot    = var.enable_autopilot
  deletion_protection = var.deletion_protection

  ip_allocation_policy {
    cluster_secondary_range_name  = var.cluster_secondary_range_name
    services_secondary_range_name = var.services_secondary_range_name
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
}