resource "google_folder_iam_member" "group_org_roles" {
  for_each = { for pair in flatten([
    for group in var.groups : [
      for role in group.roles : {
        key   = "${group.email}-${role}"
        email = group.email
        role  = role
      }
    ]
  ]) : pair.key => pair }

  folder = var.folder
  role   = each.value.role
  member = "group:${each.value.email}"
}
