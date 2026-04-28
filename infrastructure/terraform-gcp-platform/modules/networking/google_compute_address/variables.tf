variable "address_name" {
  type = string
}

variable "number_of_addresses" {
  description = "(Optional) How many resources you want to create."
  type        = number
  default     = 1
}

variable "address" {
  description = "(Optional) The static external IP address represented by this resource. Only IPv4 is supported. An address may only be specified for INTERNAL address types. The IP address must be inside the specified subnetwork, if any."
  type        = string
  default     = null
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

variable "description" {
  description = "(Optional) An optional description of this resource."
  type        = string
  default     = null
}

variable "purpose" {
  description = "(Optional) The purpose of this resource, which can be one of the following values: GCE_ENDPOINT, SHARED_LOADBALANCER_VIP, VPC_PEERING, IPSEC_INTERCONNECT"
  type        = string
  default     = null
  validation {
    condition     = var.purpose == null || (var.purpose == null ? true : contains(["GCE_ENDPOINT", "SHARED_LOADBALANCER_VIP", "VPC_PEERING", "IPSEC_INTERCONNECT"], var.purpose))
    error_message = "The value must only be one of these valid values: GCE_ENDPOINT, SHARED_LOADBALANCER_VIP, VPC_PEERING, IPSEC_INTERCONNECT."
  }
}

variable "network_tier" {
  description = "(Optional) The networking tier used for configuring this address. If this field is not specified, it is assumed to be PREMIUM. Possible values are PREMIUM and STANDARD."
  type        = string
  default     = null
  validation {
    condition     = var.network_tier == null || (var.network_tier == null ? true : contains(["PREMIUM", "STANDARD"], var.network_tier))
    error_message = "The value must only be one of these valid values: PREMIUM, STANDARD."
  }
}

variable "subnetwork" {
  description = "(Optional) The URL of the subnetwork in which to reserve the address. If an IP address is specified, it must be within the subnetwork's IP range. This field can only be used with INTERNAL type with GCE_ENDPOINT/DNS_RESOLVER purposes."
  type        = string
  default     = null
}

variable "network_name" {
  description = "(Optional) The URL of the network in which to reserve the address. This field can only be used with INTERNAL type with the VPC_PEERING and IPSEC_INTERCONNECT purposes."
  type        = string
  default     = null
}

variable "prefix_length" {
  description = "(Optional) The prefix length if the resource represents an IP range."
  type        = string
  default     = null
}

variable "region" {
  description = "(Optional) The Region in which the created address should reside. If it is not provided, the provider region is used."
  type        = string
  default     = "asia-south1"
}

variable "project" {
  description = "(Optional) The ID of the project in which the resource belongs. If it is not provided, the provider project is used."
  type        = string
  default     = null
}

# ------------------------------------------------------------------------------
# MODULE CONFIGURATION PARAMETERS
# These variables are used to configure the module.
# ------------------------------------------------------------------------------

variable "module_enabled" {
  type        = bool
  description = "(Optional) Whether to create resources within the module or not. Default is 'true'."
  default     = true
}

variable "module_depends_on" {
  type        = any
  description = "(Optional) A list of external resources the module depends_on. Default is '[]'."
  default     = []
}