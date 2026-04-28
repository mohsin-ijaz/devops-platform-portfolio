resource "google_compute_ha_vpn_gateway" "ha_gateway" {
  name       = var.name
  project    = var.project_id
  region     = var.region
  network    = var.network
  stack_type = var.stack_type
}