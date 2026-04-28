output "gateway" {
  description = "HA VPN gateway resource."
  value       = google_compute_ha_vpn_gateway.ha_gateway
}

output "name" {
  description = "VPN gateway name."
  value       = google_compute_ha_vpn_gateway.ha_gateway.name
}