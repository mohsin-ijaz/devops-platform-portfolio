resource "google_organization_iam_member" "group_org_roles" {
  for_each = { for pair in flatten([
    for group in var.groups : [
      for role in group.roles : {
        key   = "${group.email}-${role}"
        email = group.email
        role  = role
      }
    ]
  ]) : pair.key => pair }

  org_id = var.org_id
  role   = each.value.role
  member = "group:${each.value.email}"
}


resource "google_organization_iam_member" "sa_org_roles" {
  for_each = {
    for pair in flatten([
      for sa in var.service_accounts : [
        for role in sa.roles : {
          key   = "${sa.email}-${role}"
          email = sa.email
          role  = role
        }
      ]
    ]) : pair.key => pair
  }

  org_id = var.org_id
  role   = each.value.role
  member = "serviceAccount:${each.value.email}"
}
