resource "google_project_iam_member" "bindings" {
  for_each = {
    for pair in flatten([
      for principal, roles in var.iam_members : [
        for role in roles : {
          key    = "${principal}:::${role}"
          member = principal
          role   = role
        }
      ]
      ]) : pair.key => {
      member = pair.member
      role   = pair.role
    }
  }

  project = var.project_id
  role    = each.value.role
  member  = each.value.member
}