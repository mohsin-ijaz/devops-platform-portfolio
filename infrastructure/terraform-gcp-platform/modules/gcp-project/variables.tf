variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "new_project_id" {
  description = "ID of the project"
  type        = string
}

variable "billing_account" {
  type        = string
  description = "Billing account of the org"
  default     = null
}

variable "org_id" {
  type        = string
  description = "Org ID of acme.com"
  default     = null
}

variable "folder_id" {
  type    = string
  default = null
}

variable "auto_create_network" {
  type        = bool
  description = "Auto create default network"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Labels, provided as a map"
  default     = {}
}