# LGTM Stack Production Service Accounts
# Based on: cs-dev-terraform-infra/environments/mgmt/service-accounts/lgtm-service-accounts/
# Target Namespace: lgtm-stack
# Target Bucket: <GCS_BUCKET_NAME>

# Create service accounts dynamically for PRODUCTION
module "service_accounts" {
  source   = "../../../../modules/service-account"  # Adjust path based on your repo structure
  for_each = var.service_accounts

  description  = each.value.description
  project_id   = var.project_id
  account_id   = each.value.account_id
  display_name = each.value.display_name
}

# Assign IAM roles to service accounts dynamically
module "member_roles" {
  source   = "../../../../modules/iam/member-iam"  # Adjust path
  for_each = var.service_accounts

  project_id    = var.project_id
  project_roles = each.value.roles
  members       = ["serviceAccount:${module.service_accounts[each.key].service_account_email}"]

  depends_on = [module.service_accounts]
}

# Create Workload Identity bindings for GKE PRODUCTION namespace
resource "google_service_account_iam_binding" "workload_identity_binding" {
  for_each = var.service_accounts

  service_account_id = module.service_accounts[each.key].service_account_name
  role               = "roles/iam.workloadIdentityUser"

  # IMPORTANT: Binds to lgtm-stack namespace with -prod suffix
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[lgtm-stack/${each.key}-sa-prod]"
  ]

  depends_on = [module.service_accounts]
}

# Grant bucket access to storage service accounts (Mimir, Loki, Tempo)
resource "google_storage_bucket_iam_member" "bucket_access" {
  for_each = {
    for name, sa in var.service_accounts : name => sa
    if contains(["mimir", "loki", "tempo"], name)
  }

  bucket = "<GCS_BUCKET_NAME>"  # PRODUCTION bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.service_accounts[each.key].service_account_email}"

  depends_on = [module.service_accounts]
}
