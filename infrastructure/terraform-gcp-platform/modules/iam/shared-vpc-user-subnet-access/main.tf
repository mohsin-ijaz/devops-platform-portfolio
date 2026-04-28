resource "google_compute_subnetwork_iam_member" "subnet_access" {
  for_each = { for combo in setproduct(var.project_roles, var.members) : "${combo[0]}-${combo[1]}" => combo }

  project    = var.project_id
  region     = var.region
  subnetwork = var.subnetwork
  role       = each.value[0]
  member     = each.value[1]
}

