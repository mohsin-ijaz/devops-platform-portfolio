variable "region" {
  type        = string
  description = "The location of the ServiceConnectionPolicy"
}

variable "project_id" {
  type = string

}

variable "policy_name" {
  type        = string
  description = "Name of the sevice needs to be created"
}

variable "service_class" {
  type        = string
  description = "The service class identifier for which this ServiceConnectionPolicy is for"
}

variable "description" {
  type        = string
  description = "Description for the ServiceconnectionPolicy to be created"
}

variable "network" {
  type        = string
  description = "The resource path of the consumer network"
}

variable "subnetwork_ids" {
  type        = list(string)
  description = "IDs of the subnetworks or fully qualified identifiers for the subnetworks"

}