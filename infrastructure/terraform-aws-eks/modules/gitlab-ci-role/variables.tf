# GitLab CI Role Module Variables

variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "gitlab_url" {
  description = "GitLab instance URL"
  type        = string
  default     = "https://gitlab.com"
}

variable "allowed_subjects" {
  description = "List of allowed GitLab subjects (project paths with wildcards)"
  type        = list(string)
}

variable "max_session_duration" {
  description = "Maximum session duration in seconds"
  type        = number
  default     = 3600
}

variable "enable_ecr_access" {
  description = "Enable ECR push/pull access"
  type        = bool
  default     = true
}

variable "ecr_repository_arns" {
  description = "List of ECR repository ARNs to grant access to"
  type        = list(string)
  default     = []
}

variable "enable_eks_access" {
  description = "Enable EKS describe access"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
