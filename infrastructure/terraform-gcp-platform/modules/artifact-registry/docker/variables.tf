variable "project_id" {
  description = "Name of the project"
  type        = string
}

variable "repository_id" {
  description = "Name of the repository"
  type        = string
}

variable "location" {
  description = "Name of the location where this repository located in"
  type        = string
}

variable "description" {
  description = "Description of the repository"
  type        = string
}

variable "format" {
  description = "The format of packages that are stored in the repository"
  type        = string
  default     = "DOCKER"
}

variable "labels" {
  type        = map(string)
  description = "Labels, provided as a map"
}


variable "use_case" {
  type = string
}

variable "cleanup_policies" {
  description = "Optional cleanup policy blocks"
  type = list(object({
    action = string
    id     = string
    condition = object({
      tag_state             = optional(string)
      tag_prefixes          = optional(list(string))
      package_name_prefixes = optional(list(string))
      version_name_prefixes = optional(list(string))
      older_than            = optional(string)
    })
  }))
  default = []
}