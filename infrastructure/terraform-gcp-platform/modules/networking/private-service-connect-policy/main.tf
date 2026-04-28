resource "google_network_connectivity_service_connection_policy" "default" {
  name          = var.policy_name
  project       = var.project_id
  location      = var.region
  service_class = var.service_class
  description   = var.description
  network       = var.network
  psc_config {
    subnetworks = var.subnetwork_ids
  }
}