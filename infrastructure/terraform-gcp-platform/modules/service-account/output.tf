output "service_account_email" {
  value = google_service_account.service_account.email
}

output "service_account_name" {
  value = google_service_account.service_account.name
}
