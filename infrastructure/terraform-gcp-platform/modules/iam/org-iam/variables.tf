variable "org_id" {
  description = "The Organization ID"
  type        = string
}

variable "groups" {
  description = "A list of Google Groups and their IAM roles"
  type = list(object({
    email = string
    roles = list(string)
  }))
}

variable "service_accounts" {
  description = "List of service accounts and their roles"
  type = list(object({
    email = string
    roles = list(string)
  }))
}
