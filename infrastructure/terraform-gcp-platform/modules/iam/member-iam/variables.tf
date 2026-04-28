variable "project_id" {
  description = "Project id"
  type        = string
}

variable "project_roles" {
  description = "List of IAM roles"
  type        = list(string)
}

variable "members" {
  description = "Identities that will be granted the privilege in role"
  type        = list(string)
}

variable "ignored_changes" {
  description = "List of attributes to ignore in lifecycle"
  type        = list(string)
  default     = ["etag"]
}