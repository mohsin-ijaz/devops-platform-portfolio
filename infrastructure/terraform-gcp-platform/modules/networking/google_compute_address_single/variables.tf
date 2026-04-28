variable "address_name" {
  description = "The name of the address that we want to create"
  type        = string
}

variable "address_type" {
  description = "(Optional) The type of address to reserve. Default value is EXTERNAL. Possible values are INTERNAL and EXTERNAL."
  type        = string
  default     = "EXTERNAL"
  validation {
    condition     = contains(["INTERNAL", "EXTERNAL"], var.address_type)
    error_message = "The value must only be one of these valid values: INTERNAL, EXTERNAL."
  }
}


variable "labels" {
  description = "Labels to attach to the IP address"
  type        = map(string)
  default     = {}
}
