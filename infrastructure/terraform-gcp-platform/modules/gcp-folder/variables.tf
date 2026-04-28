variable "folder_name" {
  description = "The name of the department folder."
  type        = string
}

variable "parent_folder" {
  description = "The parent folder ID for the department folder."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
