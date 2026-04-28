variable "description" {
  type        = string
  description = "A text description of the service account"
}
variable "account_id" {
  type        = string
  description = "Name of service account"
}

variable "display_name" {
  type        = string
  description = "Display name of the created service accounts (defaults to 'Terraform-managed service account')"
}

variable "project_id" {
  type        = string
  description = "The ID of the project that the service account will be created in."
}
