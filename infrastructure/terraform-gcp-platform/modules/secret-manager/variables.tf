variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "secrets" {
  description = "Secrets with namespace and purpose"
  type = map(object({
    env       = string
    namespace = string
    service   = string
    purpose   = string
  }))
}

