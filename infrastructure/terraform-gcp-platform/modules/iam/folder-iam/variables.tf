variable "folder" {
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
