resource "google_compute_global_address" "global_address" {
  name         = var.address_name
  address_type = var.address_type
  labels       = var.labels
}
