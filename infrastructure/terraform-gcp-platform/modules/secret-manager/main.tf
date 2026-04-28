resource "google_secret_manager_secret" "secrets" {
  for_each  = var.secrets
  project   = var.project_id
  secret_id = "sec-${each.value.env}-${each.value.namespace}-${each.value.service}-${each.value.purpose}"

  replication {
    user_managed {
      replicas {
        location = "<GCP_REGION>"
      }
    }
  }

  labels = {
    namespace = each.value.namespace
    service   = each.value.service
    purpose   = each.value.purpose
  }
}

