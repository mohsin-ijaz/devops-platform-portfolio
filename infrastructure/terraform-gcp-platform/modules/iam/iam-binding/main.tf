resource "google_service_account_iam_member" "service_account_iam_member" {
  for_each           = { for combo in setproduct(var.service_account_roles, var.members) : "${combo[0]}-${combo[1]}" => combo }
  service_account_id = var.service_account_id
  role               = each.value[0]
  member             = each.value[1]
}
