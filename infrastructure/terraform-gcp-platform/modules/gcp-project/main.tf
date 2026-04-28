resource "google_project" "google_project" {
  name                = var.project_name
  billing_account     = var.billing_account
  project_id          = var.new_project_id
  org_id              = var.org_id
  auto_create_network = var.auto_create_network
  tags                = var.tags
  folder_id           = var.folder_id
}
