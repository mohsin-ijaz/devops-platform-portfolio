variable "project_id" {
  description = "The ID of the GCP project."
  type        = string
}

variable "region" {
  description = "The region where resources will be created."
  type        = string
}

variable "subnetwork" {
  description = "The name of the subnetwork."
  type        = string
}

variable "project_roles" {
  type = list(string)
}

variable "members" {
  type = list(string)
}