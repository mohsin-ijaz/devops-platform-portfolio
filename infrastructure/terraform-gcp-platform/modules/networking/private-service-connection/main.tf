resource "google_compute_global_address" "gcp_managed_svc_subnet_ranges" {
  address       = var.address
  address_type  = var.address_type
  name          = var.pvt_svc_name
  network       = var.network_name
  prefix_length = var.prefix_length
  project       = var.project_id
  purpose       = var.purpose
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = var.network_name
  service                 = var.service
  reserved_peering_ranges = [google_compute_global_address.gcp_managed_svc_subnet_ranges.name]
}

resource "google_compute_network_peering_routes_config" "peering_routes" {
  peering              = var.peering_name
  network              = var.network_name
  project              = var.project_id
  import_custom_routes = var.import_custom_routes
  export_custom_routes = var.export_custom_routes
}