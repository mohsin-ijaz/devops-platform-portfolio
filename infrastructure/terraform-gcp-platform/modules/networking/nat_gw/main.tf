locals {
  # locals for google_compute_router_nat
  nat_ip_allocate_option = length(var.nat_ips) > 0 ? "MANUAL_ONLY" : "AUTO_ONLY"
}

resource "google_compute_router_nat" "nat" {
  project                             = var.project_id
  region                              = var.region
  name                                = var.natgw_name
  router                              = var.router_name
  nat_ip_allocate_option              = local.nat_ip_allocate_option
  nat_ips                             = var.nat_ips
  source_subnetwork_ip_ranges_to_nat  = var.source_subnetwork_ip_ranges_to_nat
  min_ports_per_vm                    = var.min_ports_per_vm
  max_ports_per_vm                    = var.enable_dynamic_port_allocation ? var.max_ports_per_vm : null
  udp_idle_timeout_sec                = var.udp_idle_timeout_sec
  icmp_idle_timeout_sec               = var.icmp_idle_timeout_sec
  tcp_established_idle_timeout_sec    = var.tcp_established_idle_timeout_sec
  tcp_transitory_idle_timeout_sec     = var.tcp_transitory_idle_timeout_sec
  tcp_time_wait_timeout_sec           = var.tcp_time_wait_timeout_sec
  enable_endpoint_independent_mapping = var.enable_endpoint_independent_mapping
  enable_dynamic_port_allocation      = var.enable_dynamic_port_allocation

  dynamic "subnetwork" {
    for_each = var.subnetworks
    content {
      name                     = subnetwork.value.name
      source_ip_ranges_to_nat  = subnetwork.value.source_ip_ranges_to_nat
      secondary_ip_range_names = contains(subnetwork.value.source_ip_ranges_to_nat, "LIST_OF_SECONDARY_IP_RANGES") ? subnetwork.value.secondary_ip_range_names : []
    }
  }

  dynamic "log_config" {
    for_each = var.log_config_enable == true ? [{
      enable = var.log_config_enable
      filter = var.log_config_filter
    }] : []

    content {
      enable = log_config.value.enable
      filter = log_config.value.filter
    }
  }
}