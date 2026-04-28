variable "project_id" {
  description = "Name of the project"
  type        = string
}
variable "address" {
  description = "The IP address or beginning of the address range represented by this resource"
  type        = string
}

variable "pvt_svc_name" {
  type = string
}
variable "network_name" {
  type        = string
  description = "Name of the network"
}

variable "import_custom_routes" {
  type = bool
}

variable "export_custom_routes" {
  type = bool
}

variable "peering_name" {
  type        = string
  description = "Name of the peering"
}

variable "address_type" {
  description = "The type of the address to reserve- Internal or External"
  type        = string
  default     = "INTERNAL"
}
variable "prefix_length" {
  description = "The prefix length of the IP range"
  type        = number
}
variable "purpose" {
  description = "The purpose of the resource- VPC_PEERING, PRIVATE_SERVICE_CONNECT"
  type        = string
  default     = "VPC_PEERING"
}
variable "service" {
  description = "Provider peering service that is managing peering connectivity for a service provider organization"
  type        = string
  default     = "servicenetworking.googleapis.com"
}
