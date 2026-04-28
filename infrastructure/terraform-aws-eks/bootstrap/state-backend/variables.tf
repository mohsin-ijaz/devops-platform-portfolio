# Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "company" {
  description = "Company name for resource naming"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "environment" {
  description = "Environment name (network, uat, prod)"
  type        = string

  validation {
    condition     = contains(["network", "uat", "prod"], var.environment)
    error_message = "Environment must be one of: network, uat, prod."
  }
}

variable "additional_principals" {
  description = "Additional AWS account IDs that can access the state"
  type        = list(string)
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
}
