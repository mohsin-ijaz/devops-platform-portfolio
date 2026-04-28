output "iam_bindings" {
  description = "IAM bindings created by this module"
  value       = google_project_iam_member.bindings
}