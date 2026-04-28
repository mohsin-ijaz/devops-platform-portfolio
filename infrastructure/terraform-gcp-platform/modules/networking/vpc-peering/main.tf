# Forward peering
resource "google_compute_network_peering" "forward" {
  for_each = {
    for pair in var.vpc_peering_pairs :
    "${coalesce(pair.project1, var.project_id)}-${pair.vpc1}__${coalesce(pair.project2, var.project_id)}-${pair.vpc2}" => pair
    if lookup(pair, "create_forward", true)
  }


  name = coalesce(each.value.name, "peer-${each.value.vpc1}-${each.value.vpc2}")

  network      = "projects/${coalesce(each.value.project1, var.project_id)}/global/networks/${each.value.vpc1}"
  peer_network = "projects/${coalesce(each.value.project2, var.project_id)}/global/networks/${each.value.vpc2}"

  export_custom_routes                 = each.value.forward_export_custom_routes
  import_custom_routes                 = each.value.forward_import_custom_routes
  export_subnet_routes_with_public_ip  = each.value.forward_export_subnet_routes_with_public_ip
  import_subnet_routes_with_public_ip  = each.value.forward_import_subnet_routes_with_public_ip
}

# Reverse peering
resource "google_compute_network_peering" "reverse" {
  for_each = {
    for pair in var.vpc_peering_pairs :
    "${coalesce(pair.project2, var.project_id)}-${pair.vpc2}__${coalesce(pair.project1, var.project_id)}-${pair.vpc1}" => pair
    if lookup(pair, "create_reverse", false)
  }

  name = coalesce(each.value.name, "peer-${each.value.vpc2}-${each.value.vpc1}")
  network      = "projects/${coalesce(each.value.project2, var.project_id)}/global/networks/${each.value.vpc2}"
  peer_network = "projects/${coalesce(each.value.project1, var.project_id)}/global/networks/${each.value.vpc1}"

  export_custom_routes                 = lookup(each.value, "reverse_export_custom_routes", false)
  import_custom_routes                 = lookup(each.value, "reverse_import_custom_routes", false)
  export_subnet_routes_with_public_ip  = lookup(each.value, "reverse_export_subnet_routes_with_public_ip", false)
  import_subnet_routes_with_public_ip  = lookup(each.value, "reverse_import_subnet_routes_with_public_ip", false)
}
