output "gateway" {
  description = "HA VPN gateway resource."
  value       = google_compute_ha_vpn_gateway.ha_gateway
}


output "name" {
  description = "VPN gateway name."
  value       = google_compute_ha_vpn_gateway.ha_gateway.name
}

output "router" {
  description = "Router resource."
  value       = google_compute_router.router.name
}

output "router_name" {
  description = "Router name."
  value       = google_compute_router.router.name
}

output "self_link" {
  description = "HA VPN gateway self link."
  value       = google_compute_ha_vpn_gateway.ha_gateway.self_link
}

output "tunnels" {
  description = "VPN tunnel resources."
  sensitive   = true
  value = {
    for name in keys(var.tunnels) :
    name => google_compute_vpn_tunnel.tunnels[name]
  }
}

output "tunnel_names" {
  description = "VPN tunnel names."
  value = {
    for name in keys(var.tunnels) :
    name => google_compute_vpn_tunnel.tunnels[name].name
  }
}

output "tunnel_self_links" {
  description = "VPN tunnel self links."
  sensitive   = true
  value = {
    for name in keys(var.tunnels) :
    name => google_compute_vpn_tunnel.tunnels[name].self_link
  }
}

output "random_secret" {
  description = "Generated secret."
  sensitive   = true
  value       = local.secret
}