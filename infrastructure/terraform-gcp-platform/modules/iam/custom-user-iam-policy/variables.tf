variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "iam_members" {
  type = map(list(string))
}
