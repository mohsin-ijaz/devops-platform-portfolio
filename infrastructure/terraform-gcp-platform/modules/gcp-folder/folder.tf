resource "google_folder" "folder" {
  display_name = var.folder_name
  parent       = var.parent_folder
  tags         = var.tags
}

output "folder_id" {
  value = google_folder.folder.name
}

