variable "image" {
  description = "Boot disk image"
  type        = string
}

variable "project_id" {
  description = "The ID of the project where this GKE Cluster will be created"
  type        = string
}

variable "can_ip_forward" {
  description = "Enable IP forwarding"
  type        = bool
}

variable "deletion_protection" {
  description = "VM instance can be protected from accidental deletion"
  type        = bool
}

variable "labels" {
  type        = map(string)
  description = "Labels, provided as a map"
}
variable "zone" {
  description = "Name of the zone"
  type        = string
}
variable "machine_type" {
  description = "Name of the machine"
  type        = string
}
variable "name" {
  description = "Name of the instance"
  type        = string
}
variable "subnetwork_project" {
  description = "Name of the project"
  type        = string
}
variable "network" {
  description = "Name of the network"
  type        = string
}

variable "network_tier" {
  description = "Name of the network tire"
  type        = string
  default     = null
}

variable "stack_type" {
  description = "Type of stack IPV4 or IPV6"
  type        = string
}

variable "on_host_maintenance" {
  description = "maintenance of VM"
  type        = string
}
variable "preemptible" {
  description = "Preemptible VM's"
  type        = bool
}
variable "email" {
  description = "service account email"
  type        = string
}
variable "scopes" {
  description = "List of API's for accessing"
  type        = list(string)
}

variable "tags" {
  description = "List of tags"
  type        = list(string)
}

variable "subnetwork" {
  description = "Name of the subnetwork"
  type        = string
}
variable "size" {
  description = "Size of the boot disk"
  type        = string
}


variable "private_ip_name" {
  description = "The name of the private static ip."
  type        = string
  default     = ""
}

variable "address_type" {
  description = "The address type, can be EXTERNAL/INTERNAL."
  type        = string
  default     = ""
}

variable "purpose" {
  description = "The purpose of the static IP. GCE_ENDPOINT"
  type        = string
  default     = ""
}

variable "private_address" {
  description = "The reserved private static ip address"
  type        = string
  default     = null
}

variable "region" {
  description = "The region of the IP reserved"
  type        = string
  default     = ""
}

variable "create_static_private_ip" {
  description = "Whether to create static IP or not"
  type        = bool
  default     = false
}

variable "key_revocation_action_type" {
  type    = string
  default = ""
}
variable "auto_delete_disk" {
  type    = bool
  default = true
}

variable "create_static_public_ip" {
  type    = bool
  default = false
}

variable "public_ip_name" {
  type    = string
  default = ""
}

variable "address_type_public" {
  type    = string
  default = ""
}

variable "public_ip_address_description" {
  type    = string
  default = ""
}

variable "create_ephemeral_public_ip" {
  type        = bool
  default     = false
  description = "Set to true if an ephemeral public IP should be assigned"
}
