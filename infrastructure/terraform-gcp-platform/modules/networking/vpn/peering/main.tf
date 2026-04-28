resource "google_compute_router" "router" {
  name    = var.router_name
  network = var.network
  project = var.project_id
  region  = var.region

  bgp {
    asn = var.asn
    advertise_mode = (
      var.router_advertise_config == null
      ? null
      : var.router_advertise_config.mode
    )
    advertised_groups = (
      var.router_advertise_config == null ? null : (
        var.router_advertise_config.mode != "CUSTOM"
        ? null
        : var.router_advertise_config.groups
      )
    )

    dynamic "advertised_ip_ranges" {
      for_each = (
        var.router_advertise_config == null ? {} : (
          var.router_advertise_config.mode != "CUSTOM"
          ? {}
          : var.router_advertise_config.ip_ranges
        )
      )
      iterator = range
      content {
        range       = range.key
        description = range.value
      }
    }
  }
}

resource "google_compute_external_vpn_gateway" "external_gateway" {
  name            = var.external_gateway_name
  project         = var.project_id
  redundancy_type = var.redundancy_type

  dynamic "interface" {
    for_each = var.external_vpn_gateway_interfaces
    content {
      id         = interface.key
      ip_address = interface.value["tunnel_address"]
    }
  }
}

data "google_secret_manager_secret_version" "shared_secret" {
  for_each = var.external_vpn_gateway_interfaces
  project  = var.project_id
  secret   = each.value.secret_name
}

resource "google_compute_vpn_tunnel" "tunnels" {
  for_each                        = var.external_vpn_gateway_interfaces
  region                          = var.region
  name                            = each.value.name_tunnel
  project                         = var.project_id
  router                          = google_compute_router.router.self_link
  ike_version                     = var.ike_version
  shared_secret                   = data.google_secret_manager_secret_version.shared_secret[each.key].secret_data
  vpn_gateway                     = var.gateway_name
  vpn_gateway_interface           = each.value.vpn_gateway_interface
  peer_external_gateway           = google_compute_external_vpn_gateway.external_gateway.self_link
  peer_external_gateway_interface = each.key

}

resource "google_compute_router_interface" "interfaces" {
  for_each   = var.external_vpn_gateway_interfaces
  project    = var.project_id
  region     = var.region
  name       = each.value.router_int_name
  router     = google_compute_router.router.name
  ip_range   = each.value.cgw_inside_address
  vpn_tunnel = google_compute_vpn_tunnel.tunnels[each.key].name
}

resource "google_compute_router_peer" "router_peers" {
  for_each        = var.external_vpn_gateway_interfaces
  project         = var.project_id
  region          = var.region
  name            = each.value.router_peer_name
  router          = google_compute_router.router.name
  peer_ip_address = each.value.vgw_inside_address
  peer_asn        = each.value.asn
  interface       = google_compute_router_interface.interfaces[each.key].name

  advertise_mode = (
    var.router_advertise_config == null
    ? null
    : var.router_advertise_config.mode
  )
  advertised_groups = (
    var.router_advertise_config == null ? null : (
      var.router_advertise_config.mode != "CUSTOM"
      ? null
      : var.router_advertise_config.groups
    )
  )

  dynamic "advertised_ip_ranges" {
    for_each = (
      var.router_advertise_config == null ? {} : (
        var.router_advertise_config.mode != "CUSTOM"
        ? {}
        : var.router_advertise_config.ip_ranges
      )
    )
    iterator = range
    content {
      range       = range.key
      description = range.value
    }
  }
}
