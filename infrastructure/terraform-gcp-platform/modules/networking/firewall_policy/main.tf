/******************************************
	Firewall Rules
*****************************************/
resource "google_compute_firewall" "rules" {
  for_each                = local.rules_all
  name                    = each.value.name
  description             = each.value.description
  direction               = each.value.direction
  disabled                = each.value.disabled
  network                 = var.network_name
  project                 = var.project_id
  source_ranges           = lookup(each.value, "source_ranges", null)
  destination_ranges      = lookup(each.value, "destination_ranges", null)
  source_tags             = each.value.source_tags
  source_service_accounts = each.value.source_service_accounts
  target_tags             = each.value.target_tags
  target_service_accounts = each.value.target_service_accounts
  priority                = each.value.priority

  dynamic "allow" {
    for_each = lookup(each.value, "allow", [])
    content {
      protocol = allow.value.protocol
      ports    = lookup(allow.value, "ports", null)
    }
  }

  dynamic "deny" {
    for_each = lookup(each.value, "deny", [])
    content {
      protocol = deny.value.protocol
      ports    = lookup(deny.value, "ports", null)
    }
  }
}
