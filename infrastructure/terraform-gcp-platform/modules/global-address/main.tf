# Global IP (only EXTERNAL is supported for global)
resource "google_compute_global_address" "global" {
  count = var.scope == "global" ? 1 : 0

  name    = var.address_name
  project = var.project_id
}

# Regional IP (supports EXTERNAL and INTERNAL)
resource "google_compute_address" "regional" {
  count = var.scope == "regional" ? 1 : 0

  name         = var.address_name
  project      = var.project_id
  region       = var.region
  address_type = var.address_type
}


