resource "google_project_iam_member" "project_iam_member" {
  for_each = { for combo in setproduct(var.project_roles, var.members) : "${combo[0]}-${combo[1]}" => combo }
  project  = var.project_id
  role     = each.value[0]
  member   = each.value[1]

}