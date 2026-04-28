resource "google_artifact_registry_repository" "artifact_registry" {
  location      = var.location
  repository_id = var.repository_id
  description   = var.description
  format        = var.format
  project       = var.project_id
  labels        = var.labels

  dynamic "cleanup_policies" {
    for_each = var.cleanup_policies != [] ? var.cleanup_policies : []
    content {
      action = cleanup_policies.value.action
      id     = cleanup_policies.value.id

      condition {
        tag_state             = try(cleanup_policies.value.condition.tag_state, null)
        tag_prefixes          = try(cleanup_policies.value.condition.tag_prefixes, null)
        package_name_prefixes = try(cleanup_policies.value.condition.package_name_prefixes, null)
        version_name_prefixes = try(cleanup_policies.value.condition.version_name_prefixes, null)
        older_than            = try(cleanup_policies.value.condition.older_than, null)
      }
    }
  }
}
