# Define the host project
resource "google_compute_shared_vpc_host_project" "host" {
  project = var.host_project_id
}

# Use for_each to iterate over the service projects
resource "google_compute_shared_vpc_service_project" "service" {
  for_each        = toset(var.service_projects)
  host_project    = google_compute_shared_vpc_host_project.host.project
  service_project = each.value
  depends_on      = [google_compute_shared_vpc_host_project.host]
}