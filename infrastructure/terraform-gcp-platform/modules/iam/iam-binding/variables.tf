variable "service_account_id" {
  description = "The email of the service account to which IAM roles will be assigned"
  type        = string
}

variable "service_account_roles" {
  description = "List of IAM roles to assign to the service account"
  type        = list(string)
}

variable "members" {
  description = "List of members to assign the roles to"
  type        = list(string)
}
