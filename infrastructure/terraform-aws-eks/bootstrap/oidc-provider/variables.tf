variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "gitlab_url" {
  description = "GitLab instance URL"
  type        = string
}

variable "gitlab_project_path" {
  description = "GitLab project path (e.g., Acme/infrastructure/acme-platform-terraform-infra)"
  type        = string
  default     = ""
}

variable "allowed_branches" {
  description = "List of branches allowed to assume the role"
  type        = list(string)
  default     = []
}

variable "allowed_subjects" {
  description = "List of allowed subjects (overrides gitlab_project_path and allowed_branches)"
  type        = list(string)
  default     = []
}

variable "role_name" {
  description = "Name of the IAM role for GitLab CI"
  type        = string
}

variable "role_max_session_duration" {
  description = "Maximum session duration in seconds"
  type        = number
}

variable "attach_admin_policy" {
  description = "Attach AdministratorAccess policy (for Terraform operations)"
  type        = bool
}

variable "environment" {
  description = "Environment name (network, uat, prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
}
