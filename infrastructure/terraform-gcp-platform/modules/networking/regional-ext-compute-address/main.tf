resource "google_compute_address" "regional_static_ip" {
  name         = var.name
  region       = var.region
  address_type = "EXTERNAL"
  labels       = var.labels
}