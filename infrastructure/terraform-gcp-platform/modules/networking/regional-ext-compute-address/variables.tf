variable "name" {
  description = "Name of the static IP"
  type        = string
}

variable "region" {
  description = "Region to reserve the IP in"
  type        = string
}

variable "labels" {
  description = "Labels to attach to the IP address"
  type        = map(string)
  default     = {}
}
