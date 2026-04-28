variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = null
}

variable "address_name" {
  type = string
}

variable "scope" {
  type        = string
  description = "Scope of the address: global or regional"
  validation {
    condition     = can(regex("^(global|regional)$", var.scope))
    error_message = "scope must be 'global' or 'regional'."
  }
}

variable "address_type" {
  type        = string
  default     = "EXTERNAL"
  description = "Type of address: EXTERNAL or INTERNAL"
  validation {
    condition     = can(regex("^(EXTERNAL|INTERNAL)$", var.address_type))
    error_message = "address_type must be 'EXTERNAL' or 'INTERNAL'."
  }
}

