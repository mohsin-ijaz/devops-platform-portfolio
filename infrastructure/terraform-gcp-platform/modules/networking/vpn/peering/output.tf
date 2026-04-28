output "tunnel_peer_gateway_name" {
  value = google_compute_external_vpn_gateway.external_gateway.name
}
output "vpn_router_name" {
  value = google_compute_router.router.name
}